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
import abc
import logging
import typing

from uds.core import services, types
from uds.core.jobs.delayed_task import DelayedTask
from uds.core.jobs.delayed_task_runner import DelayedTaskRunner
from uds.core.util import log
from uds.models import UserService

logger = logging.getLogger(__name__)

USERSERVICE_TAG = 'cm-'


# State updaters
# This will be executed on current service state for checking transitions to new state, task states, etc..
class StateUpdater(abc.ABC):
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

    def set_error(self, msg: typing.Optional[str] = None) -> None:
        logger.error('Got error on processor: %s', msg)
        self.save(types.states.State.ERROR)
        if msg is not None:
            log.log(self.user_service, log.LogLevel.ERROR, msg, log.LogSource.INTERNAL)

    def save(self, newState: typing.Optional[str] = None) -> None:
        if newState:
            self.user_service.set_state(newState)

        self.user_service.update_data(self.user_service_instance)

    def log_ip(self) -> None:
        ip = self.user_service_instance.get_ip()

        if ip:
            self.user_service.log_ip(ip)

    def check_later(self) -> None:
        UserServiceOpChecker.check_later(self.user_service, self.user_service_instance)

    def run(self, state: types.states.TaskState) -> None:
        # Deployments can olny be on RUNNING, ERROR or FINISHED states
        executor = {
            types.states.TaskState.RUNNING: self.state_running,
            types.states.TaskState.ERROR: self.state_error,
            types.states.TaskState.FINISHED: self.state_finish,
        }.get(state, self.state_error)

        logger.debug(
            'Running Executor for %s with state %s and executor %s',
            self.user_service.friendly_name,
            types.states.State.from_str(state).localized,
            executor,
        )

        try:
            executor()
        except Exception as e:
            self.set_error(f'Exception: {e}')

        logger.debug('Executor for %s done', self.user_service.friendly_name)

    @abc.abstractmethod
    def state_finish(self) -> None:
        raise NotImplementedError()

    def state_running(self) -> None:
        self.save()
        self.check_later()

    def state_error(self) -> None:
        self.set_error(self.user_service_instance.error_reason())


class UpdateFromPreparing(StateUpdater):
    def check_os_manager_related(self) -> types.states.State:
        osmanager = self.user_service_instance.osmanager()

        state: types.states.State = types.states.State.USABLE

        # and make this usable if os manager says that it is usable, else it pass to configuring state
        # This is an "early check" for os manager, so if we do not have os manager, or os manager
        # already notifies "ready" for this, we
        if osmanager is not None and types.states.State.from_str(self.user_service.os_state).is_preparing():
            logger.debug('Has valid osmanager for %s', self.user_service.friendly_name)

            state_os = osmanager.check_state(self.user_service)
        else:
            state_os = types.states.State.FINISHED

        logger.debug(
            'State %s, types.states.State.S %s for %s',
            state.localized,
            state_os.localized,
            self.user_service.friendly_name,
        )
        if state_os == types.states.State.RUNNING:
            self.user_service.set_os_state(types.states.State.PREPARING)
        else:
            # If state is finish, we need to notify the userService again that os has finished
            # This will return a new task state, and that one will be the one taken into account
            self.user_service.set_os_state(types.states.State.USABLE)
            rs = self.user_service_instance.process_ready_from_os_manager('')
            if rs != types.states.TaskState.FINISHED:
                self.check_later()
                # No not alter current state if after notifying os manager the user service keeps working
                state = types.states.State.from_str(self.user_service.state)
            else:
                self.log_ip()

        return state

    def state_finish(self) -> None:
        if self.user_service.destroy_after:  # Marked for destroyal
            del self.user_service.destroy_after  # Cleanup..
            self.save(types.states.State.REMOVABLE)  # And start removing it
            return

        # By default, if not valid publication, service will be marked for removal on preparation finished
        state = types.states.State.REMOVABLE
        if self.user_service.is_publication_valid():
            logger.debug('Publication is valid for %s', self.user_service.friendly_name)
            state = self.check_os_manager_related()

        # Now notifies the service instance that we have finished processing
        if state != self.user_service.state:
            self.user_service_instance.finish()

        self.save(state)


class UpdateFromRemoving(StateUpdater):
    def state_finish(self) -> None:
        osmanager = self.user_service_instance.osmanager()
        if osmanager is not None:
            osmanager.release(self.user_service)

        self.save(types.states.State.REMOVED)


