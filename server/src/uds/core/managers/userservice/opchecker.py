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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from uds.core import services
from uds.core.jobs.delayed_task import DelayedTask
from uds.core.jobs.delayed_task_runner import DelayedTaskRunner
from uds.core.util import log
from uds.core.util.state import State
from uds.models import UserService

logger = logging.getLogger(__name__)

USERSERVICE_TAG = 'cm-'


# State updaters
# This will be executed on current service state for checking transitions to new state, task states, etc..
class StateUpdater:
    user_service: UserService
    user_service_instance: services.UserService

    def __init__(
        self,
        userService: UserService,
        userServiceInstance: typing.Optional[services.UserService] = None,
    ):
        self.user_service = userService
        self.user_service_instance = (
            userServiceInstance if userServiceInstance is not None else userService.get_instance()
        )

    def set_error(self, msg: typing.Optional[str] = None):
        logger.error('Got error on processor: %s', msg)
        self.save(State.ERROR)
        if msg is not None:
            log.log(self.user_service, log.LogLevel.ERROR, msg, log.LogSource.INTERNAL)

    def save(self, newState: typing.Optional[str] = None):
        if newState:
            self.user_service.set_state(newState)

        self.user_service.updateData(self.user_service_instance)

    def log_ip(self):
        ip = self.user_service_instance.get_ip()

        if ip is not None and ip != '':
            self.user_service.log_ip(ip)

    def check_later(self):
        UserServiceOpChecker.check_later(self.user_service, self.user_service_instance)

    def run(self, state):
        executor = {
            State.RUNNING: self.running,
            State.ERROR: self.error,
            State.FINISHED: self.finish,
        }.get(state, self.error)

        logger.debug(
            'Running Executor for %s with state %s and executor %s',
            self.user_service.friendly_name,
            State.as_str(state),
            executor,
        )

        try:
            executor()
        except Exception as e:
            self.set_error(f'Exception: {e}')

        logger.debug('Executor for %s done', self.user_service.friendly_name)

    def finish(self):
        raise NotImplementedError()

    def running(self):
        self.save()
        self.check_later()

    def error(self):
        self.set_error(self.user_service_instance.error_reason())


class UpdateFromPreparing(StateUpdater):
    def check_os_manager_related(self) -> str:
        osManager = self.user_service_instance.osmanager()

        state = State.USABLE

        # and make this usable if os manager says that it is usable, else it pass to configuring state
        # This is an "early check" for os manager, so if we do not have os manager, or os manager
        # already notifies "ready" for this, we
        if osManager is not None and State.is_preparing(self.user_service.os_state):
            logger.debug('Has valid osmanager for %s', self.user_service.friendly_name)

            stateOs = osManager.check_state(self.user_service)
        else:
            stateOs = State.FINISHED

        logger.debug(
            'State %s, StateOS %s for %s',
            State.as_str(state),
            State.as_str(stateOs),
            self.user_service.friendly_name,
        )
        if stateOs == State.RUNNING:
            self.user_service.setOsState(State.PREPARING)
        else:
            # If state is finish, we need to notify the userService again that os has finished
            # This will return a new task state, and that one will be the one taken into account
            self.user_service.setOsState(State.USABLE)
            rs = self.user_service_instance.process_ready_from_os_manager('')
            if rs != State.FINISHED:
                self.check_later()
                state = (
                    self.user_service.state
                )  # No not alter current state if after notifying os manager the user service keeps working
            else:
                self.log_ip()

        return state

    def finish(self):
        if self.user_service.destroy_after:  # Marked for destroyal
            del self.user_service.destroy_after  # Cleanup..
            self.save(State.REMOVABLE)  # And start removing it
            return

        # By default, if not valid publication, service will be marked for removal on preparation finished
        state = State.REMOVABLE
        if self.user_service.check_publication_validity():
            logger.debug('Publication is valid for %s', self.user_service.friendly_name)
            state = self.check_os_manager_related()

        # Now notifies the service instance that we have finished processing
        if state != self.user_service.state:
            self.user_service_instance.finish()

        self.save(state)


class UpdateFromRemoving(StateUpdater):
    def finish(self):
        osManager = self.user_service_instance.osmanager()
        if osManager is not None:
            osManager.release(self.user_service)

        self.save(State.REMOVED)


