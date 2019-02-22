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

from uds.core.jobs.DelayedTask import DelayedTask
from uds.core.jobs.DelayedTaskRunner import DelayedTaskRunner
from uds.core.util.State import State
from uds.core.util import log
from uds.models import UserService

import logging

__updated__ = '2019-02-22'

logger = logging.getLogger(__name__)

USERSERVICE_TAG = 'cm-'


# State updaters
# This will be executed on current service state for checking transitions to new state, task states, etc..
class StateUpdater(object):

    def __init__(self, userService, userServiceInstance=None):
        self.userService = userService
        self.userServiceInstance = userServiceInstance if userServiceInstance is not None else userService.getInstance()

    def setError(self, msg=None):
        logger.error('Got error on processor: {}'.format(msg))
        self.save(State.ERROR)
        if msg is not None:
            log.doLog(self.userService, log.ERROR, msg, log.INTERNAL)

    def save(self, newState=None):
        if newState is not None:
            self.userService.setState(newState)
        self.userService.updateData(self.userServiceInstance)
        self.userService.save(update_fields=['data', 'state', 'state_date'])

    def checkLater(self):
        UserServiceOpChecker.checkLater(self.userService, self.userServiceInstance)

    def run(self, state):
        executor = {
         State.RUNNING: self.running,
         State.ERROR: self.error,
         State.FINISHED: self.finish
        }.get(state, self.error)

        logger.debug('Running updater with state {} and executor {}'.format(State.toString(state), executor))

        try:
            executor()
        except Exception as e:
            self.setError('Exception: {}'.format(e))

    def finish(self):
        raise NotImplementedError('finish method must be overriden')

    def running(self):
        self.save()
        self.checkLater()

    def error(self):
        self.setError(self.userServiceInstance.reasonOfError())


class UpdateFromPreparing(StateUpdater):

    def checkOsManagerRelated(self):
        osManager = self.userServiceInstance.osmanager()

        state = State.USABLE

        # and make this usable if os manager says that it is usable, else it pass to configuring state
        # This is an "early check" for os manager, so if we do not have os manager, or os manager
        # already notifies "ready" for this, we
        if osManager is not None and State.isPreparing(self.userService.os_state):
            logger.debug('Has valid osmanager for {}'.format(self.userService.friendly_name))

            stateOs = osManager.checkState(self.userService)
        else:
            stateOs = State.FINISHED

        logger.debug('State {}, StateOS {} for {}'.format(State.toString(state), State.toString(stateOs), self.userService.friendly_name))
        if stateOs == State.RUNNING:
            self.userService.setOsState(State.PREPARING)
        else:
            # If state is finish, we need to notify the userService again that os has finished
            # This will return a new task state, and that one will be the one taken into account
            self.userService.setOsState(State.USABLE)
            rs = self.userServiceInstance.notifyReadyFromOsManager('')
            if rs != State.FINISHED:
                self.checkLater()
                state = self.userService.state  # No not alter current state if after notifying os manager the user service keeps working

        return state

    def finish(self):
        state = State.REMOVABLE  # By default, if not valid publication, service will be marked for removal on preparation finished
        if self.userService.isValidPublication():
            logger.debug('Publication is valid for {}'.format(self.userService.friendly_name))
            state = self.checkOsManagerRelated()

        # Now notifies the service instance that we have finished processing
        if state != self.userService.state:
            self.userServiceInstance.finish()

        self.save(state)


class UpdateFromRemoving(StateUpdater):

    def finish(self):
        osManager = self.userServiceInstance.osmanager()
        if osManager is not None:
            osManager.release(self.userService)

        self.save(State.REMOVED)


class UpdateFromCanceling(StateUpdater):

    def finish(self):
        osManager = self.userServiceInstance.osmanager()
        if osManager is not None:
            osManager.release(self.userService)

        self.save(State.CANCELED)


class UpdateFromOther(StateUpdater):

    def finish(self):
        self.setError('Unknown running transition from {}'.format(State.toString(self.userService.state)))

    def running(self):
        self.setError('Unknown running transition from {}'.format(State.toString(self.userService.state)))


class UserServiceOpChecker(DelayedTask):
    '''
    This is the delayed task responsible of executing the service tasks and the service state transitions
    '''

    def __init__(self, service):
        super(UserServiceOpChecker, self).__init__()
        self._svrId = service.id
        self._state = service.state

    @staticmethod
    def makeUnique(userService, userServiceInstance, state):
        '''
        This method ensures that there will be only one delayedtask related to the userService indicated
        '''
        DelayedTaskRunner.runner().remove(USERSERVICE_TAG + userService.uuid)
        UserServiceOpChecker.checkAndUpdateState(userService, userServiceInstance, state)

    @staticmethod
    def checkAndUpdateState(userService, userServiceInstance, state):
        '''
        Checks the value returned from invocation to publish or checkPublishingState, updating the servicePoolPub database object
        Return True if it has to continue checking, False if finished
        '''
        try:
            # Fills up basic data
            userService.unique_id = userServiceInstance.getUniqueId()  # Updates uniqueId
            userService.friendly_name = userServiceInstance.getName()  # And name, both methods can modify serviceInstance, so we save it later
            userService.save(update_fields=['unique_id', 'friendly_name'])

            updater = {
                State.PREPARING: UpdateFromPreparing,
                State.REMOVING: UpdateFromRemoving,
                State.CANCELING: UpdateFromCanceling
            }.get(userService.state, UpdateFromOther)

            logger.debug('Updating from {} with updater {} and state {}'.format(State.toString(userService.state), updater, state))

            updater(userService, userServiceInstance).run(state)

        except Exception as e:
            logger.exception('Checking service state')
            log.doLog(userService, log.ERROR, 'Exception: {0}'.format(e), log.INTERNAL)
            userService.setState(State.ERROR)
            userService.save(update_fields=['data', 'state', 'state_date'])

    @staticmethod
    def checkLater(userService, ci):
        '''
        Inserts a task in the delayedTaskRunner so we can check the state of this publication
        @param dps: Database object for DeployedServicePublication
        @param pi: Instance of Publication manager for the object
        '''
        # Do not add task if already exists one that updates this service
        if DelayedTaskRunner.runner().checkExists(USERSERVICE_TAG + userService.uuid):
            return
        DelayedTaskRunner.runner().insert(UserServiceOpChecker(userService), ci.suggestedTime, USERSERVICE_TAG + userService.uuid)

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
                uService.save(update_fields=['data', 'state', 'state_date'])
            except Exception:
                logger.error('Can\'t update state of uService object')