class UpdateFromCanceling(StateUpdater):
    def state_finish(self) -> None:
        osmanager = self.user_service_instance.osmanager()
        if osmanager is not None:
            osmanager.release(self.user_service)

        self.save(types.states.State.CANCELED)


class UpdateFromOther(StateUpdater):
    def state_finish(self) -> None:
        self.set_error(
            f'Unknown running transition from {types.states.State.from_str(self.user_service.state).localized}'
        )

    def state_running(self) -> None:
        self.set_error(
            f'Unknown running transition from {types.states.State.from_str(self.user_service.state).localized}'
        )


class UserServiceOpChecker(DelayedTask):
    """
    This is the delayed task responsible of executing the service tasks and the service state transitions
    """

    _svrId: int
    _state: str

    def __init__(self, service: 'UserService'):
        super().__init__()
        self._svrId = service.id
        self._state = service.state

    @staticmethod
    def make_unique(
        userservice: UserService, userservice_instance: services.UserService, state: types.states.TaskState
    ) -> None:
        """
        This method ensures that there will be only one delayedtask related to the userService indicated
        """
        DelayedTaskRunner.runner().remove(USERSERVICE_TAG + userservice.uuid)
        UserServiceOpChecker.state_updater(userservice, userservice_instance, state)

    @staticmethod
    def state_updater(
        userservice: UserService, userservice_instance: services.UserService, state: types.states.TaskState
    ) -> None:
        """
        Checks the value returned from invocation to publish or checkPublishingState, updating the servicePoolPub database object
        Return True if it has to continue checking, False if finished
        """
        try:
            # Fills up basic data
            userservice.unique_id = userservice_instance.get_unique_id()  # Updates uniqueId
            userservice.friendly_name = (
                userservice_instance.get_name()
            )  # And name, both methods can modify serviceInstance, so we save it later
            userservice.save(update_fields=['unique_id', 'friendly_name'])

            updater = typing.cast(
                type[StateUpdater],
                {
                    types.states.State.PREPARING: UpdateFromPreparing,
                    types.states.State.REMOVING: UpdateFromRemoving,
                    types.states.State.CANCELING: UpdateFromCanceling,
                }.get(types.states.State.from_str(userservice.state), UpdateFromOther),
            )

            logger.debug(
                'Updating %s from %s with updater %s and state %s',
                userservice.friendly_name,
                types.states.State.from_str(userservice.state).localized,
                updater,
                state,
            )

            updater(userservice, userservice_instance).run(state)

        except Exception as e:
            logger.exception('Checking service state')
            log.log(userservice, log.LogLevel.ERROR, f'Exception: {e}', log.LogSource.INTERNAL)
            userservice.set_state(types.states.State.ERROR)
            userservice.save(update_fields=['data'])

    @staticmethod
    def check_later(userservice: 'UserService', instance: 'services.UserService') -> None:
        """
        Inserts a task in the delayedTaskRunner so we can check the state of this service later
        @param dps: Database object for ServicePoolPublication
        @param pi: Instance of Publication manager for the object
        """
        # Do not add task if already exists one that updates this service
        if DelayedTaskRunner.runner().tag_exists(USERSERVICE_TAG + userservice.uuid):
            return
        DelayedTaskRunner.runner().insert(
            UserServiceOpChecker(userservice),
            instance.suggested_delay,
            USERSERVICE_TAG + userservice.uuid,
        )

    def run(self) -> None:
        logger.debug('Checking user service finished %s', self._svrId)
        userservice: 'UserService|None' = None
        try:
            userservice = typing.cast(
                UserService, UserService.objects.get(pk=self._svrId)
            )  # pyright: ignore reportUnnecessaryCast
            if userservice.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
                # This item is no longer valid, returning will not check it again (no checkLater called)
                return
            ci = userservice.get_instance()
            logger.debug("uService instance class: %s", ci.__class__)
            state = ci.check_state()
            UserServiceOpChecker.state_updater(userservice, ci, state)
        except UserService.DoesNotExist as e:  # pylint: disable=no-member
            logger.error('User service not found (erased from database?) %s : %s', e.__class__, e)
        except Exception as e:
            # Exception caught, mark service as errored
            logger.exception("Error %s, %s :", e.__class__, e)
            if userservice:
                log.log(userservice, log.LogLevel.ERROR, f'Exception: {e}', log.LogSource.INTERNAL)
                try:
                    userservice.set_state(types.states.State.ERROR)
                    userservice.save(update_fields=['data'])
                except Exception:
                    logger.error('Can\'t update state of uService object')
