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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import operator
import random
import typing
import collections.abc

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
from uds.core.util.model import sql_datetime
from uds.core.util.state import State
from uds.core.util.stats import events
from uds.models import MetaPool, ServicePool, ServicePoolPublication, Transport, User, UserService

from .userservice import comms
from .userservice.opchecker import UserServiceOpChecker

if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')
operationsLogger = logging.getLogger('operationsLog')


class UserServiceManager(metaclass=singleton.Singleton):
    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'UserServiceManager':
        return UserServiceManager()  # Singleton pattern will return always the same instance

    def getCacheStateFilter(self, servicePool: ServicePool, level: int) -> Q:
        return Q(cache_level=level) & self.getStateFilter(servicePool.service)

    @staticmethod
    def getStateFilter(service: 'models.Service') -> Q:
        if service.oldMaxAccountingMethod:  # If no limits and accounting method is not old one
            # Valid states are: PREPARING, USABLE
            states = [State.PREPARING, State.USABLE]
        else:  # New accounting method selected
            states = [State.PREPARING, State.USABLE, State.REMOVING, State.REMOVABLE]
        return Q(state__in=states)

    def _checkMaxUserServicesReached(self, servicePool: ServicePool) -> None:
        """
        Checks if maxUserServices for the service has been reached, and, if so,
        raises an exception that no more services of this kind can be reached
        """
        if self.maximumUserServicesDeployed(servicePool.service):
            raise MaxServicesReachedError(
                _('Maximum number of user services reached for this {}').format(servicePool)
            )

    def getExistingUserServices(self, service: 'models.Service') -> int:
        """
        Returns the number of running user services for this service
        """
        return UserService.objects.filter(
            self.getStateFilter(service) & Q(deployed_service__service=service)
        ).count()

    def maximumUserServicesDeployed(self, service: 'models.Service') -> bool:
        """
        Checks if the maximum number of user services for this service has been reached
        """
        serviceInstance = service.get_instance()
        # Early return, so no database count is needed
        if serviceInstance.maxUserServices == consts.UNLIMITED:
            return False

        if self.getExistingUserServices(service) >= serviceInstance.maxUserServices:
            return True

        return False

    def _createCacheAtDb(self, publication: ServicePoolPublication, cacheLevel: int) -> UserService:
        """
        Private method to instatiate a cache element at database with default states
        """
        # Checks if maxUserServices has been reached and if so, raises an exception
        self._checkMaxUserServicesReached(publication.deployed_service)
        now = sql_datetime()
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

    def _createAssignedAtDb(self, publication: ServicePoolPublication, user: User) -> UserService:
        """
        Private method to instatiate an assigned element at database with default state
        """
        self._checkMaxUserServicesReached(publication.deployed_service)
        now = sql_datetime()
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

    def _createAssignedAtDbForNoPublication(self, servicePool: ServicePool, user: User) -> UserService:
        """
        __createCacheAtDb and __createAssignedAtDb uses a publication for create the UserService.
        There is cases where deployed services do not have publications (do not need them), so we need this method to create
        an UserService with no publications, and create them from an ServicePool
        """
        self._checkMaxUserServicesReached(servicePool)
        now = sql_datetime()
        return servicePool.userServices.create(
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

    def createCacheFor(self, publication: ServicePoolPublication, cacheLevel: int) -> UserService:
        """
        Creates a new cache for the deployed service publication at level indicated
        """
        operationsLogger.info(
            'Creating a new cache element at level %s for publication %s',
            cacheLevel,
            publication,
        )
        cache = self._createCacheAtDb(publication, cacheLevel)
        ci = cache.get_instance()
        state = ci.deployForCache(cacheLevel)

        UserServiceOpChecker.checkAndUpdateState(cache, ci, state)
        return cache

    def createAssignedFor(self, servicePool: ServicePool, user: User) -> UserService:
        """
        Creates a new assigned deployed service for the current publication (if any) of service pool and user indicated
        """
        # First, honor maxPreparingServices
        if self.canGrowServicePool(servicePool) is False:
            # Cannot create new
            operationsLogger.info(
                'Too many preparing services. Creation of assigned service denied by max preparing services parameter. (login storm with insufficient cache?).'
            )
            raise ServiceNotReadyError()

        if servicePool.service.get_type().publicationType is not None:
            publication = servicePool.activePublication()
            if publication:
                assigned = self._createAssignedAtDb(publication, user)
                operationsLogger.info(
                    'Creating a new assigned element for user %s for publication %s on pool %s',
                    user.pretty_name,
                    publication.revision,
                    servicePool.name,
                )
            else:
                raise Exception(
                    f'Invalid publication creating service assignation: {servicePool.name} {user.pretty_name}'
                )
        else:
            operationsLogger.info(
                'Creating a new assigned element for user %s on pool %s',
                user.pretty_name,
                servicePool.name,
            )
            assigned = self._createAssignedAtDbForNoPublication(servicePool, user)

        assignedInstance = assigned.get_instance()
        state = assignedInstance.deployForUser(user)

        UserServiceOpChecker.makeUnique(assigned, assignedInstance, state)

        return assigned

    def createFromAssignable(self, servicePool: ServicePool, user: User, assignableId: str) -> UserService:
        """
        Creates an assigned service from an "assignable" id
        """
        serviceInstance = servicePool.service.get_instance()
        if not serviceInstance.canAssign():
            raise Exception('This service type cannot assign asignables')

        if servicePool.service.get_type().publicationType is not None:
            publication = servicePool.activePublication()
            if publication:
                assigned = self._createAssignedAtDb(publication, user)
                operationsLogger.info(
                    'Creating an assigned element from assignable %s for user %s for publication %s on pool %s',
                    assignableId,
                    user.pretty_name,
                    publication.revision,
                    servicePool.name,
                )
            else:
                raise Exception(
                    f'Invalid publication creating service assignation: {servicePool.name} {user.pretty_name}'
                )
        else:
            operationsLogger.info(
                'Creating an assigned element from assignable %s for user %s on pool %s',
                assignableId,
                user.pretty_name,
                servicePool.name,
            )
            assigned = self._createAssignedAtDbForNoPublication(servicePool, user)

        # Now, get from serviceInstance the data
        assignedInstance = assigned.get_instance()
        state = serviceInstance.assignFromAssignables(assignableId, user, assignedInstance)
        # assigned.updateData(assignedInstance)

        UserServiceOpChecker.makeUnique(assigned, assignedInstance, state)

        return assigned

    def moveToLevel(self, cache: UserService, cacheLevel: int) -> None:
        """
        Moves a cache element from one level to another
        @return: cache element
        """
        cache.refresh_from_db()
        logger.debug('Moving cache %s to level %s', cache, cacheLevel)
        cacheInstance = cache.get_instance()
        state = cacheInstance.moveToCache(cacheLevel)
        cache.cache_level = cacheLevel
        cache.save(update_fields=['cache_level'])
        logger.debug(
            'Service State: %a %s %s',
            State.toString(state),
            State.toString(cache.state),
            State.toString(cache.os_state),
        )
        if State.isRuning(state) and cache.isUsable():
            cache.setState(State.PREPARING)

        # Data will be serialized on makeUnique process
        UserServiceOpChecker.makeUnique(cache, cacheInstance, state)

    def cancel(self, userService: UserService) -> UserService:
        """
        Cancels an user service creation
        @return: the Uservice canceling
        """
        userService.refresh_from_db()

        if userService.isPreparing() is False:
            logger.debug('Cancel requested for a non running operation, performing removal instead')
            return self.remove(userService)

        operationsLogger.info('Canceling userService %s', userService.name)
        userServiceInstance = userService.get_instance()

        if (
            not userServiceInstance.supportsCancel()
        ):  # Does not supports cancel, but destroy, so mark it for "later" destroy
            # State is kept, just mark it for destroy after finished preparing
            userService.destroy_after = True
        else:
            userService.setState(State.CANCELING)
            # We simply notify service that it should cancel operation
            state = userServiceInstance.cancel()

            # Data will be serialized on makeUnique process
            # If cancel is not supported, base cancel always returns "FINISHED", and
            # opchecker will set state to "removable"
            UserServiceOpChecker.makeUnique(userService, userServiceInstance, state)

        return userService

    def remove(self, userService: UserService) -> UserService:
        """
        Removes a uService element
        """
        with transaction.atomic():
            userService = UserService.objects.select_for_update().get(id=userService.id)
            operationsLogger.info('Removing userService %a', userService.name)
            if userService.isUsable() is False and State.isRemovable(userService.state) is False:
                raise OperationException(_('Can\'t remove a non active element'))
            userService.setState(State.REMOVING)
            logger.debug("***** The state now is %s *****", State.toString(userService.state))
            userService.setInUse(False)  # For accounting, ensure that it is not in use right now
            userService.save()

        userServiceInstance = userService.get_instance()
        state = userServiceInstance.destroy()

        # Data will be serialized on makeUnique process
        UserServiceOpChecker.makeUnique(userService, userServiceInstance, state)

        return userService

    def removeOrCancel(self, userService: UserService):
        if userService.isUsable() or State.isRemovable(userService.state):
            return self.remove(userService)

        if userService.isPreparing():
            return self.cancel(userService)

        raise OperationException(
            _('Can\'t remove nor cancel {} cause its state don\'t allow it').format(userService.name)
        )

    def getExistingAssignationForUser(
        self, servicePool: ServicePool, user: User
    ) -> typing.Optional[UserService]:
        existing = servicePool.assignedUserServices().filter(
            user=user, state__in=State.VALID_STATES
        )  # , deployed_service__visible=True
        if existing.exists():
            logger.debug('Found assigned service from %s to user %s', servicePool, user.name)
            return existing.first()
        return None

    def getAssignationForUser(
        self, servicePool: ServicePool, user: User
    ) -> typing.Optional[UserService]:  # pylint: disable=too-many-branches
        if servicePool.service.get_instance().spawnsNew is False:
            assignedUserService = self.getExistingAssignationForUser(servicePool, user)
        else:
            assignedUserService = None

        # If has an assigned user service, returns this without any more work
        if assignedUserService:
            return assignedUserService

        if servicePool.isRestrained():
            raise InvalidServiceException(_('The requested service is restrained'))

        cache: typing.Optional[UserService] = None
        # Now try to locate 1 from cache already "ready" (must be usable and at level 1)
        with transaction.atomic():
            caches = typing.cast(
                list[UserService],
                servicePool.cachedUserServices()
                .select_for_update()
                .filter(
                    cache_level=services.UserService.L1_CACHE,
                    state=State.USABLE,
                    os_state=State.USABLE,
                )[
                    :1  # type: ignore  # Slicing is not supported by pylance right now
                ],
            )
            if caches:
                cache = caches[0]
                # Ensure element is reserved correctly on DB
                if (
                    servicePool.cachedUserServices()
                    .select_for_update()
                    .filter(user=None, uuid=typing.cast(UserService, cache).uuid)
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
                    servicePool.cachedUserServices()
                    .select_for_update()
                    .filter(cache_level=services.UserService.L1_CACHE, state=State.USABLE)[
                        :1  # type: ignore  # Slicing is not supported by pylance right now
                    ],
                )
                if cache:
                    cache = caches[0]
                    if (
                        servicePool.cachedUserServices()
                        .select_for_update()
                        .filter(user=None, uuid=typing.cast(UserService, cache).uuid)
                        .update(user=user, cache_level=0)
                        != 1
                    ):
                        cache = None
                else:
                    cache = None

        # Out of atomic transaction
        if cache:
            # Early assign
            cache.assignToUser(user)

            logger.debug(
                'Found a cached-ready service from %s for user %s, item %s',
                servicePool,
                user,
                cache,
            )
            events.addEvent(
                servicePool,
                events.ET_CACHE_HIT,
                fld1=servicePool.cachedUserServices()
                .filter(cache_level=services.UserService.L1_CACHE, state=State.USABLE)
                .count(),
            )
            return cache

        # Cache missed

        # Now find if there is a preparing one
        with transaction.atomic():
            caches = (
                servicePool.cachedUserServices()
                .select_for_update()
                .filter(cache_level=services.UserService.L1_CACHE, state=State.PREPARING)[
                    :1  # type: ignore  # Slicing is not supported by pylance right now
                ]
            )
            if caches:
                cache = caches[0]  # type: ignore  # Slicing is not supported by pylance right now
                if (
                    servicePool.cachedUserServices()
                    .select_for_update()
                    .filter(user=None, uuid=typing.cast(UserService, cache).uuid)
                    .update(user=user, cache_level=0)
                    != 1
                ):
                    cache = None
            else:
                cache = None

        # Out of atomic transaction
        if cache:
            cache.assignToUser(user)

            logger.debug(
                'Found a cached-preparing service from %s for user %s, item %s',
                servicePool,
                user,
                cache,
            )
            events.addEvent(
                servicePool,
                events.ET_CACHE_MISS,
                fld1=servicePool.cachedUserServices()
                .filter(cache_level=services.UserService.L1_CACHE, state=State.PREPARING)
                .count(),
            )
            return cache

        # Can't assign directly from L2 cache... so we check if we can create e new service in the limits requested
        serviceType = servicePool.service.get_type()
        if serviceType.usesCache:
            inAssigned = (
                servicePool.assignedUserServices().filter(self.getStateFilter(servicePool.service)).count()
            )
            if (
                inAssigned >= servicePool.max_srvs
            ):  # cacheUpdater will drop unnecesary L1 machines, so it's not neccesary to check against inCacheL1
                log.doLog(
                    servicePool,
                    log.LogLevel.WARNING,
                    f'Max number of services reached: {servicePool.max_srvs}',
                    log.LogSource.INTERNAL,
                )
                raise MaxServicesReachedError()

        # Can create new service, create it
        events.addEvent(servicePool, events.ET_CACHE_MISS, fld1=0)
        return self.createAssignedFor(servicePool, user)

    def getUserServicesInStatesForProvider(self, provider: 'models.Provider', states: list[str]) -> int:
        """
        Returns the number of services of a service provider in the state indicated
        """
        return UserService.objects.filter(
            deployed_service__service__provider=provider, state__in=states
        ).count()

    def canRemoveServiceFromDeployedService(self, servicePool: ServicePool) -> bool:
        """
        checks if we can do a "remove" from a deployed service
        serviceIsntance is just a helper, so if we already have deserialized deployedService
        """
        removing = self.getUserServicesInStatesForProvider(servicePool.service.provider, [State.REMOVING])
        serviceInstance = servicePool.service.get_instance()
        if (
            serviceInstance.isAvailable()
            and removing >= serviceInstance.parent().getMaxRemovingServices()
            and serviceInstance.parent().getIgnoreLimits() is False
        ):
            return False
        return True

    def canGrowServicePool(self, servicePool: ServicePool) -> bool:
        """
        Checks if we can start a new service
        """
        preparingForProvider = self.getUserServicesInStatesForProvider(
            servicePool.service.provider, [State.PREPARING]
        )
        serviceInstance = servicePool.service.get_instance()
        if self.maximumUserServicesDeployed(servicePool.service) or (
            preparingForProvider >= serviceInstance.parent().getMaxPreparingServices()
            and serviceInstance.parent().getIgnoreLimits() is False
        ):
            return False
        return True

    def isReady(self, userService: UserService) -> bool:
        userService.refresh_from_db()
        logger.debug('Checking ready of %s', userService)

        if userService.state != State.USABLE or userService.os_state != State.USABLE:
            logger.debug('State is not usable for %s', userService.name)
            return False

        logger.debug('Service %s is usable, checking it via setReady', userService)
        userServiceInstance = userService.get_instance()
        try:
            state = userServiceInstance.setReady()
        except Exception as e:
            logger.warning('Could not check readyness of %s: %s', userService, e)
            return False

        logger.debug('State: %s', state)

        if state == State.FINISHED:
            userService.updateData(userServiceInstance)
            return True

        userService.setState(State.PREPARING)
        UserServiceOpChecker.makeUnique(userService, userServiceInstance, state)

        return False

    def reset(self, userService: UserService) -> None:
        userService.refresh_from_db()

        if not userService.deployed_service.service.get_type().canReset:
            return

        operationsLogger.info('Reseting %s', userService)

        userServiceInstance = userService.get_instance()
        try:
            userServiceInstance.reset()
        except Exception:
            logger.exception('Reseting service')

    def notifyPreconnect(self, userService: UserService, info: types.connections.ConnectionData) -> None:
        try:
            comms.notifyPreconnect(userService, info)
        except exceptions.actor.NoActorComms:  # If no comms url for userService, try with service
            userService.deployed_service.service.notifyPreconnect(userService, info)

    def checkUuid(self, userService: UserService) -> bool:
        return comms.checkUuid(userService)

    def requestScreenshot(self, userService: UserService) -> None:
        # Screenshot will request an screenshot to the actor
        # And the actor will return back, via REST actor API, the screenshot
        comms.requestScreenshot(userService)

    def sendScript(self, userService: UserService, script: str, forUser: bool = False) -> None:
        comms.sendScript(userService, script, forUser)

    def requestLogoff(self, userService: UserService) -> None:
        comms.requestLogoff(userService)

    def sendMessage(self, userService: UserService, message: str) -> None:
        comms.sendMessage(userService, message)

    def checkForRemoval(self, userService: UserService) -> None:
        """
        This method is used by UserService when a request for setInUse(False) is made
        This checks that the service can continue existing or not
        """
        osManager = userService.deployed_service.osmanager
        # If os manager says "machine is persistent", do not try to delete "previous version" assigned machines
        doPublicationCleanup = True if not osManager else not osManager.get_instance().isPersistent()

        if doPublicationCleanup:
            remove = False
            with transaction.atomic():
                userService = UserService.objects.select_for_update().get(id=userService.id)
                activePublication = userService.deployed_service.activePublication()
                if (
                    userService.publication
                    and activePublication
                    and userService.publication.id != activePublication.id
                ):
                    logger.debug(
                        'Old revision of user service, marking as removable: %s',
                        userService,
                    )
                    remove = True

            if remove:
                userService.remove()

    def notifyReadyFromOsManager(self, userService: UserService, data: typing.Any) -> None:
        try:
            userServiceInstance = userService.get_instance()
            logger.debug('Notifying user service ready state')
            state = userServiceInstance.notifyReadyFromOsManager(data)
            logger.debug('State: %s', state)
            if state == State.FINISHED:
                userService.updateData(userServiceInstance)
                logger.debug('Service is now ready')
            elif userService.state in (
                State.USABLE,
                State.PREPARING,
            ):  # We don't want to get active deleting or deleted machines...
                userService.setState(State.PREPARING)
                UserServiceOpChecker.makeUnique(userService, userServiceInstance, state)
            userService.save(update_fields=['os_state'])
        except Exception as e:
            logger.exception('Unhandled exception on notyfyReady: %s', e)
            userService.setState(State.ERROR)
            return

    def locateUserService(
        self, user: User, idService: str, create: bool = False
    ) -> typing.Optional[UserService]:
        kind, uuidService = idService[0], idService[1:]

        logger.debug('Kind of service: %s, idService: %s', kind, uuidService)
        userService: typing.Optional[UserService] = None

        if kind in 'A':  # This is an assigned service
            logger.debug('Getting A service %s', uuidService)
            userService = UserService.objects.get(uuid=uuidService, user=user)
            typing.cast(UserService, userService).deployed_service.validateUser(user)
        else:
            try:
                servicePool: ServicePool = ServicePool.objects.get(uuid=uuidService)
                # We first do a sanity check for this, if the user has access to this service
                # If it fails, will raise an exception
                servicePool.validateUser(user)

                # Now we have to locate an instance of the service, so we can assign it to user.
                if create:  # getAssignation, if no assignation is found, tries to create one
                    userService = self.getAssignationForUser(servicePool, user)
                else:  # Sometimes maybe we only need to locate the existint user service
                    userService = self.getExistingAssignationForUser(servicePool, user)
            except ServicePool.DoesNotExist:
                logger.debug('Service pool does not exist')
                return None

        logger.debug('Found service: %s', userService)

        if userService and userService.state == State.ERROR:
            return None

        return userService

    def getService(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        self,
        user: User,
        os: 'types.os.DetectedOsInfo',
        srcIp: str,
        idService: str,
        idTransport: typing.Optional[str],
        doTest: bool = True,
        clientHostname: typing.Optional[str] = None,
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
        if idService[0] == 'M':  # Meta pool
            return self.getMeta(user, srcIp, os, idService[1:], idTransport or '')

        userService = self.locateUserService(user, idService, create=True)

        if not userService:
            raise InvalidServiceException(
                _('Invalid service. The service is not available at this moment. Please, try later')
            )

        # Early log of "access try" so we can imagine what is going on
        userService.setConnectionSource(types.connections.ConnectionSource(srcIp, clientHostname or srcIp))

        if userService.isInMaintenance():
            raise ServiceInMaintenanceMode()

        if not userService.deployed_service.isAccessAllowed():
            raise ServiceAccessDeniedByCalendar()

        if not idTransport:  # Find a suitable transport
            t: Transport
            for t in userService.deployed_service.transports.order_by('priority'):
                typeTrans = t.get_type()
                if (
                    typeTrans
                    and t.is_ip_allowed(srcIp)
                    and typeTrans.supportsOs(os.os)
                    and t.is_os_allowed(os.os)
                ):
                    idTransport = t.uuid
                    break

        try:
            transport: Transport = Transport.objects.get(uuid=idTransport)
        except Exception as e:
            raise InvalidServiceException() from e

        # Ensures that the transport is allowed for this service
        if userService.deployed_service.transports.filter(id=transport.id).count() == 0:
            raise InvalidServiceException()

        # If transport is not available for the request IP...
        if not transport.is_ip_allowed(srcIp):
            msg = _('The requested transport {} is not valid for {}').format(transport.name, srcIp)
            logger.error(msg)
            raise InvalidServiceException(msg)

        userName = user.name if user else 'unknown'

        if not doTest:
            # traceLogger.info('GOT service "{}" for user "{}" with transport "{}" (NOT TESTED)'.format(userService.name, userName, trans.name))
            return None, userService, None, transport, None

        serviceNotReadyCode = 0x0001
        ip = 'unknown'
        # Test if the service is ready
        if userService.isReady():
            serviceNotReadyCode = 0x0002
            log.doLog(
                userService,
                log.LogLevel.INFO,
                f"User {user.pretty_name} from {srcIp} has initiated access",
                log.LogSource.WEB,
            )
            # If ready, show transport for this service, if also ready ofc
            userServiceInstance = userService.get_instance()
            ip = userServiceInstance.getIp()
            userService.logIP(ip)  # Update known ip
            logger.debug('IP: %s', ip)

            if self.checkUuid(userService) is False:  # The service is not the expected one
                serviceNotReadyCode = 0x0004
                log.doLog(
                    userService,
                    log.LogLevel.WARNING,
                    f'User service is not accessible due to invalid UUID (user: {user.pretty_name}, ip: {ip})',
                    log.LogSource.TRANSPORT,
                )
                logger.debug('UUID check failed for user service %s', userService)
            else:
                events.addEvent(
                    userService.deployed_service,
                    events.ET_ACCESS,
                    username=userName,
                    srcip=srcIp,
                    dstip=ip,
                    uniqueid=userService.unique_id,
                )
                if ip:
                    serviceNotReadyCode = 0x0003
                    transportInstance = transport.get_instance()
                    if transportInstance.isAvailableFor(userService, ip):
                        log.doLog(userService, log.LogLevel.INFO, "User service ready", log.LogSource.WEB)
                        self.notifyPreconnect(
                            userService,
                            transportInstance.getConnectionInfo(userService, user, ''),
                        )
                        traceLogger.info(
                            'READY on service "%s" for user "%s" with transport "%s" (ip:%s)',
                            userService.name,
                            userName,
                            transport.name,
                            ip,
                        )
                        return (
                            ip,
                            userService,
                            userServiceInstance,
                            transport,
                            transportInstance,
                        )

                    message = transportInstance.getCustomAvailableErrorMsg(userService, ip)
                    log.doLog(userService, log.LogLevel.WARNING, message, log.LogSource.TRANSPORT)
                    logger.debug(
                        'Transport is not ready for user service %s: %s',
                        userService,
                        message,
                    )
                else:
                    logger.debug('Ip not available from user service %s', userService)
        else:
            log.doLog(
                userService,
                log.LogLevel.WARNING,
                f'User {user.pretty_name} from {srcIp} tried to access, but service was not ready',
                log.LogSource.WEB,
            )

        traceLogger.error(
            'ERROR %s on service "%s" for user "%s" with transport "%s" (ip:%s)',
            serviceNotReadyCode,
            userService.name,
            userName,
            transport.name,
            ip,
        )
        raise ServiceNotReadyError(code=serviceNotReadyCode, userService=userService, transport=transport)

    def isMetaService(self, metaId: str) -> bool:
        return metaId[0] == 'M'

    def locateMetaService(self, user: User, idService: str) -> typing.Optional[UserService]:
        kind, uuidMetapool = idService[0], idService[1:]
        if kind != 'M':
            return None

        meta: MetaPool = MetaPool.objects.get(uuid=uuidMetapool)
        # Get pool members. Just pools "visible" and "usable"
        pools = [p.pool for p in meta.members.all() if p.pool.isVisible() and p.pool.isUsable()]
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

    def getMeta(
        self,
        user: User,
        srcIp: str,
        os: 'types.os.DetectedOsInfo',
        idMetaPool: str,
        idTransport: str,
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
        meta: MetaPool = MetaPool.objects.get(uuid=idMetaPool)

        # If access is denied by calendar...
        if meta.isAccessAllowed() is False:
            raise ServiceAccessDeniedByCalendar()

        # Get pool members. Just pools "visible" and "usable"
        poolMembers = [p for p in meta.members.all() if p.pool.isVisible() and p.pool.isUsable()]
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
        poolsFull: list[ServicePool] = []
        for p in sortedPools:
            if not p[1].isUsable():
                continue
            if p[1].usage().percent == 100:
                poolsFull.append(p[1])
            else:
                pools.append(p[1])

        logger.debug('Pools: %s/%s', pools, poolsFull)

        usable: typing.Optional[tuple[ServicePool, Transport]] = None
        # Now, Lets find first if there is one assigned in ANY pool

        def ensureTransport(
            pool: ServicePool,
        ) -> typing.Optional[tuple[ServicePool, Transport]]:
            found = None
            t: Transport
            if idTransport == 'meta':  # Autoselected:
                q = pool.transports.all()
            elif idTransport[:6] == 'LABEL:':
                q = pool.transports.filter(label=idTransport[6:])
            else:
                q = pool.transports.filter(uuid=idTransport)
            for t in q.order_by('priority'):
                typeTrans = t.get_type()
                if (
                    typeTrans
                    and t.get_type()
                    and t.is_ip_allowed(srcIp)
                    and typeTrans.supportsOs(os.os)
                    and t.is_os_allowed(os.os)
                ):
                    found = (pool, t)
                    break
            return found

        try:
            # Already assigned should look for in all usable pools, not only "non-full" ones
            alreadyAssigned: UserService = UserService.objects.filter(
                deployed_service__in=pools + poolsFull,
                state__in=State.VALID_STATES,
                user=user,
                cache_level=0,
            ).order_by('deployed_service__name')[
                0  # type: ignore  # Slicing is not supported by pylance right now
            ]
            logger.debug('Already assigned %s', alreadyAssigned)
            # If already assigned, and HA is enabled, check if it is accessible
            if meta.ha_policy == types.pools.HighAvailabilityPolicy.ENABLED:
                # Check that servide is accessible
                if (
                    not alreadyAssigned.deployed_service.service.get_instance().isAvailable()
                ):  # Not available, mark for removal
                    alreadyAssigned.release()
                raise Exception()  # And process a new access

            # Ensure transport is available for the OS, and store it
            usable = ensureTransport(alreadyAssigned.deployed_service)
            # Found already assigned, ensure everythinf is fine
            if usable:
                return self.getService(
                    user,
                    os,
                    srcIp,
                    'F' + usable[0].uuid,
                    usable[1].uuid,
                    doTest=False,
                    clientHostname=clientHostName,
                )
            # Not usable, will notify that it is not accessible

        except Exception:  # No service already assigned, lets find a suitable one
            for pool in pools:  # Pools are already sorted, and "full" pools are filtered out
                if meta.ha_policy == types.pools.HighAvailabilityPolicy.ENABLED:
                    # If not available, skip it
                    if pool.service.get_instance().isAvailable() is False:
                        continue

                # Ensure transport is available for the OS
                usable = ensureTransport(pool)

                # Stop if a pool-transport is found and can be assigned to user
                if usable:
                    try:
                        usable[0].validateUser(user)
                        return self.getService(
                            user,
                            os,
                            srcIp,
                            'F' + usable[0].uuid,
                            usable[1].uuid,
                            doTest=False,
                            clientHostname=clientHostName,
                        )
                    except Exception as e:
                        logger.info(
                            'Meta service %s:%s could not be assigned, trying a new one',
                            usable[0].name,
                            e,
                        )
                        usable = None

        log.doLog(
            meta,
            log.LogLevel.WARNING,
            f'No user service accessible from device (ip {srcIp}, os: {os.os.name})',
            log.LogSource.SERVICE,
        )
        raise InvalidServiceException(_('The service is not accessible from this device'))
