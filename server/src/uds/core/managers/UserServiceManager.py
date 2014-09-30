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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.db.models import Q
from django.db import transaction
from uds.core.jobs.DelayedTask import DelayedTask
from uds.core.jobs.DelayedTaskRunner import DelayedTaskRunner
from uds.core.services.Exceptions import OperationException
from uds.core.util.State import State
from uds.core.util import log
from uds.core.util.Config import GlobalConfig
from uds.core.services.Exceptions import MaxServicesReachedException
from uds.models import UserService, getSqlDatetime
from uds.core import services
from uds.core.services import Service
import logging

logger = logging.getLogger(__name__)

USERSERVICE_TAG = 'cm-'


class UserServiceOpChecker(DelayedTask):
    def __init__(self, service):
        super(UserServiceOpChecker, self).__init__()
        self._svrId = service.id
        self._state = service.state

    @staticmethod
    def makeUnique(userService, userServiceInstance, state):
        '''
        This method makes sure that there will be only one delayedtask related to the userService indicated
        '''
        DelayedTaskRunner.runner().remove(USERSERVICE_TAG + str(userService.id))
        UserServiceOpChecker.checkAndUpdateState(userService, userServiceInstance, state)

    @staticmethod
    def checkAndUpdateState(userService, userServiceInstance, state):
        '''
        Checks the value returned from invocation to publish or checkPublishingState, updating the dsp database object
        Return True if it has to continue checking, False if finished
        '''
        try:
            prevState = userService.state
            userService.unique_id = userServiceInstance.getUniqueId()  # Updates uniqueId
            userService.friendly_name = userServiceInstance.getName()  # And name, both methods can modify serviceInstance, so we save it later
            if State.isFinished(state):
                checkLater = False
                userServiceInstance.finish()
                if State.isPreparing(prevState):
                    if userServiceInstance.service().publicationType is None or userService.publication == userService.deployed_service.activePublication():
                        userService.setState(State.USABLE)
                        # and make this usable if os manager says that it is usable, else it pass to configuring state
                        if userServiceInstance.osmanager() is not None and userService.os_state == State.PREPARING:  # If state is already "Usable", do not recheck it
                            stateOs = userServiceInstance.osmanager().checkState(userService)
                            # If state is finish, we need to notify the userService again that os has finished
                            if State.isFinished(stateOs):
                                state = userServiceInstance.notifyReadyFromOsManager('')
                                userService.updateData(userServiceInstance)
                        else:
                            stateOs = State.FINISHED

                        if State.isRuning(stateOs):
                            userService.setOsState(State.PREPARING)
                        else:
                            userService.setOsState(State.USABLE)
                    else:
                        # We ignore OsManager info and if userService don't belong to "current" publication, mark it as removable
                        userService.setState(State.REMOVABLE)
                elif State.isRemoving(prevState):
                    if userServiceInstance.osmanager() is not None:
                        userServiceInstance.osmanager().release(userService)
                    userService.setState(State.REMOVED)
                else:
                    # Canceled,
                    logger.debug("Canceled us {2}: {0}, {1}".format(prevState, State.toString(state), State.toString(userService)))
                    userService.setState(State.CANCELED)
                    userServiceInstance.osmanager().release(userService)
                userService.updateData(userServiceInstance)
            elif State.isErrored(state):
                checkLater = False
                userService.updateData(userServiceInstance)
                userService.setState(State.ERROR)
            else:
                checkLater = True  # The task is running
                userService.updateData(userServiceInstance)
            userService.save()
            if checkLater:
                UserServiceOpChecker.checkLater(userService, userServiceInstance)
        except Exception as e:
            logger.exception('Checking service state')
            log.doLog(userService, log.ERROR, 'Exception: {0}'.format(e), log.INTERNAL)
            userService.setState(State.ERROR)
            userService.save()

    @staticmethod
    def checkLater(userService, ci):
        '''
        Inserts a task in the delayedTaskRunner so we can check the state of this publication
        @param dps: Database object for DeployedServicePublication
        @param pi: Instance of Publication manager for the object
        '''
        # Do not add task if already exists one that updates this service
        if DelayedTaskRunner.runner().checkExists(USERSERVICE_TAG + str(userService.id)):
            return
        DelayedTaskRunner.runner().insert(UserServiceOpChecker(userService), ci.suggestedTime, USERSERVICE_TAG + str(userService.id))

    def run(self):
        logger.debug('Checking user service finished {0}'.format(self._svrId))
        uService = None
        try:
            uService = UserService.objects.get(pk=self._svrId)
            if uService.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
                # This item is no longer valid, returning will not check it again (no checkLater called)
                return
            ci = uService.getInstance()
            logger.debug("uService instance class: {0}".format(ci.__class__))
            state = ci.checkState()
            UserServiceOpChecker.checkAndUpdateState(uService, ci, state)
        except UserService.DoesNotExist, e:
            logger.error('User service not found (erased from database?) {0} : {1}'.format(e.__class__, e))
        except Exception, e:
            # Exception caught, mark service as errored
            logger.exception("Error {0}, {1} :".format(e.__class__, e))
            if uService is not None:
                log.doLog(uService, log.ERROR, 'Exception: {0}'.format(e), log.INTERNAL)
            try:
                uService.setState(State.ERROR)
                uService.save()
            except Exception:
                logger.error('Can\'t update state of uService object')


