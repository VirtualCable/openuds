# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import operator
import random
import typing

from django.db import transaction
from django.db.models import Q, Count, Case, When, IntegerField
from django.utils.translation import gettext as _

from uds.core import consts, exceptions, types
from uds.core.exceptions.services import (
    InvalidServiceException,
    MaxServicesReachedError,
    OperationException,
    ServiceAccessDeniedByCalendar,
    ServiceInMaintenanceMode,
    ServiceNotReadyError,
)
from uds.core.util import log, singleton
from uds.core.util.decorators import cached
from uds.core.util.model import generate_uuid, sql_now
from uds.core.types.states import State
from uds.core.util.stats import events
from uds.models import MetaPool, ServicePool, ServicePoolPublication, Transport, User, UserService

from .userservice_helpers import comms
from .userservice_helpers.opchecker import UserServiceOpChecker

if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)
trace_logger = logging.getLogger('traceLog')
operations_logger = logging.getLogger('operationsLog')


class UserServiceManager(metaclass=singleton.Singleton):

    @staticmethod
    def manager() -> 'UserServiceManager':
        return UserServiceManager()  # Singleton pattern will return always the same instance

    @staticmethod
    def get_state_filter(service: 'models.Service') -> Q:
        """
        Returns a Q object that filters by valid states for a service
        """
        if service.old_max_accounting_method:  # If no limits and accounting method is not old one
            # Valid states are: PREPARING, USABLE
            states = [State.PREPARING, State.USABLE]
        else:  # New accounting method selected
            states = [State.PREPARING, State.USABLE, State.REMOVING, State.REMOVABLE]
        return Q(state__in=states)

    def _check_user_services_limit_reached(self, service_pool: ServicePool) -> None:
        """
        Checks if userservices_limit for the service has been reached, and, if so,
        raises an exception that no more services of this kind can be reached
        """
        if self.maximum_user_services_reached(service_pool.service):
            raise MaxServicesReachedError(
                _('Maximum number of user services reached for this {}').format(service_pool)
            )

    def get_cache_state_filter(self, servicepool: ServicePool, level: types.services.CacheLevel) -> Q:
        return Q(cache_level=level) & self.get_state_filter(servicepool.service)

    def get_existing_user_services(self, service: 'models.Service') -> int:
        """
        Returns the number of running user services for this service
        """
        return UserService.objects.filter(
            self.get_state_filter(service) & Q(deployed_service__service=service)
        ).count()

    def maximum_user_services_reached(self, service: 'models.Service') -> bool:
        """
        Checks if the maximum number of user services for this service has been reached
        """
        service_instance = service.get_instance()
        # Early return, so no database count is needed
        if service_instance.userservices_limit == consts.UNLIMITED:
            return False

        if self.get_existing_user_services(service) >= service_instance.userservices_limit:
            return True

        return False

    def _create_cache_user_service_at_db(
        self, publication: ServicePoolPublication, cache_level: int
    ) -> UserService:
        """
        Private method to instatiate a cache element at database with default states
        """
        # Checks if userservices_limit has been reached and if so, raises an exception
        self._check_user_services_limit_reached(publication.deployed_service)
        now = sql_now()
        return publication.userServices.create(
            cache_level=cache_level,
            state=State.PREPARING,
            os_state=State.PREPARING,
            state_date=now,
            creation_date=now,
            data='',
            deployed_service=publication.deployed_service,
            user=None,
            in_use=False,
        )

    def _create_assigned_user_service_at_db(
        self, publication: ServicePoolPublication, user: User
    ) -> UserService:
        """
        Private method to instatiate an assigned element at database with default state
        """
        self._check_user_services_limit_reached(publication.deployed_service)
        now = sql_now()
        return publication.userServices.create(
            cache_level=0,
            state=State.PREPARING,
            os_state=State.PREPARING,
            state_date=now,
            creation_date=now,
            data='',
            deployed_service=publication.deployed_service,
            user=user,
            in_use=False,
        )

    def _create_assigned_user_service_at_db_from_pool(
        self, service_pool: ServicePool, user: User
    ) -> UserService:
        """
        __createCacheAtDb and __createAssignedAtDb uses a publication for create the UserService.
        There is cases where deployed services do not have publications (do not need them), so we need this method to create
        an UserService with no publications, and create them from an ServicePool
        """
        self._check_user_services_limit_reached(service_pool)
        now = sql_now()
        return service_pool.userServices.create(
            cache_level=0,
            state=State.PREPARING,
            os_state=State.PREPARING,
            state_date=now,
            creation_date=now,
            data='',
            publication=None,
            user=user,
            in_use=False,
        )

    def create_cache_for(
        self, publication: ServicePoolPublication, cache_level: types.services.CacheLevel
    ) -> UserService:
        """
        Creates a new cache for the deployed service publication at level indicated
        """
        operations_logger.info(
            'Creating a new cache element at level %s for publication %s',
            cache_level,
            publication,
        )
        cache = self._create_cache_user_service_at_db(publication, cache_level)
        state = cache.get_instance().deploy_for_cache(cache_level)

        UserServiceOpChecker.state_updater(cache, state)
        return cache

    def create_assigned_for(self, service_pool: ServicePool, user: User) -> UserService:
        """
        Creates a new assigned deployed service for the current publication (if any) of service pool and user indicated
        """
        # First, honor concurrent_creation_limit
        if not self.can_grow_service_pool(service_pool):
            # Cannot create new
            operations_logger.info(
                'Too many preparing services. Creation of assigned service denied by max preparing services parameter. (login storm with insufficient cache?).'
            )
            raise MaxServicesReachedError()

        if service_pool.service.get_type().publication_type is not None:
            publication = service_pool.active_publication()
            if publication:
                assigned = self._create_assigned_user_service_at_db(publication, user)
                operations_logger.info(
                    'Creating a new assigned element for user %s for publication %s on pool %s',
                    user.pretty_name,
                    publication.revision,
                    service_pool.name,
                )
            else:
                raise InvalidServiceException(
                    f'Invalid publication creating service assignation: {service_pool.name} {user.pretty_name}'
                )
        else:
            operations_logger.info(
                'Creating a new assigned element for user %s on pool %s',
                user.pretty_name,
                service_pool.name,
            )
            assigned = self._create_assigned_user_service_at_db_from_pool(service_pool, user)

        assigned_instance = assigned.get_instance()
        state = assigned_instance.deploy_for_user(user)

        UserServiceOpChecker.make_unique(assigned, state)

        return assigned

    def create_from_assignable(self, service_pool: ServicePool, user: User, assignable_id: str) -> UserService:
        """
        Creates an assigned service from an "assignable" id
        """
        service_instance = service_pool.service.get_instance()
        if not service_instance.can_assign():
            raise Exception('This service type cannot assign asignables')

        if service_pool.service.get_type().publication_type is not None:
            publication = service_pool.active_publication()
            if publication:
                assigned = self._create_assigned_user_service_at_db(publication, user)
                operations_logger.info(
                    'Creating an assigned element from assignable %s for user %s for publication %s on pool %s',
                    assignable_id,
                    user.pretty_name,
                    publication.revision,
                    service_pool.name,
                )
            else:
                raise Exception(
                    f'Invalid publication creating service assignation: {service_pool.name} {user.pretty_name}'
                )
        else:
            operations_logger.info(
                'Creating an assigned element from assignable %s for user %s on pool %s',
                assignable_id,
                user.pretty_name,
                service_pool.name,
            )
            assigned = self._create_assigned_user_service_at_db_from_pool(service_pool, user)

        # Now, get from serviceInstance the data
        assigned_userservice_instance = assigned.get_instance()
        state = service_instance.assign_from_assignables(assignable_id, user, assigned_userservice_instance)
        # assigned.u(assignedInstance)

        UserServiceOpChecker.make_unique(assigned, state)

        return assigned

    def move_to_level(self, cache: UserService, cache_level: types.services.CacheLevel) -> None:
        """
        Moves a cache element from one level to another
        @return: cache element
        """
        cache.refresh_from_db()
        logger.debug('Moving cache %s to level %s', cache, cache_level)
        cache_instance = cache.get_instance()
        state = cache_instance.move_to_cache(cache_level)
        cache.cache_level = cache_level
        cache.save(update_fields=['cache_level'])
        logger.debug(
            'Service State: %a %s %s',
            State.from_str(state).localized,
            State.from_str(cache.state).localized,
            State.from_str(cache.os_state).localized,
        )
        if state.is_runing() and cache.is_usable():
            cache.set_state(State.PREPARING)

        # Data will be serialized on makeUnique process
        UserServiceOpChecker.make_unique(cache, state)

    def forced_move_assigned_to_cache_l1(self, user_service: UserService) -> None:
        """
        Clones the record of a user serviceself.
        For this, the original userservice will ve moved to cache, and a new one will be created
        to mark it as "REMOVED"

        The reason for creating a new one with cloned data is "conserving" a deleted record, so we can track it
        as usual
        """
        # Load again to get a copy of the object
        user_service_copy = UserService.objects.get(id=user_service.id)
        user_service_copy.pk = None
        user_service_copy.uuid = generate_uuid()
        user_service_copy.in_use = False
        user_service_copy.state = State.REMOVED
        user_service_copy.os_state = State.USABLE

        # Save the new element.
        user_service_copy.save()

        # Now, move the original to cache, but do it "hard" way, so we do not need to check for state
        user_service.state = State.USABLE
        user_service.os_state = State.USABLE
        user_service.user = None
        user_service.cache_level = types.services.CacheLevel.L1
        user_service.in_use = False
        user_service.src_hostname = user_service.src_ip = ''
        user_service.save()

    def get_cache_servicepool_stats(
        self,
        servicepool: ServicePool,
        assigned_increased_by: int = 0,
        l1_cache_increased_by: int = 0,
        l2_cache_increased_by: int = 0,
    ) -> 'types.services.ServicePoolStats':
        """
        Returns the stats (for cache pourposes) for a service pool.

        increasers are used so we can simulate the removal of some elements and check if we need to grow cache
        (for exampl)
        """
        # State filter for cached and inAssigned objects
        # First we get all deployed services that could need cache generation
        # We start filtering out the deployed services that do not need caching at all.
        if (
            servicepool.max_srvs == 0
            or servicepool.state != State.ACTIVE
            or servicepool.service.provider.maintenance_mode is True
        ):
            return types.services.ServicePoolStats.null()  # No cache needed for this servicepool

        service_instance = servicepool.service.get_instance()

        servicepool.userservices.update()  # Cleans cached queries

        # If this deployedService don't have a publication active and needs it, ignore it
        service_instance = servicepool.service.get_instance()

        if service_instance.uses_cache is False:
            logger.debug(
                'Service pool does not uses cache: %s',
                servicepool.name,
            )
            return types.services.ServicePoolStats.null()

        if servicepool.active_publication() is None and service_instance.publication_type is not None:
            logger.debug(
                'Service pool needs publication and has none: %s',
                servicepool.name,
            )
            return types.services.ServicePoolStats.null()

        # If it has any running publication, do not generate cache anymore
        if servicepool.publications.filter(state=State.PREPARING).count() > 0:
            logger.debug(
                'Service pool with publication running: %s',
                servicepool.name,
            )
            return types.services.ServicePoolStats.null()

        if servicepool.is_restrained():
            logger.debug(
                'Restrained service pool: %s',
                servicepool.name,
            )
            return types.services.ServicePoolStats.null()

        # Get data related to actual state of cache
        # Before we were removing the elements marked to be destroyed after creation, but this makes us
        # to create new items over the limit stablisshed, so we will not remove them anymore
        l1_cache_filter = self.get_cache_state_filter(servicepool, types.services.CacheLevel.L1)
        l2_cache_filter = self.get_cache_state_filter(servicepool, types.services.CacheLevel.L2)
        assigned_filter = self.get_cache_state_filter(servicepool, types.services.CacheLevel.NONE)

        counts: dict[str, int] = servicepool.userservices.aggregate(
            l1_cache_count=Count(Case(When(l1_cache_filter, then=1), output_field=IntegerField()))
            + l1_cache_increased_by,
            l2_cache_count=Count(Case(When(l2_cache_filter, then=1), output_field=IntegerField()))
            + l2_cache_increased_by,
            assigned_count=Count(Case(When(assigned_filter, then=1), output_field=IntegerField()))
            + assigned_increased_by,
        )

        pool_stat = types.services.ServicePoolStats(
            servicepool,
            l1_cache_count=counts['l1_cache_count'] + l1_cache_increased_by,
            l2_cache_count=counts['l2_cache_count'] + l2_cache_increased_by,
            assigned_count=counts['assigned_count'] + assigned_increased_by,
        )

        # if we bypasses max cache, we will reduce it in first place. This is so because this will free resources on service provider
        logger.debug("Examining %s", pool_stat)

        # Check for cache overflow
        # We have more than we want
        if pool_stat.has_l1_cache_overflow() or pool_stat.has_l2_cache_overflow():
            logger.debug('We have more services than max configured.')
            return pool_stat

        # Check for cache needed
        # If this service don't allows more starting user services...
        if not UserServiceManager.manager().can_grow_service_pool(servicepool):
            logger.debug(
                'This pool cannot grow rithg now: %s',
                servicepool,
            )
            return types.services.ServicePoolStats.null()

        if pool_stat.is_l1_cache_growth_required() or pool_stat.is_l2_cache_growth_required():
            logger.debug('Needs to grow L1 cache for %s', servicepool)
            return pool_stat

        # If this point reached, we do not need any cache
        return types.services.ServicePoolStats.null()

    def cancel(self, user_service: UserService) -> None:
        """
        Cancels an user service creation
        @return: the Uservice canceling
        """
        user_service.refresh_from_db()

        if user_service.is_preparing() is False:
            logger.debug('Cancel requested for a non running operation, performing removal instead')
            return self.remove(user_service)

        operations_logger.info('Canceling userservice %s', user_service.name)
        user_service_instance = user_service.get_instance()

        # We have fixed cancelling
        # previuously, we only allows cancelling if cancel method
        # was overrided, but now, we invoke cancel in any case
        # And will let the service to decide if it can cancel, delay it or whatever
        user_service.set_state(State.CANCELING)
        # We simply notify service that it should cancel operation
        state = user_service_instance.cancel()

        # Data will be serialized on makeUnique process
        # If cancel is not supported, base cancel always returns "FINISHED", and
        # opchecker will set state to "removable"
        UserServiceOpChecker.make_unique(user_service, state)

    def remove(self, userservice: UserService) -> None:
        """
        Removes an user service
        """
        with transaction.atomic():
            userservice = UserService.objects.select_for_update().get(id=userservice.id)
            operations_logger.info('Removing userservice %a', userservice.name)
            if userservice.is_usable() is False and State.from_str(userservice.state).is_removable() is False:
                raise OperationException(_('Can\'t remove a non active element'))
            userservice.set_state(State.REMOVING)
            logger.debug("***** The state now is %s *****", State.from_str(userservice.state).localized)
            userservice.set_in_use(False)  # For accounting, ensure that it is not in use right now
            userservice.save()

        state = userservice.get_instance().destroy()

        # Data will be serialized on makeUnique process
        UserServiceOpChecker.make_unique(userservice, state)

    def remove_or_cancel(self, user_service: UserService) -> None:
        if user_service.is_usable() or State.from_str(user_service.state).is_removable():
            return self.remove(user_service)

        if user_service.is_preparing():
            return self.cancel(user_service)

        raise OperationException(
            _('Can\'t remove nor cancel {} cause its state don\'t allow it').format(user_service.name)
        )

    def release_from_logout(self, userservice: UserService) -> None:
        """
        In case of logout, this method will take care of removing the service
        This is so because on logout, may the userservice returns back to cache if ower service
        desired it that way.

        This method will take care of removing the service if no cache is desired of cache already full (on servicepool)
        """
        if userservice.allow_putting_back_to_cache() is False:
            userservice.release()  # Normal release
            return

        # Some sanity checks, should never happen
        if userservice.cache_level != types.services.CacheLevel.NONE:
            logger.error('Cache level is not NONE for userservice %s on release_on_logout', userservice)
            userservice.release()
            return

        if userservice.is_usable() is False:
            logger.error('State is not USABLE for userservice %s on release_on_logout', userservice)
            userservice.release()
            return

        # Fix assigned value, because "userservice" will not count as assigned anymore
        stats = self.get_cache_servicepool_stats(userservice.deployed_service, assigned_increased_by=-1)

        # Note that only moves to cache L1
        # Also, we can get values for L2 cache, thats why we check L1 for overflow and needed
        if stats.is_null() or stats.has_l1_cache_overflow():
            userservice.release()  # Mark as removable
        elif stats.is_l1_cache_growth_required():
            # Move the clone of the user service to cache, and set our as REMOVED
            self.forced_move_assigned_to_cache_l1(userservice)

    def get_existing_assignation_for_user(
        self, service_pool: ServicePool, user: User
    ) -> typing.Optional[UserService]:
        existing = service_pool.assigned_user_services().filter(
            user=user, state__in=State.VALID_STATES
        )  # , deployed_service__visible=True
        if existing.exists():
            logger.debug('Found assigned service from %s to user %s', service_pool, user.name)
            return existing.first()
        return None

    def get_assignation_for_user(
        self, servicepool: ServicePool, user: User
    ) -> typing.Optional[UserService]:  # pylint: disable=too-many-branches
        if servicepool.service.get_instance().spawns_new is False:  # Locate first if we have an assigned one
            assigned_userservice = self.get_existing_assignation_for_user(servicepool, user)
        else:
            assigned_userservice = None

        # If has an assigned user service, returns this without any more work
        if assigned_userservice:
            return assigned_userservice

        if servicepool.is_restrained():
            raise InvalidServiceException(_('The requested service is restrained'))

        if servicepool.uses_cache:
            cache: typing.Optional[UserService] = None
            # Now try to locate 1 from cache already "ready" (must be usable and at level 1)
            with transaction.atomic():
                caches = typing.cast(
                    list[UserService],
                    servicepool.cached_users_services()
                    .select_for_update()
                    .filter(
                        cache_level=types.services.CacheLevel.L1,
                        state=State.USABLE,
                        os_state=State.USABLE,
                    )[:1],
                )
                if caches:
                    cache = caches[0]
                    # Ensure element is reserved correctly on DB
                    if (
                        servicepool.cached_users_services()
                        .select_for_update()
                        .filter(user=None, uuid=cache.uuid)
                        .update(user=user, cache_level=0)
                        != 1
                    ):
                        cache = None
                else:
                    cache = None

            # Out of previous atomic
            if not cache:
                with transaction.atomic():
                    caches = typing.cast(
                        list[UserService],
                        servicepool.cached_users_services()
                        .select_for_update()
                        .filter(cache_level=types.services.CacheLevel.L1, state=State.USABLE)[:1],
                    )
                    if caches:  # If there is a cache, we will use it
                        cache = caches[0]
                        if (
                            servicepool.cached_users_services()
                            .select_for_update()
                            .filter(user=None, uuid=cache.uuid)
                            .update(user=user, cache_level=0)
                            != 1
                        ):
                            cache = None
                    else:
                        cache = None

            # Out of atomic transaction
            if cache:
                # Early assign
                cache.assign_to(user)

                logger.debug(
                    'Found a cached-ready service from %s for user %s, item %s',
                    servicepool,
                    user,
                    cache,
                )
                events.add_event(
                    servicepool,
                    types.stats.EventType.CACHE_HIT,
                    fld1=servicepool.cached_users_services()
                    .filter(cache_level=types.services.CacheLevel.L1, state=State.USABLE)
                    .count(),
                )
                return cache

            # Cache missed

            # Now find if there is a preparing one
            with transaction.atomic():
                caches = list(
                    servicepool.cached_users_services()
                    .select_for_update()
                    .filter(cache_level=types.services.CacheLevel.L1, state=State.PREPARING)[:1]
                )
                if caches:  # If there is a cache, we will use it
                    cache = caches[0]
                    if (
                        servicepool.cached_users_services()
                        .select_for_update()
                        .filter(user=None, uuid=cache.uuid)
                        .update(user=user, cache_level=0)
                        != 1
                    ):
                        cache = None
                else:
                    cache = None

            # Out of atomic transaction
            if cache:
                cache.assign_to(user)

                logger.debug(
                    'Found a cached-preparing service from %s for user %s, item %s',
                    servicepool,
                    user,
                    cache,
                )
                events.add_event(
                    servicepool,
                    events.types.stats.EventType.CACHE_MISS,
                    fld1=servicepool.cached_users_services()
                    .filter(cache_level=types.services.CacheLevel.L1, state=State.PREPARING)
                    .count(),
                )
                return cache

            # Can't assign directly from L2 cache... so we check if we can create e new service in the limits requested
            service_type = servicepool.service.get_type()
            if service_type.uses_cache:
                in_assigned = (
                    servicepool.assigned_user_services()
                    .filter(self.get_state_filter(servicepool.service))
                    .count()
                )
                if (
                    in_assigned >= servicepool.max_srvs
                ):  # cacheUpdater will drop unnecesary L1 machines, so it's not neccesary to check against inCacheL1
                    log.log(
                        servicepool,
                        types.log.LogLevel.WARNING,
                        f'Max number of services reached: {servicepool.max_srvs}',
                        types.log.LogSource.INTERNAL,
                    )
                    raise MaxServicesReachedError()

            # Can create new service, create it
            events.add_event(servicepool, events.types.stats.EventType.CACHE_MISS, fld1=0)
        return self.create_assigned_for(servicepool, user)

    def count_userservices_in_states_for_provider(self, provider: 'models.Provider', states: list[str]) -> int:
        """
        Returns the number of services of a service provider in the state indicated
        """
        return UserService.objects.filter(
            deployed_service__service__provider=provider, state__in=states
        ).count()

    # Avoids too many complex queries to database
    @cached(prefix='max_srvs', timeout=30)  # Less than user service removal check time
    def is_userservice_removal_allowed(self, service_pool: ServicePool) -> bool:
        """
        checks if we can do a "remove" from a deployed service
        """
        removing = self.count_userservices_in_states_for_provider(
            service_pool.service.provider, [State.REMOVING]
        )
        service_instance = service_pool.service.get_instance()
        if (
            (
                removing >= service_instance.provider().get_concurrent_removal_limit()
                and service_instance.provider().get_ignore_limits() is False
            )
            or service_pool.service.provider.is_in_maintenance()
            or service_pool.is_restrained()
            or not service_instance.is_avaliable()
        ):
            return False

        return True

    def can_grow_service_pool(self, service_pool: ServicePool) -> bool:
        """
        Checks if we can start a new service
        """
        number_of_preparing = self.count_userservices_in_states_for_provider(
            service_pool.service.provider, [State.PREPARING]
        )
        service_instance = service_pool.service.get_instance()
        if self.maximum_user_services_reached(service_pool.service) or (
            number_of_preparing >= service_instance.provider().get_concurrent_creation_limit()
            and service_instance.provider().get_ignore_limits() is False
        ):
            return False
        return True

    def is_ready(self, user_service: UserService) -> bool:
        user_service.refresh_from_db()
        logger.debug('Checking ready of %s', user_service)

        if user_service.state != State.USABLE or user_service.os_state != State.USABLE:
            logger.debug('State is not usable for %s', user_service.name)
            return False

        logger.debug('Service %s is usable, checking it via set_ready', user_service)
        userservice_instance = user_service.get_instance()
        try:
            state = userservice_instance.set_ready()
        except Exception as e:
            logger.warning('Could not check readyness of %s: %s', user_service, e)
            return False

        logger.debug('State: %s', state)

        if state == types.states.TaskState.FINISHED:
            user_service.update_data(userservice_instance)
            return True

        user_service.set_state(State.PREPARING)
        UserServiceOpChecker.make_unique(user_service, state)

        return False

    def reset(self, userservice: UserService) -> None:
        userservice.refresh_from_db()

        if not userservice.deployed_service.service.get_type().can_reset:
            return

        operations_logger.info('Reseting %s', userservice)

        userservice_instance = userservice.get_instance()
        try:
            state = userservice_instance.reset()
            userservice.update_state_date()

            log.log(
                userservice,
                types.log.LogLevel.INFO,
                'Service reset by user',
                types.log.LogSource.WEB,
            )
        except Exception:
            logger.exception('Reseting service')
            return

        logger.debug('State: %s', state)

        if state == types.states.TaskState.FINISHED:
            userservice.update_data(userservice_instance)
            return

        UserServiceOpChecker.make_unique(userservice, state)

    def notify_preconnect(self, userservice: UserService, info: types.connections.ConnectionData) -> None:
        try:
            comms.notify_preconnect(userservice, info)
        except exceptions.actor.NoActorComms:  # If no comms url for userService, try with service
            userservice.deployed_service.service.notify_preconnect(userservice, info)

    def check_user_service_uuid(self, userservice: UserService) -> bool:
        return comms.check_user_service_uuid(userservice)

    def request_screenshot(self, userservice: UserService) -> None:
        # Screenshot will request an screenshot to the actor
        # And the actor will return back, via REST actor API, the screenshot
        comms.request_screenshot(userservice)

    def send_script(self, userservice: UserService, script: str, exec_on_user: bool = False) -> None:
        comms.send_script(userservice, script, exec_on_user)

    def request_logoff(self, userservice: UserService) -> None:
        comms.request_logoff(userservice)

    def send_message(self, userservice: UserService, message: str) -> None:
        comms.send_message(userservice, message)

    def process_not_in_use_and_old_publication(self, userservice: UserService) -> None:
        """
        This method is used by UserService when a request for set_in_use(False) is made
        This checks that the userservice can continue existing or not
        """
        osmanager = userservice.deployed_service.osmanager
        # If os manager says "machine is persistent", do not try to delete "previous version" assigned machines
        do_publication_cleanup = True if not osmanager else not osmanager.get_instance().is_persistent()

        if do_publication_cleanup:
            remove = False
            with transaction.atomic():
                userservice = UserService.objects.select_for_update().get(id=userservice.id)
                active_publication = userservice.deployed_service.active_publication()
                if (
                    userservice.publication
                    and active_publication
                    and userservice.publication.id != active_publication.id
                ):
                    logger.debug(
                        'Old revision of user service, marking as removable: %s',
                        userservice,
                    )
                    remove = True

            if remove:
                userservice.release()

    def notify_ready_from_os_manager(self, userservice: UserService, data: typing.Any) -> None:
        try:
            userservice_instance = userservice.get_instance()
            logger.debug('Notifying user service ready state')
            state = userservice_instance.process_ready_from_os_manager(data)
            logger.debug('State: %s', state)
            if state == types.states.TaskState.FINISHED:
                userservice.update_data(userservice_instance)
                logger.debug('Service is now ready')
            elif userservice.state in (
                State.USABLE,
                State.PREPARING,
            ):  # We don't want to get active deleting or deleted machines...
                userservice.set_state(State.PREPARING)
                # Make unique will make sure that we do not have same machine twice
                UserServiceOpChecker.make_unique(userservice, state)
            userservice.save(update_fields=['os_state'])
        except Exception as e:
            logger.exception('Unhandled exception on notyfyready: %s', e)
            userservice.set_state(State.ERROR)
            return

    def locate_user_service(
        self, user: User, userservice_id: str, create: bool = False
    ) -> typing.Optional[UserService]:
        """
        Locates a user service from a user and a service id

        Args:
            user: User owner of the service
            id_service: Service id (A<uuid> for assigned, M<uuid> for meta, ?<uuid> for service pool)
            create: If True, will create a new service if not found
        """
        kind, uuid_userservice_pool = userservice_id[0], userservice_id[1:]

        logger.debug('Kind of service: %s, idservice: %s', kind, uuid_userservice_pool)
        userservice: typing.Optional[UserService] = None

        if kind in 'A':  # This is an assigned service
            logger.debug('Getting assugned user service %s', uuid_userservice_pool)
            try:
                userservice = UserService.objects.get(uuid=uuid_userservice_pool, user=user)
                userservice.service_pool.validate_user(user)
            except UserService.DoesNotExist:
                logger.debug('Service does not exist')
                return None
        else:
            logger.debug('Getting service pool %s', uuid_userservice_pool)
            try:
                service_pool: ServicePool = ServicePool.objects.get(uuid=uuid_userservice_pool)
                # We first do a sanity check for this, if the user has access to this service
                # If it fails, will raise an exception
                service_pool.validate_user(user)

                # Now we have to locate an instance of the service, so we can assign it to user.
                if create:  # getAssignation, if no assignation is found, tries to create one
                    userservice = self.get_assignation_for_user(service_pool, user)
                else:  # Sometimes maybe we only need to locate the existint user service
                    userservice = self.get_existing_assignation_for_user(service_pool, user)
            except ServicePool.DoesNotExist:
                logger.debug('Service pool does not exist')
                return None

        logger.debug('Found service: %s', userservice)

        if userservice and userservice.state == State.ERROR:
            return None

        return userservice

    def get_user_service_info(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        self,
        user: User,
        os: 'types.os.DetectedOsInfo',
        src_ip: str,
        user_service_id: str,
        transport_id: typing.Optional[str],
        test_userservice_status: bool = True,
        client_hostname: typing.Optional[str] = None,
    ) -> types.services.UserServiceInfo:
        """
        Get service info from user service

        Args:
            user: User owner of the service
            os: Detected OS (as provided by request)
            src_ip: Source IP of the request
            user_service_id: User service id (A<uuid> for assigned, M<uuid> for meta, ?<uuid> for service pool)
            transport_id: Transport id (optional). If not provided, will try to find a suitable one
            validate_with_test: If True, will check if the service is ready
            client_hostname: Client hostname (optional). If not provided, will use src_ip

        Returns:
            UserServiceInfo: User service info
        """
        if user_service_id[0] == 'M':  # Meta pool
            return self.get_meta_service_info(user, src_ip, os, user_service_id[1:], transport_id or 'meta')

        userservice = self.locate_user_service(user, user_service_id, create=True)

        if not userservice:
            raise InvalidServiceException(
                _('Invalid service. The service is not available at this moment. Please, try later')
            )

        # Early log of "access try" so we can imagine what is going on
        userservice.set_connection_source(types.connections.ConnectionSource(src_ip, client_hostname or src_ip))

        if userservice.is_in_maintenance():
            raise ServiceInMaintenanceMode()

        if not userservice.deployed_service.is_access_allowed():
            raise ServiceAccessDeniedByCalendar()

        if not transport_id:  # Find a suitable transport
            for transport in userservice.deployed_service.transports.order_by('priority'):
                transport_type = transport.get_type()
                if (
                    transport_type
                    and transport.is_ip_allowed(src_ip)
                    and transport_type.supports_os(os.os)
                    and transport.is_os_allowed(os.os)
                ):
                    transport_id = transport.uuid
                    break
            else:
                raise InvalidServiceException(_('No suitable transport found'))

        try:
            transport = Transport.objects.get(uuid=transport_id)
        except Transport.DoesNotExist:
            raise InvalidServiceException(_('No suitable transport found'))

        # Ensures that the transport is allowed for this service
        if userservice.deployed_service.transports.filter(id=transport.id).count() == 0:
            raise InvalidServiceException()

        # If transport is not available for the request IP...
        if not transport.is_ip_allowed(src_ip):
            msg = _('The requested transport {} is not valid for {}').format(transport.name, src_ip)
            logger.error(msg)
            raise InvalidServiceException(msg)

        username = user.name if user else 'unknown'

        if not test_userservice_status:
            # traceLogger.info('GOT service "{}" for user "{}" with transport "{}" (NOT TESTED)'.format(userService.name, userName, trans.name))
            return types.services.UserServiceInfo(
                ip=None,
                userservice=userservice,
                transport=transport,
            )
            # return None, userservice, None, transport, None

        userservice_status: types.services.ReadyStatus = types.services.ReadyStatus.USERSERVICE_NOT_READY
        ip = 'unknown'
        # Test if the service is ready
        if userservice.is_ready():
            # Is ready, update possible state
            userservice_status = types.services.ReadyStatus.USERSERVICE_NO_IP
            log.log(
                userservice,
                types.log.LogLevel.INFO,
                f"User {user.pretty_name} from {src_ip} has initiated access",
                types.log.LogSource.WEB,
            )
            # If ready, show transport for this service, if also ready ofc
            userservice_instance = userservice.get_instance()
            ip = userservice_instance.get_ip()
            userservice.log_ip(ip)  # Update known ip
            logger.debug('IP: %s', ip)

            if self.check_user_service_uuid(userservice) is False:  # The service is not the expected one
                userservice_status = types.services.ReadyStatus.USERSERVICE_INVALID_UUID
                log.log(
                    userservice,
                    types.log.LogLevel.WARNING,
                    f'User service is not accessible due to invalid UUID (user: {user.pretty_name}, ip: {ip})',
                    types.log.LogSource.TRANSPORT,
                )
                logger.debug('UUID check failed for user service %s', userservice)
            else:
                events.add_event(
                    userservice.deployed_service,
                    events.types.stats.EventType.ACCESS,
                    username=username,
                    srcip=src_ip,
                    dstip=ip,
                    uniqueid=userservice.unique_id,
                )
                if ip:
                    userservice_status = types.services.ReadyStatus.TRANSPORT_NOT_READY
                    transport_instance = transport.get_instance()
                    if transport_instance.is_ip_allowed(userservice, ip):
                        log.log(
                            userservice, types.log.LogLevel.INFO, "User service ready", types.log.LogSource.WEB
                        )
                        self.notify_preconnect(
                            userservice,
                            transport_instance.get_connection_info(userservice, user, ''),
                        )
                        trace_logger.info(
                            'READY on service "%s" for user "%s" with transport "%s" (ip:%s)',
                            userservice.name,
                            username,
                            transport.name,
                            ip,
                        )
                        return types.services.UserServiceInfo(
                            ip=ip,
                            userservice=userservice,
                            transport=transport,
                        )
                        # return ( ip, userservice, userservice_instance, transport, transport_instance)

                    message = transport_instance.get_available_error_msg(userservice, ip)
                    log.log(userservice, types.log.LogLevel.WARNING, message, types.log.LogSource.TRANSPORT)
                    logger.debug(
                        'Transport is not ready for user service %s: %s',
                        userservice,
                        message,
                    )
                else:
                    logger.debug('Ip not available from user service %s', userservice)
        else:
            log.log(
                userservice,
                types.log.LogLevel.WARNING,
                f'User {user.pretty_name} from {src_ip} tried to access, but service was not ready',
                types.log.LogSource.WEB,
            )

        trace_logger.error(
            'ERROR %s on service "%s" for user "%s" with transport "%s" (ip:%s)',
            userservice_status,
            userservice.name,
            username,
            transport.name,
            ip,
        )
        raise ServiceNotReadyError(code=userservice_status, user_service=userservice, transport=transport)

    def is_meta_service(self, meta_id: str) -> bool:
        return meta_id[0] == 'M'

    def locate_meta_service(self, user: User, id_metapool: str) -> typing.Optional[UserService]:
        kind, uuid_metapool = id_metapool[0], id_metapool[1:]
        if kind != 'M':
            return None

        meta: MetaPool = MetaPool.objects.get(uuid=uuid_metapool)
        # Get pool members. Just pools enabled, that are "visible" and "usable"
        pools = [p.pool for p in meta.members.filter(enabled=True) if p.pool.is_visible() and p.pool.is_usable()]
        # look for an existing user service in the pool
        try:
            return UserService.objects.filter(
                deployed_service__in=pools,
                state__in=State.VALID_STATES,
                user=user,
                cache_level=0,
            ).order_by('deployed_service__name')[0]
        except IndexError:
            return None

    def get_meta_service_info(
        self,
        user: User,
        src_ip: str,
        os: 'types.os.DetectedOsInfo',
        id_metapool: str,
        id_transport: str,
        client_hostname: typing.Optional[str] = None,
    ) -> types.services.UserServiceInfo:
        logger.debug('This is meta')
        # We need to locate the service pool related to this meta, and also the transport
        # First, locate if there is a service in any pool associated with this metapool
        meta: MetaPool = MetaPool.objects.get(uuid=id_metapool)

        # If access is denied by calendar...
        if meta.is_access_allowed() is False:
            raise ServiceAccessDeniedByCalendar()

        # Get pool members. Just pools "visible" and "usable"
        metapool_members = [p for p in meta.members.filter(enabled=True) if p.pool.is_visible() and p.pool.is_usable()]
        # Sort pools array. List of tuples with (priority, pool)
        pools_sorted: list[tuple[int, ServicePool]]
        # Sort pools based on meta selection
        if meta.policy == types.pools.LoadBalancingPolicy.PRIORITY:
            pools_sorted = [(p.priority, p.pool) for p in metapool_members]
        elif meta.policy == types.pools.LoadBalancingPolicy.GREATER_PERCENT_FREE:
            pools_sorted = [(p.pool.usage().percent, p.pool) for p in metapool_members]
        else:
            pools_sorted = [
                (
                    random.randint(
                        0, 10000
                    ),  # nosec: just a suffle, not a crypto (to get a round robin-like behavior)
                    p.pool,
                )
                for p in metapool_members
            ]  # Just shuffle them

        # Sort pools related to policy now, and xtract only pools, not sort keys
        # split resuult in two lists, 100% full and not 100% full
        # Remove "full" pools (100%) from result and pools in maintenance mode, not ready pools, etc...
        pools_sorted = sorted(pools_sorted, key=operator.itemgetter(0))  # sort by priority (first element)
        pools: list[ServicePool] = []
        fully_occupied_pools: list[ServicePool] = []
        for p in pools_sorted:
            if not p[1].is_usable():
                continue
            if p[1].usage().percent == 100:
                fully_occupied_pools.append(p[1])
            else:
                pools.append(p[1])

        logger.debug('Pools: %s/%s', pools, fully_occupied_pools)

        usable: typing.Optional[tuple[ServicePool, Transport]] = None
        # Now, Lets find first if there is one assigned in ANY pool

        def _ensure_transport(
            pool: ServicePool,
        ) -> typing.Optional[tuple[ServicePool, Transport]]:
            found = None
            t: Transport
            if id_transport == 'meta':  # Autoselected:
                q = pool.transports.all()
            elif id_transport[:6] == 'LABEL:':
                q = pool.transports.filter(label=id_transport[6:])
            else:
                q = pool.transports.filter(uuid=id_transport)
            for t in q.order_by('priority'):
                transport_type = t.get_type()
                if (
                    transport_type
                    and t.get_type()
                    and t.is_ip_allowed(src_ip)
                    and transport_type.supports_os(os.os)
                    and t.is_os_allowed(os.os)
                ):
                    found = (pool, t)
                    break
            return found

        try:
            # Already assigned should look for in all usable pools, not only "non-full" ones
            already_assigned: UserService = UserService.objects.filter(
                deployed_service__in=pools + fully_occupied_pools,
                state__in=State.VALID_STATES,
                user=user,
                cache_level=0,
            ).order_by('deployed_service__name')[0]
            logger.debug('Already assigned %s', already_assigned)
            # If already assigned, and HA is enabled, check if it is accessible
            if meta.ha_policy == types.pools.HighAvailabilityPolicy.ENABLED:
                # Check that servide is accessible
                if (
                    not already_assigned.deployed_service.service.get_instance().is_avaliable()
                ):  # Not available, mark for removal
                    already_assigned.release()
                raise Exception()  # And process a new access

            # Ensure transport is available for the OS, and store it
            usable = _ensure_transport(already_assigned.deployed_service)
            # Found already assigned, ensure everythinf is fine
            if usable:
                return self.get_user_service_info(
                    user,
                    os,
                    src_ip,
                    'F' + usable[0].uuid,
                    usable[1].uuid,
                    test_userservice_status=False,
                    client_hostname=client_hostname,
                )
            # Not usable, will notify that it is not accessible

        except Exception:  # No service already assigned, lets find a suitable one
            for pool in pools:  # Pools are already sorted, and "full" pools are filtered out
                if meta.ha_policy == types.pools.HighAvailabilityPolicy.ENABLED:
                    # If not available, skip it
                    if pool.service.get_instance().is_avaliable() is False:
                        continue

                # Ensure transport is available for the OS
                usable = _ensure_transport(pool)

                # Stop if a pool-transport is found and can be assigned to user
                if usable:
                    try:
                        usable[0].validate_user(user)
                        return self.get_user_service_info(
                            user,
                            os,
                            src_ip,
                            'F' + usable[0].uuid,
                            usable[1].uuid,
                            test_userservice_status=False,
                            client_hostname=client_hostname,
                        )
                    except Exception as e:
                        logger.info(
                            'Meta service %s:%s could not be assigned, trying a new one',
                            usable[0].name,
                            e,
                        )
                        usable = None

        log.log(
            meta,
            types.log.LogLevel.WARNING,
            f'No user service accessible from device (ip {src_ip}, os: {os.os.name})',
            types.log.LogSource.SERVICE,
        )
        raise InvalidServiceException(_('The service is not accessible from this device'))
