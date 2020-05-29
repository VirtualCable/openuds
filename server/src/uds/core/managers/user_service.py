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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import random
import typing

from django.utils.translation import ugettext as _
from django.db.models import Q
from django.db import transaction
from uds.core.services.exceptions import OperationException
from uds.core.util.state import State
from uds.core.util import log
from uds.core.services.exceptions import (
    MaxServicesReachedError,
    ServiceInMaintenanceMode,
    InvalidServiceException,
    ServiceNotReadyError,
    ServiceAccessDeniedByCalendar
)
from uds.models import MetaPool, ServicePool, UserService, getSqlDatetime, Transport, User, ServicePoolPublication
from uds.core import services, transports
from uds.core.util.stats import events

from .userservice import comms
from .userservice.opchecker  import UserServiceOpChecker

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')

class UserServiceManager:
    _manager: typing.Optional['UserServiceManager'] = None

    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'UserServiceManager':
        if not UserServiceManager._manager:
            UserServiceManager._manager = UserServiceManager()
        return UserServiceManager._manager

    @staticmethod
    def getCacheStateFilter(level: int) -> Q:
        return Q(cache_level=level) & UserServiceManager.getStateFilter()

    @staticmethod
    def getStateFilter() -> Q:
        return Q(state__in=[State.PREPARING, State.USABLE])

    def __checkMaxDeployedReached(self, servicePool: ServicePool) -> None:
        """
        Checks if maxDeployed for the service has been reached, and, if so,
        raises an exception that no more services of this kind can be reached
        """
        serviceInstance = servicePool.service.getInstance()
        # Early return, so no database count is needed
        if serviceInstance.maxDeployed == services.Service.UNLIMITED:
            return

        numberOfServices = servicePool.userServices.filter(state__in=[State.PREPARING, State.USABLE]).count()

        if serviceInstance.maxDeployed <= numberOfServices:
            raise MaxServicesReachedError('Max number of allowed deployments for service reached')

    def __createCacheAtDb(self, publication: ServicePoolPublication, cacheLevel: int) -> UserService:
        """
        Private method to instatiate a cache element at database with default states
        """
        # Checks if maxDeployed has been reached and if so, raises an exception
        self.__checkMaxDeployedReached(publication.deployed_service)
        now = getSqlDatetime()
        return publication.userServices.create(
            cache_level=cacheLevel,
            state=State.PREPARING,
            os_state=State.PREPARING,
            state_date=now,
            creation_date=now,
            data='',
            deployed_service=publication.deployed_service,
            user=None,
            in_use=False
        )

    def __createAssignedAtDb(self, publication: ServicePoolPublication, user: User) -> UserService:
        """
        Private method to instatiate an assigned element at database with default state
        """
        self.__checkMaxDeployedReached(publication.deployed_service)
        now = getSqlDatetime()
        return publication.userServices.create(
            cache_level=0,
            state=State.PREPARING,
            os_state=State.PREPARING,
            state_date=now,
            creation_date=now,
            data='',
            deployed_service=publication.deployed_service,
            user=user,
            in_use=False
        )

    def __createAssignedAtDbForNoPublication(self, servicePool: ServicePool, user: User) -> UserService:
        """
        __createCacheAtDb and __createAssignedAtDb uses a publication for create the UserService.
        There is cases where deployed services do not have publications (do not need them), so we need this method to create
        an UserService with no publications, and create them from an ServicePool
        """
        self.__checkMaxDeployedReached(servicePool)
        now = getSqlDatetime()
        return servicePool.userServices.create(
            cache_level=0,
            state=State.PREPARING,
            os_state=State.PREPARING,
            state_date=now,
            creation_date=now,
            data='',
            publication=None,
            user=user,
            in_use=False
        )

    def createCacheFor(self, publication: ServicePoolPublication, cacheLevel: int) -> UserService:
        """
        Creates a new cache for the deployed service publication at level indicated
        """
        logger.debug('Creating a new cache element at level %s for publication %s', cacheLevel, publication)
        cache = self.__createCacheAtDb(publication, cacheLevel)
        ci = cache.getInstance()
        state = ci.deployForCache(cacheLevel)

        UserServiceOpChecker.checkAndUpdateState(cache, ci, state)
        return cache

    def createAssignedFor(self, servicePool: ServicePool, user: User) -> UserService:
        """
        Creates a new assigned deployed service for the current publication (if any) of service pool and user indicated
        """
        # First, honor maxPreparingServices
        if self.canInitiateServiceFromDeployedService(servicePool) is False:
            # Cannot create new
            logger.info('Too many preparing services. Creation of assigned service denied by max preparing services parameter. (login storm with insufficient cache?).')
            raise ServiceNotReadyError()

        if servicePool.service.getType().publicationType is not None:
            publication = servicePool.activePublication()
            logger.debug('Creating a new assigned element for user %s por publication %s', user, publication)
            if publication:
                assigned = self.__createAssignedAtDb(publication, user)
            else:
                raise Exception('Invalid publication creating service assignation: {} {}'.format(servicePool, user))
        else:
            logger.debug('Creating a new assigned element for user %s', user)
            assigned = self.__createAssignedAtDbForNoPublication(servicePool, user)

        assignedInstance = assigned.getInstance()
        state = assignedInstance.deployForUser(user)

        UserServiceOpChecker.makeUnique(assigned, assignedInstance, state)

        return assigned

    def createFromAssignable(self, servicePool: ServicePool, user: User, assignableId: str) -> UserService:
        """
        Creates an assigned service from an "assignable" id
        """
        serviceInstance = servicePool.service.getInstance()
        if not serviceInstance.canAssign():
            raise Exception('This service type cannot assign asignables')

        if servicePool.service.getType().publicationType is not None:
            publication = servicePool.activePublication()
            logger.debug('Creating an assigned element from assignable %s for user %s por publication %s', user, assignableId, publication)
            if publication:
                assigned = self.__createAssignedAtDb(publication, user)
            else:
                raise Exception('Invalid publication creating service assignation: {} {}'.format(servicePool, user))
        else:
            logger.debug('Creating an assigned element from assignable %s for user %s', assignableId, user)
            assigned = self.__createAssignedAtDbForNoPublication(servicePool, user)

        # Now, get from serviceInstance the data
        assignedInstance = assigned.getInstance()
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
        cacheInstance = cache.getInstance()
        state = cacheInstance.moveToCache(cacheLevel)
        cache.cache_level = cacheLevel
        cache.save(update_fields=['cache_level'])
        logger.debug('Service State: %a %s %s', State.toString(state), State.toString(cache.state), State.toString(cache.os_state))
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
        logger.debug('Canceling userService %s creation', userService)

        if userService.isPreparing() is False:
            logger.info('Cancel requested for a non running operation, performing removal instead')
            return self.remove(userService)

        userServiceInstance = userService.getInstance()

        if not userServiceInstance.supportsCancel(): # Does not supports cancel, but destroy, so mark it for "later" destroy
            # State is kept, just mark it for destroy after finished preparing
            userService.setProperty('destroy_after', 'y')
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
            logger.debug('Removing userService %a', userService)
            if userService.isUsable() is False and State.isRemovable(userService.state) is False:
                raise OperationException(_('Can\'t remove a non active element'))
            userService.setState(State.REMOVING)
            logger.debug("***** The state now is %s *****", State.toString(userService.state))
            userService.setInUse(False)  # For accounting, ensure that it is not in use right now
            userService.save()

        userServiceInstance = userService.getInstance()
        state = userServiceInstance.destroy()

        # Data will be serialized on makeUnique process
        UserServiceOpChecker.makeUnique(userService, userServiceInstance, state)

        return userService

    def removeOrCancel(self, userService: UserService):
        if userService.isUsable() or State.isRemovable(userService.state):
            return self.remove(userService)

        if userService.isPreparing():
            return self.cancel(userService)

        raise OperationException(_('Can\'t remove nor cancel {} cause its state don\'t allow it').format(userService.name))

    def getExistingAssignationForUser(self, servicePool: ServicePool, user: User) -> typing.Optional[UserService]:
        existing = servicePool.assignedUserServices().filter(user=user, state__in=State.VALID_STATES)  # , deployed_service__visible=True
        lenExisting = existing.count()
        if lenExisting > 0:  # Already has 1 assigned
            logger.debug('Found assigned service from %s to user %s', servicePool, user.name)
            return existing[0]
        return None

    def getAssignationForUser(self, servicePool: ServicePool, user: User) -> typing.Optional[UserService]:  # pylint: disable=too-many-branches
        if servicePool.service.getInstance().spawnsNew is False:
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
            caches = servicePool.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE, os_state=State.USABLE)[:1]
            if caches:
                cache = caches[0]
                # Ensure element is reserved correctly on DB
                if servicePool.cachedUserServices().select_for_update().filter(user=None, uuid=typing.cast(UserService, cache).uuid).update(user=user, cache_level=0) != 1:
                    cache = None
            else:
                cache = None

        # Out of previous atomic
        if not cache:
            with transaction.atomic():
                cache = servicePool.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE)[:1]
                if cache:
                    cache = cache[0]
                    if servicePool.cachedUserServices().select_for_update().filter(user=None, uuid=typing.cast(UserService, cache).uuid).update(user=user, cache_level=0) != 1:
                        cache = None
                else:
                    cache = None

        # Out of atomic transaction
        if cache:
            # Early assign
            cache.assignToUser(user)

            logger.debug('Found a cached-ready service from %s for user %s, item %s', servicePool, user, cache)
            events.addEvent(servicePool, events.ET_CACHE_HIT, fld1=servicePool.cachedUserServices().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE).count())
            return cache

        # Cache missed

        # Now find if there is a preparing one
        with transaction.atomic():
            caches = servicePool.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.PREPARING)[:1]
            if caches:
                cache = caches[0]
                if servicePool.cachedUserServices().select_for_update().filter(user=None, uuid=typing.cast(UserService, cache).uuid).update(user=user, cache_level=0) != 1:
                    cache = None
            else:
                cache = None

        # Out of atomic transaction
        if cache:
            cache.assignToUser(user)

            logger.debug('Found a cached-preparing service from %s for user %s, item %s', servicePool, user, cache)
            events.addEvent(servicePool, events.ET_CACHE_MISS, fld1=servicePool.cachedUserServices().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.PREPARING).count())
            return cache

        # Can't assign directly from L2 cache... so we check if we can create e new service in the limits requested
        serviceType = servicePool.service.getType()
        if serviceType.usesCache:
            # inCacheL1 = ds.cachedUserServices().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L1_CACHE)).count()
            inAssigned = servicePool.assignedUserServices().filter(UserServiceManager.getStateFilter()).count()
            # totalL1Assigned = inCacheL1 + inAssigned
            if inAssigned >= servicePool.max_srvs:  # cacheUpdater will drop unnecesary L1 machines, so it's not neccesary to check against inCacheL1
                log.doLog(servicePool, log.WARN, 'Max number of services reached: {}'.format(servicePool.max_srvs), log.INTERNAL)
                raise MaxServicesReachedError()

        # Can create new service, create it
        events.addEvent(servicePool, events.ET_CACHE_MISS, fld1=0)
        return self.createAssignedFor(servicePool, user)

    def getServicesInStateForProvider(self, provider_id: int, state: str) -> int:
        """
        Returns the number of services of a service provider in the state indicated
        """
        return UserService.objects.filter(deployed_service__service__provider__id=provider_id, state=state).count()

    def canRemoveServiceFromDeployedService(self, servicePool: ServicePool) -> bool:
        """
        checks if we can do a "remove" from a deployed service
        serviceIsntance is just a helper, so if we already have unserialized deployedService
        """
        removing = self.getServicesInStateForProvider(servicePool.service.provider_id, State.REMOVING)
        serviceInstance = servicePool.service.getInstance()
        if removing >= serviceInstance.parent().getMaxRemovingServices() and serviceInstance.parent().getIgnoreLimits() is False:
            return False
        return True

    def canInitiateServiceFromDeployedService(self, servicePool: ServicePool) -> bool:
        """
        Checks if we can start a new service
        """
        preparing = self.getServicesInStateForProvider(servicePool.service.provider_id, State.PREPARING)
        serviceInstance = servicePool.service.getInstance()
        if preparing >= serviceInstance.parent().getMaxPreparingServices() and serviceInstance.parent().getIgnoreLimits() is False:
            return False
        return True

    def isReady(self, userService: UserService) -> bool:
        userService.refresh_from_db()
        logger.debug('Checking ready of %s', userService)

        if userService.state != State.USABLE or userService.os_state != State.USABLE:
            logger.debug('State is not usable for %s', userService.name)
            return False

        logger.debug('Service %s is usable, checking it via setReady', userService)
        userServiceInstance = userService.getInstance()
        try:
            state = userServiceInstance.setReady()
        except Exception as e:
            logger.warn('Could not check readyness of %s: %s', userService, e)
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

        if not userService.deployed_service.service.getType().canReset:
            return

        logger.debug('Reseting %s', userService)

        userServiceInstance = userService.getInstance()
        try:
            userServiceInstance.reset()
        except Exception:
            logger.exception('Reseting service')

    def notifyPreconnect(self, userService: UserService, userName: str, protocol: str) -> None:
        comms.notifyPreconnect(userService, userName, protocol)

    def checkUuid(self, userService: UserService) ->  bool:
        return comms.checkUuid(userService)

    def requestScreenshot(self, userService: UserService) -> bytes:
        return comms.requestScreenshot(userService)

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
        doPublicationCleanup = True if not osManager else not osManager.getInstance().isPersistent()

        if doPublicationCleanup:
            remove = False
            with transaction.atomic():
                userService = UserService.objects.select_for_update().get(id=userService.id)
                activePublication = userService.deployed_service.activePublication()
                if userService.publication and activePublication and userService.publication.id != activePublication.id:
                    logger.debug('Old revision of user service, marking as removable: %s', userService)
                    remove = True

            if remove:
                userService.remove()

    def notifyReadyFromOsManager(self, userService: UserService, data: typing.Any) -> None:
        try:
            userServiceInstance = userService.getInstance()
            logger.debug('Notifying user service ready state')
            state = userServiceInstance.notifyReadyFromOsManager(data)
            logger.debug('State: %s', state)
            if state == State.FINISHED:
                userService.updateData(userServiceInstance)
                logger.debug('Service is now ready')
            elif userService.state in (State.USABLE, State.PREPARING):  # We don't want to get active deleting or deleted machines...
                userService.setState(State.PREPARING)
                UserServiceOpChecker.makeUnique(userService, userServiceInstance, state)
            userService.save(update_fields=['os_state'])
        except Exception as e:
            logger.exception('Unhandled exception on notyfyReady: %s', e)
            userService.setState(State.ERROR)
            return

    def locateUserService(self, user: User, idService: str, create: bool = False) -> typing.Optional[UserService]:
        kind, uuidService = idService[0], idService[1:]

        logger.debug('Kind of service: %s, idService: %s', kind, uuidService)
        userService: typing.Optional[UserService] = None

        if kind == 'A':  # This is an assigned service
            logger.debug('Getting A service %s', uuidService)
            userService = UserService.objects.get(uuid=uuidService, user=user)
            typing.cast(UserService, userService).deployed_service.validateUser(user)
        else:
            servicePool: ServicePool = ServicePool.objects.get(uuid=uuidService)
            # We first do a sanity check for this, if the user has access to this service
            # If it fails, will raise an exception
            servicePool.validateUser(user)

            # Now we have to locate an instance of the service, so we can assign it to user.
            if create:  # getAssignation, if no assignation is found, tries to create one
                userService = self.getAssignationForUser(servicePool, user)
            else:  # Sometimes maybe we only need to locate the existint user service
                userService = self.getExistingAssignationForUser(servicePool, user)

        logger.debug('Found service: %s', userService)

        return userService

    def getService( # pylint: disable=too-many-locals, too-many-branches, too-many-statements
            self,
            user: User,
            os: typing.Dict,
            srcIp: str,
            idService: str,
            idTransport: str,
            doTest: bool = True,
            clientHostname: typing.Optional[str] = None
        ) -> typing.Tuple[
            typing.Optional[str],
            UserService,
            typing.Optional['services.UserDeployment'],
            Transport,
            typing.Optional[transports.Transport]]:
        """
        Get service info from user service
        """
        if idService[0] == 'M':  # Meta pool
            return self.getMeta(user, srcIp, os, idService[1:])

        userService = self.locateUserService(user, idService, create=True)

        if not userService:
            raise InvalidServiceException(_('The requested service is not available'))

        # Early log of "access try" so we can imagine what is going on
        userService.setConnectionSource(srcIp, clientHostname or srcIp)

        if userService.isInMaintenance():
            raise ServiceInMaintenanceMode()

        if not userService.deployed_service.isAccessAllowed():
            raise ServiceAccessDeniedByCalendar()

        if not idTransport:  # Find a suitable transport
            t: Transport
            for t in userService.deployed_service.transports.order_by('priority'):
                typeTrans = t.getType()
                if t.validForIp(srcIp) and typeTrans.supportsOs(os['OS']) and t.validForOs(os['OS']):
                    idTransport = t.uuid
                    break

        try:
            transport: Transport = Transport.objects.get(uuid=idTransport)
        except Exception:
            raise InvalidServiceException()

        # Ensures that the transport is allowed for this service
        if  userService.deployed_service.transports.filter(id=transport.id).count() == 0:
            raise InvalidServiceException()

        # If transport is not available for the request IP...
        if not transport.validForIp(srcIp):
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
            log.doLog(userService, log.INFO, "User {0} from {1} has initiated access".format(user.name, srcIp), log.WEB)
            # If ready, show transport for this service, if also ready ofc
            userServiceInstance = userService.getInstance()
            ip = userServiceInstance.getIp()
            userService.logIP(ip)  # Update known ip
            logger.debug('IP: %s', ip)

            if self.checkUuid(userService) is False:  # The service is not the expected one
                serviceNotReadyCode = 0x0004
                log.doLog(userService, log.WARN, "User service is not accessible due to invalid UUID (ip {0})".format(ip), log.TRANSPORT)
                logger.debug('UUID check failed for user service %s', userService)
            else:
                events.addEvent(userService.deployed_service, events.ET_ACCESS, username=userName, srcip=srcIp, dstip=ip, uniqueid=userService.unique_id)
                if ip:
                    serviceNotReadyCode = 0x0003
                    transportInstance = transport.getInstance()
                    if transportInstance.isAvailableFor(userService, ip):
                        # userService.setConnectionSource(srcIp, 'unknown')
                        log.doLog(userService, log.INFO, "User service ready", log.WEB)
                        self.notifyPreconnect(userService, transportInstance.processedUser(userService, user), transportInstance.protocol)
                        traceLogger.info('READY on service "%s" for user "%s" with transport "%s" (ip:%s)', userService.name, userName, transport.name, ip)
                        return ip, userService, userServiceInstance, transport, transportInstance

                    message = transportInstance.getCustomAvailableErrorMsg(userService, ip)
                    log.doLog(userService, log.WARN, message, log.TRANSPORT)
                    logger.debug('Transport is not ready for user service %s: %s', userService, message)
                else:
                    logger.debug('Ip not available from user service %s', userService)
        else:
            log.doLog(userService, log.WARN, "User {} from {} tried to access, but service was not ready".format(user.name, srcIp), log.WEB)

        traceLogger.error('ERROR %s on service "%s" for user "%s" with transport "%s" (ip:%s)', serviceNotReadyCode, userService.name, userName, transport.name, ip)
        raise ServiceNotReadyError(code=serviceNotReadyCode, service=userService, transport=transport)

    def getMeta(
            self,
            user: User,
            srcIp: str,
            os: typing.Dict,
            idMetaPool: str,
            clientHostName: typing.Optional[str] = None
        ) -> typing.Tuple[typing.Optional[str], UserService, typing.Optional['services.UserDeployment'], Transport, typing.Optional[transports.Transport]]:
        logger.debug('This is meta')
        # We need to locate the service pool related to this meta, and also the transport
        # First, locate if there is a service in any pool associated with this metapool
        meta: MetaPool = MetaPool.objects.get(uuid=idMetaPool)

        # If access is denied by calendar...
        if meta.isAccessAllowed() is False:
            raise ServiceAccessDeniedByCalendar()

        # Sort pools based on meta selection
        if meta.policy == MetaPool.PRIORITY_POOL:
            sortPools = [(p.priority, p.pool) for p in meta.members.all()]
        elif meta.policy == MetaPool.MOST_AVAILABLE_BY_NUMBER:
            sortPools = [(p.usage(), p) for p in meta.pools.all()]
        else:
            sortPools = [(random.randint(0, 10000), p) for p in meta.pools.all()]  # Just shuffle them

        # Sort pools related to policy now, and xtract only pools, not sort keys
        # Remove "full" pools (100%) from result and pools in maintenance mode, not ready pools, etc...
        pools: typing.List[ServicePool] = [p[1] for p in sorted(sortPools, key=lambda x: x[0]) if p[1].usage() < 100 and p[1].isUsable()]

        logger.debug('Pools: %s', pools)

        usable: typing.Optional[typing.Tuple[ServicePool, Transport]] = None
        # Now, Lets find first if there is one assigned in ANY pool

        def ensureTransport(pool: ServicePool) -> typing.Optional[typing.Tuple[ServicePool, Transport]]:
            found = None
            t: Transport
            for t in pool.transports.all().order_by('priority'):
                typeTrans = t.getType()
                if t.getType() and t.validForIp(srcIp) and typeTrans.supportsOs(os['OS']) and t.validForOs(os['OS']):
                    found = (pool, t)
                    break
            return found

        try:
            alreadyAssigned: UserService = UserService.objects.filter(
                deployed_service__in=pools,
                state__in=State.VALID_STATES,
                user=user,
                cache_level=0
            ).order_by('deployed_service__name')[0]
            logger.debug('Already assigned %s', alreadyAssigned)

            # Ensure transport is available for the OS, and store it
            usable = ensureTransport(alreadyAssigned.deployed_service)
            # Found already assigned, ensure everythinf is fine
            if usable:
                return self.getService(user, os, srcIp, 'F' + usable[0].uuid, usable[1].uuid, doTest=False, clientHostname=clientHostName)

        except Exception:  # No service already assigned, lets find a suitable one
            for pool in pools:  # Pools are already sorted, and "full" pools are filtered out
                # Ensure transport is available for the OS
                usable = ensureTransport(pool)

                # Stop if a pool-transport is found and can be assigned to user
                if usable:
                    try:
                        usable[0].validateUser(user)
                        self.getService(user, os, srcIp, 'F' + usable[0].uuid, usable[1].uuid, doTest=False, clientHostname=clientHostName)
                    except Exception as e:
                        logger.info('Meta service %s:%s could not be assigned, trying a new one', usable[0].name, e)
                        usable = None

        if not usable:
            log.doLog(meta, log.WARN, "No user service accessible from device (ip {}, os: {})".format(srcIp, os['OS']), log.SERVICE)
            raise InvalidServiceException(_('The service is not accessible from this device'))

        logger.debug('Found usable pair: %s', usable)
        # We have found an usable deployed already assigned & can be accessed from this, so return it
        return None, usable[0], None, usable[1], None