class UserServiceManager(object):
    _manager = None

    def __init__(self):
        pass

    @staticmethod
    def manager():
        if UserServiceManager._manager == None:
            UserServiceManager._manager = UserServiceManager()
        return UserServiceManager._manager

    @staticmethod
    def getCacheStateFilter(level):
        return  Q(cache_level=level) & UserServiceManager.getStateFilter()

    @staticmethod
    def getStateFilter():
        return Q(state__in=[State.PREPARING, State.USABLE])

    def __checkMaxDeployedReached(self, deployedService):
        '''
        Checks if maxDeployed for the service has been reached, and, if so,
        raises an exception that no more services of this kind can be reached
        '''
        serviceInstance = deployedService.service.getInstance()
        # Early return, so no database count is needed
        if serviceInstance.maxDeployed == Service.UNLIMITED:
            return

        numberOfServices = deployedService.userServices.filter(
                               state__in=[State.PREPARING, State.USABLE]).count()

        if serviceInstance.maxDeployed <= numberOfServices:
            raise MaxServicesReachedException('Max number of allowed deployments for service reached')

    def __createCacheAtDb(self, deployedServicePublication, cacheLevel):
        '''
        Private method to instatiate a cache element at database with default states
        '''
        # Checks if maxDeployed has been reached and if so, raises an exception
        self.__checkMaxDeployedReached(deployedServicePublication.deployed_service)
        now = getSqlDatetime()
        return deployedServicePublication.userServices.create(cache_level=cacheLevel, state=State.PREPARING, os_state=State.PREPARING,
                                               state_date=now, creation_date=now, data='', deployed_service=deployedServicePublication.deployed_service,
                                               user=None, in_use=False)

    def __createAssignedAtDb(self, deployedServicePublication, user):
        '''
        Private method to instatiate an assigned element at database with default state
        '''
        self.__checkMaxDeployedReached(deployedServicePublication.deployed_service)
        now = getSqlDatetime()
        return deployedServicePublication.userServices.create(cache_level=0, state=State.PREPARING, os_state=State.PREPARING,
                                       state_date=now, creation_date=now, data='', deployed_service=deployedServicePublication.deployed_service, user=user, in_use=False)

    def __createAssignedAtDbForNoPublication(self, deployedService, user):
        '''
        __createCacheAtDb and __createAssignedAtDb uses a publication for create the UserService.
        There is cases where deployed services do not have publications (do not need them), so we need this method to create
        an UserService with no publications, and create them from an DeployedService
        '''
        self.__checkMaxDeployedReached(deployedService)
        now = getSqlDatetime()
        return deployedService.userServices.create(cache_level=0, state=State.PREPARING, os_state=State.PREPARING,
                                       state_date=now, creation_date=now, data='', publication=None, user=user, in_use=False)

    def createCacheFor(self, deployedServicePublication, cacheLevel):
        '''
        Creates a new cache for the deployed service publication at level indicated
        '''
        logger.debug('Creating a new cache element at level {0} for publication {1}'.format(cacheLevel, deployedServicePublication))
        cache = self.__createCacheAtDb(deployedServicePublication, cacheLevel)
        ci = cache.getInstance()
        state = ci.deployForCache(cacheLevel)

        UserServiceOpChecker.checkAndUpdateState(cache, ci, state)
        return cache

    def createAssignedFor(self, ds, user):
        '''
        Creates a new assigned deployed service for the publication and user indicated
        '''
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
        '''
        Creates an assignable service
        '''
        now = getSqlDatetime()
        assignable = ds.userServices.create(cache_level=0, state=State.PREPARING, os_state=State.PREPARING,
                                       state_date=now, creation_date=now, data='', user=user, in_use=False)
        state = deployed.deployForUser(user)
        try:
            UserServiceOpChecker.makeUnique(assignable, deployed, state)
        except Exception, e:
            logger.exception("Exception {0}".format(e))
        logger.debug("Assignable: {0}".format(assignable))
        return assignable

    def moveToLevel(self, cache, cacheLevel):
        '''
        Moves a cache element from one level to another
        @return: cache element
        '''
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
        '''
        Cancels a user service creation
        @return: the Uservice canceling
        '''
        uService = UserService.objects.get(pk=uService.id)
        logger.debug('Canceling uService {0} creation'.format(uService))
        if uService.isPreparing() == False:
            logger.INFO(_('Cancel requested for a non running operation, doing remove instead'))
            return self.remove(uService)

        ui = uService.getInstance()
        # We simply notify service that it should cancel operation
        state = ui.cancel()
        uService.updateData(ui)
        uService.setState(State.CANCELING)
        UserServiceOpChecker.makeUnique(uService, ui, state)
        return uService

    def remove(self, uService):
        '''
        Removes a uService element
        @return: the uService removed (marked for removal)
        '''
        uService = UserService.objects.get(id=uService.id)
        logger.debug('Removing uService {0}'.format(uService))
        if uService.isUsable() == False and State.isRemovable(uService.state) == False:
            raise OperationException(_('Can\'t remove a non active element'))

        ci = uService.getInstance()
        state = ci.destroy()
        uService.setState(State.REMOVING)
        UserServiceOpChecker.makeUnique(uService, ci, state)

    def removeOrCancel(self, uService):
        if uService.isUsable() or State.isRemovable(uService.state):
            return self.remove(uService)
        elif uService.isPreparing():
            return self.cancel(uService)
        else:
            raise OperationException(_('Can\'t remove nor cancel {0} cause its states doesn\'t allows it'))

    def removeInfoItems(self, dsp):
        with transaction.atomic():
            dsp.cachedDeployedService.filter(state__in=State.INFO_STATES).delete()

    def getAssignationForUser(self, ds, user):
        # First, we try to locate an already assigned service
        existing = ds.assignedUserServices().filter(user=user, state__in=State.VALID_STATES)
        lenExisting = existing.count()
        if lenExisting > 0:  # Already has 1 assigned
            logger.debug('Found assigned service from {0} to user {1}'.format(ds, user.name))
            return existing[0]
            # if existing[0].state == State.ERROR:
            #    if lenExisting > 1:
            #        return existing[1]
            # else:
            #    return existing[0]

        # Now try to locate 1 from cache already "ready" (must be usable and at level 1)
        with transaction.atomic():
            cache = ds.cachedUserServices().select_for_update().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.USABLE)[:1]
            if len(cache) > 0:
                cache = cache[0]
                cache.assignToUser(user)
                cache.save()  # Store assigned ASAP, we do not know how long assignToUser method of instance will take
            else:
                cache = None

        if cache is not None:
            logger.debug('Found a cached-ready service from {0} for user {1}, item {2}'.format(ds, user, cache))
            ci = cache.getInstance()  # User Deployment instance
            ci.assignToUser(user)
            cache.updateData(ci)
            cache.save()
            return cache

        # Now find if there is a preparing one
        with transaction.atomic():
            cache = ds.cachedUserServices().filter(cache_level=services.UserDeployment.L1_CACHE, state=State.PREPARING)[:1]
            if len(cache) > 0:
                cache = cache[0]
                cache.assignToUser(user)
                cache.save()
            else:
                cache = None

        if cache is not None:
            logger.debug('Found a cached-preparing service from {0} for user {1}, item {2}'.format(ds, user, cache))
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
                raise MaxServicesReachedException()
        # Can create new service, create it
        return self.createAssignedFor(ds, user)

    def getServicesInStateForProvider(self, provider_id, state):
        '''
        Returns the number of services of a service provider in the state indicated
        '''
        return UserService.objects.filter(deployed_service__service__provider__id=provider_id, state=state).count()

    def canRemoveServiceFromDeployedService(self, ds):
        '''
        checks if we can do a "remove" from a deployed service
        '''
        removing = self.getServicesInStateForProvider(ds.service.provider_id, State.REMOVING)
        if removing >= GlobalConfig.MAX_REMOVING_SERVICES.getInt() and GlobalConfig.IGNORE_LIMITS.getBool() == False:
            return False
        return True

    def canInitiateServiceFromDeployedService(self, ds):
        '''
        Checks if we can start a new service
        '''
        preparing = self.getServicesInStateForProvider(ds.service.provider_id, State.PREPARING)
        if preparing >= GlobalConfig.MAX_PREPARING_SERVICES.getInt() and GlobalConfig.IGNORE_LIMITS.getBool() == False:
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

    def checkForRemoval(self, uService):
        '''
        This method is used by UserService when a request for setInUse(False) is made
        This checks that the service can continue existing or not
        '''
        # uService = UserService.objects.get(id=uService.id)
        if uService.publication == None:
            return
        if uService.publication.id != uService.deployed_service.activePublication().id:
            logger.debug('Old revision of user service, marking as removable: {0}'.format(uService))
            uService.remove()

    def notifyReadyFromOsManager(self, uService, data):
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