class UpdateFromCanceling(StateUpdater):
    def finish(self):
        osManager = self.user_service_instance.osmanager()
        if osManager is not None:
            osManager.release(self.user_service)

        self.save(State.CANCELED)


class UpdateFromOther(StateUpdater):
    def finish(self):
        self.set_error(f'Unknown running transition from {State.as_str(self.user_service.state)}')

    def running(self):
        self.set_error(f'Unknown running transition from {State.as_str(self.user_service.state)}')


class UserServiceOpChecker(DelayedTask):
    """
    This is the delayed task responsible of executing the service tasks and the service state transitions
    """

    def __init__(self, service):
        super().__init__()
        self._svrId = service.id
        self._state = service.state

    @staticmethod
    def make_unique(userService: UserService, userServiceInstance: services.UserService, state: str):
        """
        This method ensures that there will be only one delayedtask related to the userService indicated
        """
        DelayedTaskRunner.runner().remove(USERSERVICE_TAG + userService.uuid)
        UserServiceOpChecker.state_updater(userService, userServiceInstance, state)

    @staticmethod
    def state_updater(userService: UserService, userServiceInstance: services.UserService, state: str):
        """
        Checks the value returned from invocation to publish or checkPublishingState, updating the servicePoolPub database object
        Return True if it has to continue checking, False if finished
        """
        try:
            # Fills up basic data
            userService.unique_id = userServiceInstance.get_unique_id()  # Updates uniqueId
            userService.friendly_name = (
                userServiceInstance.get_name()
            )  # And name, both methods can modify serviceInstance, so we save it later
            userService.save(update_fields=['unique_id', 'friendly_name'])

            updater = typing.cast(
                type[StateUpdater],
                {
                    State.PREPARING: UpdateFromPreparing,
                    State.REMOVING: UpdateFromRemoving,
                    State.CANCELING: UpdateFromCanceling,
                }.get(userService.state, UpdateFromOther),
            )

            logger.debug(
                'Updating %s from %s with updater %s and state %s',
                userService.friendly_name,
                State.as_str(userService.state),
                updater,
                state,
            )

            updater(userService, userServiceInstance).run(state)

        except Exception as e:
            logger.exception('Checking service state')
            log.log(userService, log.LogLevel.ERROR, f'Exception: {e}', log.LogSource.INTERNAL)
            userService.set_state(State.ERROR)
            userService.save(update_fields=['data'])

    @staticmethod
    def check_later(userService, ci):
        """
        Inserts a task in the delayedTaskRunner so we can check the state of this publication
        @param dps: Database object for ServicePoolPublication
        @param pi: Instance of Publication manager for the object
        """
        # Do not add task if already exists one that updates this service
        if DelayedTaskRunner.runner().tag_exists(USERSERVICE_TAG + userService.uuid):
            return
        DelayedTaskRunner.runner().insert(
            UserServiceOpChecker(userService),
            ci.suggested_delay,
            USERSERVICE_TAG + userService.uuid,
        )

    def run(self) -> None:
        logger.debug('Checking user service finished %s', self._svrId)
        user_service: 'UserService|None' = None
        try:
            user_service = typing.cast(UserService, UserService.objects.get(pk=self._svrId))
            if user_service.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
                # This item is no longer valid, returning will not check it again (no checkLater called)
                return
            ci = user_service.get_instance()
            logger.debug("uService instance class: %s", ci.__class__)
            state = ci.check_state()
            UserServiceOpChecker.state_updater(user_service, ci, state)
        except UserService.DoesNotExist as e:  # pylint: disable=no-member
            logger.error('User service not found (erased from database?) %s : %s', e.__class__, e)
        except Exception as e:
            # Exception caught, mark service as errored
            logger.exception("Error %s, %s :", e.__class__, e)
            if user_service:
                log.log(user_service, log.LogLevel.ERROR, f'Exception: {e}', log.LogSource.INTERNAL)
                try:
                    user_service.set_state(State.ERROR)
                    user_service.save(update_fields=['data'])
                except Exception:
                    logger.error('Can\'t update state of uService object')
