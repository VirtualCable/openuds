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
from django.db.models import Q
from django.utils.translation import gettext as _

from uds.core import consts, exceptions, services, transports, types
from uds.core.services.exceptions import (
    InvalidServiceException,
    MaxServicesReachedError,
    OperationException,
    ServiceAccessDeniedByCalendar,
    ServiceInMaintenanceMode,
    ServiceNotReadyError,
)
from uds.core.util import log, singleton
from uds.core.util.decorators import cached
from uds.core.util.model import sql_now
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

    def get_cache_state_filter(self, service_pool: ServicePool, level: types.services.CacheLevel) -> Q:
        return Q(cache_level=level) & self.get_state_filter(service_pool.service)

    @staticmethod
    def get_state_filter(service: 'models.Service') -> Q:
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
        self, publication: ServicePoolPublication, cacheLevel: int
    ) -> UserService:
        """
        Private method to instatiate a cache element at database with default states
        """
        # Checks if userservices_limit has been reached and if so, raises an exception
        self._check_user_services_limit_reached(publication.deployed_service)
        now = sql_now()
        return publication.userServices.create(
            cache_level=cacheLevel,
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
        ci = cache.get_instance()
        state = ci.deploy_for_cache(cache_level)

        UserServiceOpChecker.state_updater(cache, ci, state)
        return cache

    def create_assigned_for(self, service_pool: ServicePool, user: User) -> UserService:
        """
        Creates a new assigned deployed service for the current publication (if any) of service pool and user indicated
        """
        # First, honor concurrent_creation_limit
        if self.can_grow_service_pool(service_pool) is False:
            # Cannot create new
            operations_logger.info(
                'Too many preparing services. Creation of assigned service denied by max preparing services parameter. (login storm with insufficient cache?).'
            )
            raise ServiceNotReadyError()

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

        UserServiceOpChecker.make_unique(assigned, assigned_instance, state)

        return assigned

    def create_from_assignable(self, service_pool: ServicePool, user: User, assignable_id: str) -> UserService:
        """
        Creates an assigned service from an "assignable" id
        """
        serviceInstance = service_pool.service.get_instance()
        if not serviceInstance.can_assign():
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
        state = serviceInstance.assign_from_assignables(assignable_id, user, assigned_userservice_instance)
        # assigned.u(assignedInstance)

        UserServiceOpChecker.make_unique(assigned, assigned_userservice_instance, state)

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
        UserServiceOpChecker.make_unique(cache, cache_instance, state)

    def cancel(self, user_service: UserService) -> None:
        """
        Cancels an user service creation
        @return: the Uservice canceling
        """
        user_service.refresh_from_db()

        if user_service.is_preparing() is False:
            logger.debug('Cancel requested for a non running operation, performing removal instead')
            return self.remove(user_service)

        operations_logger.info('Canceling userService %s', user_service.name)
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
        UserServiceOpChecker.make_unique(user_service, user_service_instance, state)

    def remove(self, userservice: UserService) -> None:
        """
        Removes a uService element
        """
        with transaction.atomic():
            userservice = UserService.objects.select_for_update().get(id=userservice.id)
            operations_logger.info('Removing userService %a', userservice.name)
            if userservice.is_usable() is False and State.from_str(userservice.state).is_removable() is False:
                raise OperationException(_('Can\'t remove a non active element'))
            userservice.set_state(State.REMOVING)
            logger.debug("***** The state now is %s *****", State.from_str(userservice.state).localized)
            userservice.set_in_use(False)  # For accounting, ensure that it is not in use right now
            userservice.save()

        userServiceInstance = userservice.get_instance()
        state = userServiceInstance.destroy()

        # Data will be serialized on makeUnique process
        UserServiceOpChecker.make_unique(userservice, userServiceInstance, state)

    def remove_or_cancel(self, user_service: UserService) -> None:
        if user_service.is_usable() or State.from_str(user_service.state).is_removable():
            return self.remove(user_service)

        if user_service.is_preparing():
            return self.cancel(user_service)

        raise OperationException(
            _('Can\'t remove nor cancel {} cause its state don\'t allow it').format(user_service.name)
        )

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
        self, service_pool: ServicePool, user: User
    ) -> typing.Optional[UserService]:  # pylint: disable=too-many-branches
        if service_pool.service.get_instance().spawns_new is False:
            assignedUserService = self.get_existing_assignation_for_user(service_pool, user)
        else:
            assignedUserService = None

        # If has an assigned user service, returns this without any more work
        if assignedUserService:
            return assignedUserService

        if service_pool.is_restrained():
            raise InvalidServiceException(_('The requested service is restrained'))

        cache: typing.Optional[UserService] = None
        # Now try to locate 1 from cache already "ready" (must be usable and at level 1)
        with transaction.atomic():
            caches = typing.cast(
                list[UserService],
                service_pool.cached_users_services()
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
                    service_pool.cached_users_services()
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
                    service_pool.cached_users_services()
                    .select_for_update()
                    .filter(cache_level=types.services.CacheLevel.L1, state=State.USABLE)[:1],
                )
                if caches:  # If there is a cache, we will use it
                    cache = caches[0]
                    if (
                        service_pool.cached_users_services()
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
                service_pool,
                user,
                cache,
            )
            events.add_event(
                service_pool,
                types.stats.EventType.CACHE_HIT,
                fld1=service_pool.cached_users_services()
                .filter(cache_level=types.services.CacheLevel.L1, state=State.USABLE)
                .count(),
            )
            return cache

        # Cache missed

        # Now find if there is a preparing one
        with transaction.atomic():
            caches = list(
                service_pool.cached_users_services()
                .select_for_update()
                .filter(cache_level=types.services.CacheLevel.L1, state=State.PREPARING)[:1]
            )
            if caches:  # If there is a cache, we will use it
                cache = caches[0]
                if (
                    service_pool.cached_users_services()
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
                service_pool,
                user,
                cache,
            )
            events.add_event(
                service_pool,
                events.types.stats.EventType.CACHE_MISS,
                fld1=service_pool.cached_users_services()
                .filter(cache_level=types.services.CacheLevel.L1, state=State.PREPARING)
                .count(),
            )
            return cache

        # Can't assign directly from L2 cache... so we check if we can create e new service in the limits requested
        serviceType = service_pool.service.get_type()
        if serviceType.uses_cache:
            inAssigned = (
                service_pool.assigned_user_services()
                .filter(self.get_state_filter(service_pool.service))
                .count()
            )
            if (
                inAssigned >= service_pool.max_srvs
            ):  # cacheUpdater will drop unnecesary L1 machines, so it's not neccesary to check against inCacheL1
                log.log(
                    service_pool,
                    types.log.LogLevel.WARNING,
                    f'Max number of services reached: {service_pool.max_srvs}',
                    types.log.LogSource.INTERNAL,
                )
                raise MaxServicesReachedError()

        # Can create new service, create it
        events.add_event(service_pool, events.types.stats.EventType.CACHE_MISS, fld1=0)
        return self.create_assigned_for(service_pool, user)

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

        logger.debug('Service %s is usable, checking it via setReady', user_service)
        userServiceInstance = user_service.get_instance()
        try:
            state = userServiceInstance.set_ready()
        except Exception as e:
            logger.warning('Could not check readyness of %s: %s', user_service, e)
            return False

        logger.debug('State: %s', state)

        if state == types.states.TaskState.FINISHED:
            user_service.update_data(userServiceInstance)
            return True

        user_service.set_state(State.PREPARING)
        UserServiceOpChecker.make_unique(user_service, userServiceInstance, state)

        return False

    def reset(self, user_service: UserService) -> None:
        user_service.refresh_from_db()

        if not user_service.deployed_service.service.get_type().can_reset:
            return

        operations_logger.info('Reseting %s', user_service)

        userservice_instance = user_service.get_instance()
        try:
            state = userservice_instance.reset()
        except Exception:
            logger.exception('Reseting service')
            return

        logger.debug('State: %s', state)

        if state == types.states.TaskState.FINISHED:
            user_service.update_data(userservice_instance)
            return

        UserServiceOpChecker.make_unique(user_service, userservice_instance, state)

    def notify_preconnect(self, user_service: UserService, info: types.connections.ConnectionData) -> None:
        try:
            comms.notify_preconnect(user_service, info)
        except exceptions.actor.NoActorComms:  # If no comms url for userService, try with service
            user_service.deployed_service.service.notify_preconnect(user_service, info)

    def check_user_service_uuid(self, user_service: UserService) -> bool:
        return comms.check_user_service_uuid(user_service)

    def request_screenshot(self, user_service: UserService) -> None:
        # Screenshot will request an screenshot to the actor
        # And the actor will return back, via REST actor API, the screenshot
        comms.request_screenshot(user_service)

    def send_script(self, user_service: UserService, script: str, forUser: bool = False) -> None:
        comms.send_script(user_service, script, forUser)

    def request_logoff(self, user_service: UserService) -> None:
        comms.request_logoff(user_service)

    def send_message(self, user_service: UserService, message: str) -> None:
        comms.send_message(user_service, message)

    def check_for_removal(self, user_service: UserService) -> None:
        """
        This method is used by UserService when a request for setInUse(False) is made
        This checks that the service can continue existing or not
        """
        osmanager = user_service.deployed_service.osmanager
        # If os manager says "machine is persistent", do not try to delete "previous version" assigned machines
        doPublicationCleanup = True if not osmanager else not osmanager.get_instance().is_persistent()

        if doPublicationCleanup:
            remove = False
            with transaction.atomic():
                user_service = UserService.objects.select_for_update().get(id=user_service.id)
                active_publication = user_service.deployed_service.active_publication()
                if (
                    user_service.publication
                    and active_publication
                    and user_service.publication.id != active_publication.id
                ):
                    logger.debug(
                        'Old revision of user service, marking as removable: %s',
                        user_service,
                    )
                    remove = True

            if remove:
                user_service.remove()

    def notify_ready_from_os_manager(self, user_service: UserService, data: typing.Any) -> None:
        try:
            userServiceInstance = user_service.get_instance()
            logger.debug('Notifying user service ready state')
            state = userServiceInstance.process_ready_from_os_manager(data)
            logger.debug('State: %s', state)
            if state == types.states.TaskState.FINISHED:
                user_service.update_data(userServiceInstance)
                logger.debug('Service is now ready')
            elif user_service.state in (
                State.USABLE,
                State.PREPARING,
            ):  # We don't want to get active deleting or deleted machines...
                user_service.set_state(State.PREPARING)
                # Make unique will make sure that we do not have same machine twice
                UserServiceOpChecker.make_unique(user_service, userServiceInstance, state)
            user_service.save(update_fields=['os_state'])
        except Exception as e:
            logger.exception('Unhandled exception on notyfyReady: %s', e)
            user_service.set_state(State.ERROR)
            return

    def locate_user_service(
        self, user: User, id_service: str, create: bool = False
    ) -> typing.Optional[UserService]:
        kind, uuid_user_service = id_service[0], id_service[1:]

        logger.debug('Kind of service: %s, idService: %s', kind, uuid_user_service)
        userservice: typing.Optional[UserService] = None

        if kind in 'A':  # This is an assigned service
            logger.debug('Getting A service %s', uuid_user_service)
            userservice = UserService.objects.get(uuid=uuid_user_service, user=user)
            userservice.deployed_service.validate_user(user)
        else:
            try:
                service_pool: ServicePool = ServicePool.objects.get(uuid=uuid_user_service)
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
        validate_with_test: bool = True,
        client_hostname: typing.Optional[str] = None,
    ) -> tuple[
        typing.Optional[str],
        UserService,
        typing.Optional['services.UserService'],
        Transport,
        typing.Optional[transports.Transport],
    ]:
        """
        Get service info from user service
        """
        if user_service_id[0] == 'M':  # Meta pool
            return self.get_meta_service_info(user, src_ip, os, user_service_id[1:], transport_id or 'meta')

        user_service = self.locate_user_service(user, user_service_id, create=True)

        if not user_service:
            raise InvalidServiceException(
                _('Invalid service. The service is not available at this moment. Please, try later')
            )

        # Early log of "access try" so we can imagine what is going on
        user_service.set_connection_source(
            types.connections.ConnectionSource(src_ip, client_hostname or src_ip)
        )

        if user_service.is_in_maintenance():
            raise ServiceInMaintenanceMode()

        if not user_service.deployed_service.is_access_allowed():
            raise ServiceAccessDeniedByCalendar()

        if not transport_id:  # Find a suitable transport
            t: Transport
            for t in user_service.deployed_service.transports.order_by('priority'):
                typeTrans = t.get_type()
                if (
                    typeTrans
                    and t.is_ip_allowed(src_ip)
                    and typeTrans.supports_os(os.os)
                    and t.is_os_allowed(os.os)
                ):
                    transport_id = t.uuid
                    break

        try:
            transport: Transport = Transport.objects.get(uuid=transport_id)
        except Exception as e:
            raise InvalidServiceException() from e

        # Ensures that the transport is allowed for this service
        if user_service.deployed_service.transports.filter(id=transport.id).count() == 0:
            raise InvalidServiceException()

        # If transport is not available for the request IP...
        if not transport.is_ip_allowed(src_ip):
            msg = _('The requested transport {} is not valid for {}').format(transport.name, src_ip)
            logger.error(msg)
            raise InvalidServiceException(msg)

        userName = user.name if user else 'unknown'

        if not validate_with_test:
            # traceLogger.info('GOT service "{}" for user "{}" with transport "{}" (NOT TESTED)'.format(userService.name, userName, trans.name))
            return None, user_service, None, transport, None

        service_status: types.services.ReadyStatus = types.services.ReadyStatus.USERSERVICE_NOT_READY
        ip = 'unknown'
        # Test if the service is ready
        if user_service.is_ready():
            # Is ready, update possible state
            service_status = types.services.ReadyStatus.USERSERVICE_NO_IP
            log.log(
                user_service,
                types.log.LogLevel.INFO,
                f"User {user.pretty_name} from {src_ip} has initiated access",
                types.log.LogSource.WEB,
            )
            # If ready, show transport for this service, if also ready ofc
            userServiceInstance = user_service.get_instance()
            ip = userServiceInstance.get_ip()
            user_service.log_ip(ip)  # Update known ip
            logger.debug('IP: %s', ip)

            if self.check_user_service_uuid(user_service) is False:  # The service is not the expected one
                service_status = types.services.ReadyStatus.USERSERVICE_INVALID_UUID
                log.log(
                    user_service,
                    types.log.LogLevel.WARNING,
                    f'User service is not accessible due to invalid UUID (user: {user.pretty_name}, ip: {ip})',
                    types.log.LogSource.TRANSPORT,
                )
                logger.debug('UUID check failed for user service %s', user_service)
            else:
                events.add_event(
                    user_service.deployed_service,
                    events.types.stats.EventType.ACCESS,
                    username=userName,
                    srcip=src_ip,
                    dstip=ip,
                    uniqueid=user_service.unique_id,
                )
                if ip:
                    service_status = types.services.ReadyStatus.TRANSPORT_NOT_READY
                    transportInstance = transport.get_instance()
                    if transportInstance.is_ip_allowed(user_service, ip):
                        log.log(
                            user_service, types.log.LogLevel.INFO, "User service ready", types.log.LogSource.WEB
                        )
                        self.notify_preconnect(
                            user_service,
                            transportInstance.get_connection_info(user_service, user, ''),
                        )
                        trace_logger.info(
                            'READY on service "%s" for user "%s" with transport "%s" (ip:%s)',
                            user_service.name,
                            userName,
                            transport.name,
                            ip,
                        )
                        return (
                            ip,
                            user_service,
                            userServiceInstance,
                            transport,
                            transportInstance,
                        )

                    message = transportInstance.get_available_error_msg(user_service, ip)
                    log.log(user_service, types.log.LogLevel.WARNING, message, types.log.LogSource.TRANSPORT)
                    logger.debug(
                        'Transport is not ready for user service %s: %s',
                        user_service,
                        message,
                    )
                else:
                    logger.debug('Ip not available from user service %s', user_service)
        else:
            log.log(
                user_service,
                types.log.LogLevel.WARNING,
                f'User {user.pretty_name} from {src_ip} tried to access, but service was not ready',
                types.log.LogSource.WEB,
            )

        trace_logger.error(
            'ERROR %s on service "%s" for user "%s" with transport "%s" (ip:%s)',
            service_status,
            user_service.name,
            userName,
            transport.name,
            ip,
        )
        raise ServiceNotReadyError(code=service_status, user_service=user_service, transport=transport)

    def is_meta_service(self, meta_id: str) -> bool:
        return meta_id[0] == 'M'

    def locate_meta_service(self, user: User, id_metapool: str) -> typing.Optional[UserService]:
        kind, uuid_metapool = id_metapool[0], id_metapool[1:]
        if kind != 'M':
            return None

        meta: MetaPool = MetaPool.objects.get(uuid=uuid_metapool)
        # Get pool members. Just pools "visible" and "usable"
        pools = [p.pool for p in meta.members.all() if p.pool.is_visible() and p.pool.is_usable()]
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
        srcIp: str,
        os: 'types.os.DetectedOsInfo',
        id_metapool: str,
        id_transport: str,
        clientHostName: typing.Optional[str] = None,
    ) -> tuple[
        typing.Optional[str],
        UserService,
        typing.Optional['services.UserService'],
        Transport,
        typing.Optional[transports.Transport],
    ]:
        logger.debug('This is meta')
        # We need to locate the service pool related to this meta, and also the transport
        # First, locate if there is a service in any pool associated with this metapool
        meta: MetaPool = MetaPool.objects.get(uuid=id_metapool)

        # If access is denied by calendar...
        if meta.is_access_allowed() is False:
            raise ServiceAccessDeniedByCalendar()

        # Get pool members. Just pools "visible" and "usable"
        poolMembers = [p for p in meta.members.all() if p.pool.is_visible() and p.pool.is_usable()]
        # Sort pools array. List of tuples with (priority, pool)
        sortPools: list[tuple[int, ServicePool]]
        # Sort pools based on meta selection
        if meta.policy == types.pools.LoadBalancingPolicy.PRIORITY:
            sortPools = [(p.priority, p.pool) for p in poolMembers]
        elif meta.policy == types.pools.LoadBalancingPolicy.GREATER_PERCENT_FREE:
            sortPools = [(p.pool.usage().percent, p.pool) for p in poolMembers]
        else:
            sortPools = [
                (
                    random.randint(
                        0, 10000
                    ),  # nosec: just a suffle, not a crypto (to get a round robin-like behavior)
                    p.pool,
                )
                for p in poolMembers
            ]  # Just shuffle them

        # Sort pools related to policy now, and xtract only pools, not sort keys
        # split resuult in two lists, 100% full and not 100% full
        # Remove "full" pools (100%) from result and pools in maintenance mode, not ready pools, etc...
        sortedPools = sorted(sortPools, key=operator.itemgetter(0))  # sort by priority (first element)
        pools: list[ServicePool] = []
        pool_full: list[ServicePool] = []
        for p in sortedPools:
            if not p[1].is_usable():
                continue
            if p[1].usage().percent == 100:
                pool_full.append(p[1])
            else:
                pools.append(p[1])

        logger.debug('Pools: %s/%s', pools, pool_full)

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
                typeTrans = t.get_type()
                if (
                    typeTrans
                    and t.get_type()
                    and t.is_ip_allowed(srcIp)
                    and typeTrans.supports_os(os.os)
                    and t.is_os_allowed(os.os)
                ):
                    found = (pool, t)
                    break
            return found

        try:
            # Already assigned should look for in all usable pools, not only "non-full" ones
            alreadyAssigned: UserService = UserService.objects.filter(
                deployed_service__in=pools + pool_full,
                state__in=State.VALID_STATES,
                user=user,
                cache_level=0,
            ).order_by('deployed_service__name')[0]
            logger.debug('Already assigned %s', alreadyAssigned)
            # If already assigned, and HA is enabled, check if it is accessible
            if meta.ha_policy == types.pools.HighAvailabilityPolicy.ENABLED:
                # Check that servide is accessible
                if (
                    not alreadyAssigned.deployed_service.service.get_instance().is_avaliable()
                ):  # Not available, mark for removal
                    alreadyAssigned.release()
                raise Exception()  # And process a new access

            # Ensure transport is available for the OS, and store it
            usable = _ensure_transport(alreadyAssigned.deployed_service)
            # Found already assigned, ensure everythinf is fine
            if usable:
                return self.get_user_service_info(
                    user,
                    os,
                    srcIp,
                    'F' + usable[0].uuid,
                    usable[1].uuid,
                    validate_with_test=False,
                    client_hostname=clientHostName,
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
                            srcIp,
                            'F' + usable[0].uuid,
                            usable[1].uuid,
                            validate_with_test=False,
                            client_hostname=clientHostName,
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
            f'No user service accessible from device (ip {srcIp}, os: {os.os.name})',
            types.log.LogSource.SERVICE,
        )
        raise InvalidServiceException(_('The service is not accessible from this device'))
