# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.db.models import Q
from django.db import transaction
from uds.core.services.Exceptions import OperationException
from uds.core.util.State import State
from uds.core.util import log
from uds.core.util.Config import GlobalConfig
from uds.core.services.Exceptions import MaxServicesReachedError, ServiceInMaintenanceMode, InvalidServiceException, ServiceNotReadyError, ServiceAccessDeniedByCalendar
from uds.models import ServicePool, UserService, getSqlDatetime, Transport
from uds.core import services
from uds.core.services import Service
from uds.core.util.stats import events

from .userservice.opchecker  import UserServiceOpChecker

import requests
import json
import logging

__updated__ = '2018-05-16'

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')


class UserServiceManager(object):
    _manager = None

    def __init__(self):
        pass

    @staticmethod
    def manager():
        if UserServiceManager._manager is None:
            UserServiceManager._manager = UserServiceManager()
        return UserServiceManager._manager

    @staticmethod
    def getCacheStateFilter(level):
        return Q(cache_level=level) & UserServiceManager.getStateFilter()

    @staticmethod
    def getStateFilter():
        return Q(state__in=[State.PREPARING, State.USABLE])

    def __checkMaxDeployedReached(self, deployedService):
        """
        Checks if maxDeployed for the service has been reached, and, if so,
        raises an exception that no more services of this kind can be reached
        """
        serviceInstance = deployedService.service.getInstance()
        # Early return, so no database count is needed
        if serviceInstance.maxDeployed == Service.UNLIMITED:
            return

        numberOfServices = deployedService.userServices.filter(state__in=[State.PREPARING, State.USABLE]).count()

        if serviceInstance.maxDeployed <= numberOfServices:
            raise MaxServicesReachedError('Max number of allowed deployments for service reached')

    def __createCacheAtDb(self, deployedServicePublication, cacheLevel):
        """
        Private method to instatiate a cache element at database with default states
        """
        # Checks if maxDeployed has been reached and if so, raises an exception
        self.__checkMaxDeployedReached(deployedServicePublication.deployed_service)
        now = getSqlDatetime()
        return deployedServicePublication.userServices.create(cache_level=cacheLevel, state=State.PREPARING, os_state=State.PREPARING,
                                                              state_date=now, creation_date=now, data='',
                                                              deployed_service=deployedServicePublication.deployed_service,
                                                              user=None, in_use=False)

    def __createAssignedAtDb(self, deployedServicePublication, user):
        """
        Private method to instatiate an assigned element at database with default state
        """
        self.__checkMaxDeployedReached(deployedServicePublication.deployed_service)
        now = getSqlDatetime()
        return deployedServicePublication.userServices.create(cache_level=0, state=State.PREPARING, os_state=State.PREPARING,
                                                              state_date=now, creation_date=now, data='',
                                                              deployed_service=deployedServicePublication.deployed_service,
                                                              user=user, in_use=False)

    def __createAssignedAtDbForNoPublication(self, deployedService, user):
        """
        __createCacheAtDb and __createAssignedAtDb uses a publication for create the UserService.
        There is cases where deployed services do not have publications (do not need them), so we need this method to create
        an UserService with no publications, and create them from an DeployedService
        """
        self.__checkMaxDeployedReached(deployedService)
        now = getSqlDatetime()
        return deployedService.userServices.create(cache_level=0, state=State.PREPARING, os_state=State.PREPARING,
                                                   state_date=now, creation_date=now, data='', publication=None, user=user, in_use=False)

    def createCacheFor(self, deployedServicePublication, cacheLevel):
        """
        Creates a new cache for the deployed service publication at level indicated
        """
        logger.debug('Creating a new cache element at level {0} for publication {1}'.format(cacheLevel, deployedServicePublication))
        cache = self.__createCacheAtDb(deployedServicePublication, cacheLevel)
        ci = cache.getInstance()
        state = ci.deployForCache(cacheLevel)

        UserServiceOpChecker.checkAndUpdateState(cache, ci, state)
        return cache

    def createAssignedFor(self, ds, user):
        """
        Creates a new assigned deployed service for the publication and user indicated
        """
        if ds.service.getType().publicationType is not None:
            dsp = ds.activePublication()
            logger.debug('Creating a new assigned element for user {0} por publication {1}'.format(user, dsp))
            assigned = self.__createAssignedAtDb(dsp, user)
        else:
            logger.debug('Creating a new assigned element for user {0}'.format(user))
            assigned = self.__createAssignedAtDbForNoPublication(ds, user)

        ai = assigned.getInstance()
        state = ai.deployForUser(user)

        UserServiceOpChecker.makeUnique(assigned, ai, state)

        return assigned

    def createAssignable(self, ds, deployed, user):
        """
        Creates an assignable service
        """
        now = getSqlDatetime()
        assignable = ds.userServices.create(cache_level=0, state=State.PREPARING, os_state=State.PREPARING,
                                            state_date=now, creation_date=now, data='', user=user, in_use=False)
        state = deployed.deployForUser(user)
        try:
            UserServiceOpChecker.makeUnique(assignable, deployed, state)
        except Exception as e:
            logger.exception("Exception {0}".format(e))
        logger.debug("Assignable: {0}".format(assignable))
        return assignable

    def moveToLevel(self, cache, cacheLevel):
        """
        Moves a cache element from one level to another
        @return: cache element
        """
        cache = UserService.objects.get(id=cache.id)
        logger.debug('Moving cache {0} to level {1}'.format(cache, cacheLevel))
        ci = cache.getInstance()
        state = ci.moveToCache(cacheLevel)
        cache.cache_level = cacheLevel
        logger.debug('Service State: {0} {1} {2}'.format(State.toString(state), State.toString(cache.state), State.toString(cache.os_state)))
        if State.isRuning(state) and cache.isUsable():
            cache.setState(State.PREPARING)

        UserServiceOpChecker.makeUnique(cache, ci, state)

    def cancel(self, uService):
        """
        Cancels a user service creation
        @return: the Uservice canceling
        """
        uService = UserService.objects.get(pk=uService.id)
        logger.debug('Canceling uService {0} creation'.format(uService))
        if uService.isPreparing() is False:
            logger.info('Cancel requested for a non running operation, performing removal instead')
            return self.remove(uService)

        ui = uService.getInstance()
        # We simply notify service that it should cancel operation
        state = ui.cancel()
        uService.updateData(ui)
        uService.setState(State.CANCELING)
        UserServiceOpChecker.makeUnique(uService, ui, state)
        return uService

    def remove(self, uService):
        """
        Removes a uService element
        @return: the uService removed (marked for removal)
        """
        with transaction.atomic():
            uService = UserService.objects.select_for_update().get(id=uService.id)
            logger.debug('Removing uService {0}'.format(uService))
            if uService.isUsable() is False and State.isRemovable(uService.state) is False:
                raise OperationException(_('Can\'t remove a non active element'))
            uService.setState(State.REMOVING)
            logger.debug("***** The state now is {}".format(State.toString(uService.state)))
            uService.setInUse(False)  # For accounting, ensure that it is not in use right now
            uService.save()

        ci = uService.getInstance()
        state = ci.destroy()

        UserServiceOpChecker.makeUnique(uService, ci, state)

    def removeOrCancel(self, uService):
        if uService.isUsable() or State.isRemovable(uService.state):
            return self.remove(uService)
        elif uService.isPreparing():
            return self.cancel(uService)
        else:
            raise OperationException(_('Can\'t remove nor cancel {0} cause its states don\'t allow it'))

    def removeInfoItems(self, dsp):
        with transaction.atomic():
            dsp.cachedDeployedService.filter(state__in=State.INFO_STATES).delete()

    def getExistingAssignationForUser(self, ds, user):
        existing = ds.assignedUserServices().filter(user=user, state__in=State.VALID_STATES, deployed_service__visible=True)
        lenExisting = existing.count()
        if lenExisting > 0:  # Already has 1 assigned
            logger.debug('Found assigned service from {0} to user {1}'.format(ds, user.name))
            return existing[0]
            # if existing[0].state == State.ERROR:
            #    if lenExisting > 1:
            #        return existing[1]
            # else:
            #    return existing[0]
        return None

    def getAssignationForUser(self, ds, user):

        if ds.service.getInstance().spawnsNew is False:
            assignedUserService = self.getExistingAssignationForUser(ds, user)
        else:
            assignedUserService = None

        # If has an assigned user service, returns this without any more work
        if assignedUserService is not None:
            return assignedUserService

        # Now try to locate 1 from cache already "ready" (must be usable and at level 1)
        with transaction.atomic():
            cache = ds.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE, os_state=State.USABLE)[:1]
            if len(cache) == 0:
                cache = ds.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE)[:1]
            if len(cache) > 0:
                cache = cache[0]
                cache.assignToUser(user)
                cache.save()  # Store assigned ASAP, we do not know how long assignToUser method of instance will take
            else:
                cache = None

        # Out of atomic transaction
        if cache is not None:
            logger.debug('Found a cached-ready service from {0} for user {1}, item {2}'.format(ds, user, cache))
            events.addEvent(ds, events.ET_CACHE_HIT, fld1=ds.cachedUserServices().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE).count())
            ci = cache.getInstance()  # User Deployment instance
            ci.assignToUser(user)
            cache.updateData(ci)
            cache.save()
            return cache

        # Cache missed

        # Now find if there is a preparing one
        with transaction.atomic():
            cache = ds.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.PREPARING)[:1]
            if len(cache) > 0:
                cache = cache[0]
                cache.assignToUser(user)
                cache.save()
            else:
                cache = None

        # Out of atomic transaction
        if cache is not None:
            logger.debug('Found a cached-preparing service from {0} for user {1}, item {2}'.format(ds, user, cache))
            events.addEvent(ds, events.ET_CACHE_MISS, fld1=ds.cachedUserServices().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.PREPARING).count())
            ci = cache.getInstance()  # User Deployment instance
            ci.assignToUser(user)
            cache.updateData(ci)
            cache.save()
            return cache

        # Can't assign directly from L2 cache... so we check if we can create e new service in the limits requested
        ty = ds.service.getType()
        if ty.usesCache is True:
            # inCacheL1 = ds.cachedUserServices().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L1_CACHE)).count()
            inAssigned = ds.assignedUserServices().filter(UserServiceManager.getStateFilter()).count()
            # totalL1Assigned = inCacheL1 + inAssigned
            if inAssigned >= ds.max_srvs:  # cacheUpdater will drop necesary L1 machines, so it's not neccesary to check against inCacheL1
                raise MaxServicesReachedError()
        # Can create new service, create it
        events.addEvent(ds, events.ET_CACHE_MISS, fld1=0)
        return self.createAssignedFor(ds, user)

    def getServicesInStateForProvider(self, provider_id, state):
        """
        Returns the number of services of a service provider in the state indicated
        """
        return UserService.objects.filter(deployed_service__service__provider__id=provider_id, state=state).count()

    def canRemoveServiceFromDeployedService(self, ds):
        """
        checks if we can do a "remove" from a deployed service
        serviceIsntance is just a helper, so if we already have unserialized deployedService
        """
        removing = self.getServicesInStateForProvider(ds.service.provider_id, State.REMOVING)
        serviceInstance = ds.service.getInstance()
        if removing >= serviceInstance.parent().getMaxRemovingServices() and serviceInstance.parent().getIgnoreLimits() is False:
            return False
        return True

    def canInitiateServiceFromDeployedService(self, ds):
        """
        Checks if we can start a new service
        """
        preparing = self.getServicesInStateForProvider(ds.service.provider_id, State.PREPARING)
        serviceInstance = ds.service.getInstance()
        if preparing >= serviceInstance.parent().getMaxPreparingServices() and serviceInstance.parent().getIgnoreLimits() is False:
            return False
        return True

    def isReady(self, uService):
        UserService.objects.update()
        uService = UserService.objects.get(id=uService.id)
        logger.debug('Checking ready of {0}'.format(uService))
        if uService.state != State.USABLE or uService.os_state != State.USABLE:
            logger.debug('State is not usable for {0}'.format(uService))
            return False
        logger.debug('Service {0} is usable, checking it via setReady'.format(uService))
        ui = uService.getInstance()
        state = ui.setReady()
        logger.debug('State: {0}'.format(state))
        uService.updateData(ui)
        if state == State.FINISHED:
            uService.save()
            return True
        uService.setState(State.PREPARING)
        UserServiceOpChecker.makeUnique(uService, ui, state)
        return False

    def reset(self, uService):
        UserService.objects.update()
        uService = UserService.objects.get(id=uService.id)
        if uService.deployed_service.service.getType().canReset is False:
            return

        logger.debug('Reseting'.format(uService))

        ui = uService.getInstance()
        try:
            ui.reset()
        except Exception:
            logger.exception('Reseting service')

    def notifyPreconnect(self, uService, userName, protocol):

        proxy = uService.deployed_service.proxy
        url = uService.getCommsUrl()
        if url is None:
            logger.debug('No notification is made because agent does not supports notifications')
            return

        url += '/preConnect'

        try:
            data = {'user': userName, 'protocol': protocol}
            if proxy is not None:
                r = proxy.doProxyRequest(url=url, data=data, timeout=2)
            else:
                r = requests.post(url,
                                  data=json.dumps(data),
                                  headers={'content-type': 'application/json'},
                                  verify=False,
                                  timeout=2)
            r = json.loads(r.content)
            logger.debug('Sent pre connection to client using {}: {}'.format(url, r))
            # In fact we ignore result right now
        except Exception as e:
            logger.info('preConnection failed: {}. Check connection on destination machine: {}'.format(e, url))

    def checkUuid(self, uService):

        proxy = uService.deployed_service.proxy

        url = uService.getCommsUrl()

        if url is None:
            logger.debug('No uuid to retrieve because agent does not supports notifications')
            return True  # UUid is valid because it is not supported checking it

        version = uService.getProperty('actor_version', '')
        # Just for 2.0 or newer, previous actors will not support this method.
        # Also externally supported agents will not support this method (as OpenGnsys)
        if '-' in version or version < '2.0.0':
            return True

        url += '/uuid'

        try:
            if proxy is not None:
                r = proxy.doProxyRequest(url=url, timeout=5)
            else:
                r = requests.get(url, verify=False, timeout=5)
            uuid = json.loads(r.content)
            if uuid != uService.uuid:
                logger.info('The requested machine has uuid {} and the expected was {}'.format(uuid, uService.uuid))
                return False

            logger.debug('Got uuid from machine: {} {} {}'.format(url, uuid, uService.uuid))
            # In fact we ignore result right now
        except Exception as e:
            logger.info('Get uuid failed: {}. Check connection on destination machine: {}'.format(e, url))
            # return True

        return True

    def sendScript(self, uService, script):
        """
        If allowed, send script to user service
        """
        proxy = uService.deployed_service.proxy

        # logger.debug('Senging script: {}'.format(script))
        url = uService.getCommsUrl()
        if url is None:
            logger.error('Can\'t connect with actor (no actor or legacy actor)')
            return
        url += '/script'

        try:
            data = {'script': script}
            if proxy is not None:
                r = proxy.doProxyRequest(url=url, data=data, timeout=5)
            else:
                r = requests.post(
                    url,
                    data=json.dumps(data),
                    headers={'content-type': 'application/json'},
                    verify=False,
                    timeout=5
                )
            r = json.loads(r.content)
            logger.debug('Sent script to client using {}: {}'.format(url, r))
            # In fact we ignore result right now
        except Exception as e:
            logger.error('Exception caught sending script: {}. Check connection on destination machine: {}'.format(e, url))

        # All done

    def requestLogoff(self, uService):
        """
        Ask client to logoff user
        """
        url = uService.getCommsUrl()
        if url is None:
            logger.error('Can\'t connect with actor (no actor or legacy actor)')
            return
        url += '/logoff'

        try:
            r = requests.post(url, data=json.dumps({}), headers={'content-type': 'application/json'}, verify=False, timeout=4)
            r = json.loads(r.content)
            logger.debug('Sent logoff to client using {}: {}'.format(url, r))
            # In fact we ignore result right now
        except Exception as e:
            # TODO: Right now, this is an "experimental" feature, not supported on Apps (but will)
            pass
            # logger.info('Logoff requested but service was not listening: {}'.format(e, url))

        # All done

    def checkForRemoval(self, uService):
        """
        This method is used by UserService when a request for setInUse(False) is made
        This checks that the service can continue existing or not
        """
        osm = uService.deployed_service.osmanager
        # If os manager says "machine is persistent", do not tray to delete "previous version" assigned machines
        doPublicationCleanup = True if osm is None else not osm.getInstance().isPersistent()

        if doPublicationCleanup:
            remove = False
            with transaction.atomic():
                uService = UserService.objects.select_for_update().get(id=uService.id)
                if uService.publication is not None and uService.publication.id != uService.deployed_service.activePublication().id:
                    logger.debug('Old revision of user service, marking as removable: {0}'.format(uService))
                    remove = True

            if remove:
                uService.remove()

    def notifyReadyFromOsManager(self, uService, data):
        try:
            ui = uService.getInstance()
            logger.debug('Notifying user service ready state')
            state = ui.notifyReadyFromOsManager(data)
            logger.debug('State: {0}'.format(state))
            uService.updateData(ui)
            if state == State.FINISHED:
                logger.debug('Service is now ready')
                uService.save()
            elif uService.state in (State.USABLE, State.PREPARING):  # We don't want to get active deleting or deleted machines...
                uService.setState(State.PREPARING)
                UserServiceOpChecker.makeUnique(uService, ui, state)
        except Exception as e:
            logger.exception('Unhandled exception on notyfyReady: {}'.format(e))
            uService.setState(State.ERROR)
            return

    def locateUserService(self, user, idService, create=False):
        kind, idService = idService[0], idService[1:]

        logger.debug('Kind of service: {0}, idService: {1}'.format(kind, idService))
        userService = None

        if kind == 'A':  # This is an assigned service
            logger.debug('Getting A service {}'.format(idService))
            userService = UserService.objects.get(uuid=idService)
            userService.deployed_service.validateUser(user)
        elif kind == 'M':  # This is a meta service..
            pass
        else:
            ds = ServicePool.objects.get(uuid=idService)
            # We first do a sanity check for this, if the user has access to this service
            # If it fails, will raise an exception
            ds.validateUser(user)

            # Now we have to locate an instance of the service, so we can assign it to user.
            if create:  # getAssignation, if no assignation is found, tries to create one
                userService = self.getAssignationForUser(ds, user)
            else:  # Sometimes maybe we only need to locate the existint user service
                userService = self.getExistingAssignationForUser(ds, user)

        logger.debug('Found service: {0}'.format(userService))
        return userService

    def getService(self, user, srcIp, idService, idTransport, doTest=True):
        """
        Get service info from
        """
        userService = self.locateUserService(user, idService, create=True)

        # Early log of "access try" so we can imagine what is going on
        userService.setConnectionSource(srcIp, 'unknown')

        if userService.isInMaintenance() is True:
            raise ServiceInMaintenanceMode()

        if userService.deployed_service.isAccessAllowed() is False:
            raise ServiceAccessDeniedByCalendar()

        if idTransport is None or idTransport == '':  # Find a suitable transport
            for v in userService.deployed_service.transports.order_by('priority'):
                if v.validForIp(srcIp):
                    idTransport = v.uuid
                    break

        try:
            trans = Transport.objects.get(uuid=idTransport)
        except Exception:
            raise InvalidServiceException()

        # Ensures that the transport is allowed for this service
        if trans not in userService.deployed_service.transports.all():
            raise InvalidServiceException()

        # If transport is not available for the request IP...
        if trans.validForIp(srcIp) is False:
            msg = 'The requested transport {} is not valid for {}'.format(trans.name, srcIp)
            logger.error(msg)
            raise InvalidServiceException(msg)

        if user is not None:
            userName = user.name
        else:
            userName = 'unknown'

        if doTest is False:
            # traceLogger.info('GOT service "{}" for user "{}" with transport "{}" (NOT TESTED)'.format(userService.name, userName, trans.name))
            return None, userService, None, trans, None

        serviceNotReadyCode = 0x0001
        ip = 'unknown'
        # Test if the service is ready
        if userService.isReady():
            serviceNotReadyCode = 0x0002
            log.doLog(userService, log.INFO, "User {0} from {1} has initiated access".format(user.name, srcIp), log.WEB)
            # If ready, show transport for this service, if also ready ofc
            iads = userService.getInstance()
            ip = iads.getIp()
            userService.logIP(ip)  # Update known ip

            if self.checkUuid(userService) is False:  # Machine is not what is expected
                serviceNotReadyCode = 0x0004
                log.doLog(userService, log.WARN, "User service is not accessible (ip {0})".format(ip), log.TRANSPORT)
                logger.debug('Transport is not ready for user service {0}'.format(userService))
            else:
                events.addEvent(userService.deployed_service, events.ET_ACCESS, username=userName, srcip=srcIp, dstip=ip, uniqueid=userService.unique_id)
                if ip is not None:
                    serviceNotReadyCode = 0x0003
                    itrans = trans.getInstance()
                    if itrans.isAvailableFor(userService, ip):
                        # userService.setConnectionSource(srcIp, 'unknown')
                        log.doLog(userService, log.INFO, "User service ready", log.WEB)
                        self.notifyPreconnect(userService, itrans.processedUser(userService, user), itrans.protocol)
                        traceLogger.info('READY on service "{}" for user "{}" with transport "{}" (ip:{})'.format(userService.name, userName, trans.name, ip))
                        return ip, userService, iads, trans, itrans
                    else:
                        message = itrans.getCustomAvailableErrorMsg(userService, ip)
                        log.doLog(userService, log.WARN, message, log.TRANSPORT)
                        logger.debug('Transport is not ready for user service {}:  {}'.format(userService, message))
                else:
                    logger.debug('Ip not available from user service {0}'.format(userService))
        else:
            log.doLog(userService, log.WARN, "User {0} from {1} tried to access, but service was not ready".format(user.name, srcIp), log.WEB)

        traceLogger.error('ERROR {} on service "{}" for user "{}" with transport "{}" (ip:{})'.format(serviceNotReadyCode, userService.name, userName, trans.name, ip))
        raise ServiceNotReadyError(code=serviceNotReadyCode, service=userService, transport=trans)
