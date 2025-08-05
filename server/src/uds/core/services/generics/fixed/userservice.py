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
import abc
import logging
import typing
import collections.abc

from uds.core import consts, services, types, exceptions
from uds.core.util import autoserializable


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from . import service

logger = logging.getLogger(__name__)


class FixedUserService(services.UserService, autoserializable.AutoSerializable, abc.ABC):
    """
    This class represents a fixed user service, that is, a service that is assigned to an user
    and that will be always the from a "fixed" machine, that is, a machine that is not created.

    Note that only support a subset of operations, that are:
        - CREATE
        - START
        - STOP
        - DELETE
        - SNAPSHOT_CREATE
        - SNAPSHOT_RECOVER
        - PROCESS_TOKEN
        - SHUTDOWN
        - NOP
        - RETRY
        - ERROR
        - FINISH
    """

    suggested_delay = consts.services.USRV_FIXED_SUGGESTED_CHECK_INTERVAL
    # How many times we will check for a state before giving up
    max_state_checks: typing.ClassVar[int] = consts.services.USRV_MAX_STATE_CHECKS
    # How many "retries" operation on same state will be allowed before giving up
    max_retries: typing.ClassVar[int] = consts.services.USRV_MAX_RETRIES

    _name = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _task = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[types.services.Operation](cast=types.services.Operation.from_int)

    # Note that even if SNAPHSHOT operations are in middel
    # implementations may opt to no have snapshots at all
    # In this case, the default service snapshot methods will handle this (default to do nothing)
    _create_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.CREATE,
        types.services.Operation.SNAPSHOT_CREATE,
        types.services.Operation.PROCESS_TOKEN,
        types.services.Operation.START,
        types.services.Operation.FINISH,
    ]
    _destroy_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.DELETE,
        types.services.Operation.SNAPSHOT_RECOVER,
        types.services.Operation.FINISH,
    ]
    _assign_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.CREATE,
        types.services.Operation.SNAPSHOT_CREATE,
        types.services.Operation.PROCESS_TOKEN,
        types.services.Operation.FINISH,
    ]

    @typing.final
    def _current_op(self) -> types.services.Operation:
        if not self._queue:
            return types.services.Operation.FINISH

        return self._queue[0]

    @typing.final
    def _set_queue(self, queue: list[types.services.Operation]) -> None:
        """
        Sets the queue of tasks to be executed
        Ensures that we mark it as new format
        """
        self._queue = queue

    @typing.final
    def _reset_checks_counter(self) -> None:
        with self.storage.as_dict() as data:
            data['exec_count'] = 0

    @typing.final
    def _inc_checks_counter(self, info: typing.Optional[str] = None) -> typing.Optional[types.states.TaskState]:
        with self.storage.as_dict() as data:
            count = data.get('exec_count', 0) + 1
            data['exec_count'] = count
        if count > self.max_state_checks:
            return self.error(f'Max checks reached on {info or "unknown"}')
        return None

    @typing.final
    def _reset_retries_counter(self) -> None:
        with self.storage.as_dict() as data:
            data['retries'] = 0

    @typing.final
    def _inc_retries_counter(self) -> typing.Optional[types.states.TaskState]:
        with self.storage.as_dict() as data:
            retries = data.get('retries', 0) + 1
            data['retries'] = retries

        if retries > self.max_retries:  # get "own class" max retries
            return self.error(f'Max retries reached')

        return None

    @typing.final
    def error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s (%s)', reason, self._queue, stack_info=True, stacklevel=3)
        self.do_log(types.log.LogLevel.ERROR, reason)

        if self._vmid:
            if self.service().should_maintain_on_error() is False:
                try:
                    self.service().remove_and_free(self._vmid)
                    self.service().snapshot_recovery(userservice_instance=self)
                    self._vmid = ''
                except Exception as e:
                    logger.exception('Exception removing machine: %s', e)
            else:
                logger.debug('Keep on error is enabled, not removing machine')
                self._queue = [types.services.Operation.FINISH]
                return types.states.TaskState.FINISHED

        self._queue = [types.services.Operation.ERROR]
        self._reason = reason
        return types.states.TaskState.ERROR

    @typing.final
    def _execute_queue(self) -> types.states.TaskState:
        self._debug('executeQueue')
        op = self._current_op()

        if op == types.services.Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == types.services.Operation.FINISH:
            return types.states.TaskState.FINISHED

        try:
            self._reset_checks_counter()  # Reset checks counter

            operation_runner = _EXECUTORS[op]

            # Invoke using instance, we have overrided methods
            # and we want to use the overrided ones
            getattr(self, operation_runner.__name__)()

            return types.states.TaskState.RUNNING
        except exceptions.services.generics.RetryableError as e:
            # This is a retryable error, so we will retry later
            return self.retry_later()
        except Exception as e:
            logger.exception('Unexpected FixedUserService exception: %s', e)
            return self.error(str(e))

    @typing.final
    def retry_later(self) -> types.states.TaskState:
        """
        Retries the current operation
        For this, we insert a RETRY that will be:
            - If used from a "executor" method, will invoke the "retry_checker" method
            - If used from a "checker" method, will be consumed, and the operation will be retried
        In any case, if we overpass the max retries, we will set the machine to error state
        """
        if self._inc_retries_counter() is not None:
            return self.error('Max retries reached')
        self._queue.insert(0, types.services.Operation.RETRY)
        return types.states.TaskState.FINISHED

    # Utility overrides for type checking...
    # Probably, overriden again on child classes
    def service(self) -> 'service.FixedService':
        return typing.cast('service.FixedService', super().service())

    @typing.final
    def get_name(self) -> str:
        return self._name

    @typing.final
    def set_ip(self, ip: str) -> None:
        logger.debug('Setting IP to %s (ignored!!)', ip)

    @typing.final
    def get_unique_id(self) -> str:
        return self._mac or self._name

    @typing.final
    def get_ip(self) -> str:
        try:
            if self._vmid:
                return self.service().get_ip(self._vmid)
        except exceptions.services.generics.NotFoundError:
            self.do_log(types.log.LogLevel.ERROR, f'Machine not found: {self._vmid}::{self._name}')

        except Exception:  # No ip already assigned, wait...
            pass
        return ''

    @typing.final
    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._vmid = self.service().get_and_assign()
        # copy is needed to avoid modifying class var, and access using instance allowing to get, if provided, overriden queue
        self._queue = self._create_queue.copy()
        return self._execute_queue()

    @typing.final
    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        """
        Fixed Userservice does not provided "cached" elements
        """
        return self.error('Cache for fixed userservices not supported')

    def process_ready_from_os_manager(self, data: typing.Any) -> types.states.TaskState:
        """
        By default, process ready from os manager will return finished for most of the fixed services
        So we provide a default implementation here
        """
        return types.states.TaskState.FINISHED

    def set_ready(self) -> types.states.TaskState:
        # If already ready, return finished
        try:
            if self.cache.get('ready', '0') == '1':
                self._queue = [types.services.Operation.FINISH]
            elif self.service().is_ready(self._vmid):
                self.cache.set('ready', '1', consts.cache.SHORT_CACHE_TIMEOUT // 2)  # short cache timeout
                self._queue = [types.services.Operation.FINISH]
            else:
                self._queue = [types.services.Operation.START, types.services.Operation.FINISH]
        except exceptions.services.generics.NotFoundError:
            return self.error('Machine not found')
        except Exception as e:
            return self.error(f'Error on set_ready: {e}')
        return self._execute_queue()

    @typing.final
    def assign(self, vmid: str) -> types.states.TaskState:
        logger.debug('Assigning from VM {}'.format(vmid))
        self._vmid = vmid
        self._queue = FixedUserService._assign_queue.copy()  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def check_state(self) -> types.states.TaskState:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._current_op()

        if op == types.services.Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == types.services.Operation.FINISH:
            return types.states.TaskState.FINISHED

        # All operations except WAIT will check against checks counter
        # but, due to the fact that WAIT is a NOP, we will not check for WAIT operations
        # (not present on fixed services, because do not have cache 2, so no need to wait)
        counter_state = self._inc_checks_counter(self._op2str(op))
        if counter_state is not None:
            return counter_state  # Error or None

        try:
            check_function = _CHECKERS[op]  # If some operation not supported, will raise exception

            # Invoke using instance, we have overrided methods
            # and we want to use the overrided ones
            state = typing.cast(types.states.TaskState, getattr(self, check_function.__name__)())

            if state == types.states.TaskState.FINISHED:
                top_op = self._queue.pop(0)  # Remove finished op
                # And reset retries counter, if needed
                if top_op != types.services.Operation.RETRY:
                    self._reset_retries_counter()
                return self._execute_queue()

            return state
        except exceptions.services.generics.RetryableError as e:
            # This is a retryable error, so we will retry later
            # We don not need to push a NOP here, as we will retry the same operation checking again
            # And it has not been removed from the queue
            return types.states.TaskState.RUNNING
        except exceptions.services.generics.NotFoundError as e:
            return self.error(f'Machine not found ({e})')
        except Exception as e:
            logger.exception('Unexpected UserService check exception: %s', e)
            return self.error(e)

    @typing.final
    def op_nop(self) -> None:
        """
        Does nothing
        """
        pass

    @typing.final
    def op_create(self) -> None:
        """
        Deploys a machine from template for user/cache
        """
        self._mac = self.service().get_mac(self._vmid) or ''
        self._name = self.service().get_name(self._vmid) or f'VM-{self._vmid}'

    @typing.final
    def op_snapshot_create(self) -> None:
        """
        Creates a snapshot if needed
        """
        # Try to process snaptshots if needed
        self.service().snapshot_creation(userservice_instance=self)

    @typing.final
    def op_snapshot_recover(self) -> None:
        """
        Recovers a snapshot if needed
        """
        self.service().snapshot_recovery(userservice_instance=self)

    @typing.final
    def op_process_token(self) -> None:
        # If not to be managed by a token, "autologin" user
        if not self.service().get_token():
            userservice = self.db_obj()
            if userservice:
                userservice.set_in_use(True)

    def op_delete(self) -> None:
        """
        Removes the snapshot if needed and releases the machine again
        """
        self.service().remove_and_free(self._vmid)

    # Check methods
    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        return types.states.TaskState.FINISHED

    def op_snapshot_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a snapshot creation
        """
        return types.states.TaskState.FINISHED

    def op_snapshot_recover_checker(self) -> types.states.TaskState:
        """
        Checks the state of a snapshot recovery
        """
        return types.states.TaskState.FINISHED

    def op_process_token_checker(self) -> types.states.TaskState:
        """
        Checks the state of a token processing
        """
        return types.states.TaskState.FINISHED

    def op_nop_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    @typing.final
    def op_retry_checker(self) -> types.states.TaskState:
        # If max retrieas has beeen reached, error should already have been set
        if self._queue[0] == types.services.Operation.ERROR:
            return types.states.TaskState.ERROR
        return types.states.TaskState.FINISHED

    def op_start(self) -> None:
        """
        Override this method to start the machine if needed
        """
        pass

    def op_start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        Defaults to is_ready method from service
        """
        if self.service().is_running(self._vmid):
            return types.states.TaskState.FINISHED
        return types.states.TaskState.RUNNING

    def op_stop(self) -> None:
        """
        Override this method to stop the machine if needed
        """
        pass

    def op_stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        Default to is_ready method from service
        """
        if not self.service().is_running(self._vmid):
            return types.states.TaskState.FINISHED
        return types.states.TaskState.RUNNING

    # Not abstract methods, defaults to stop machine
    def op_shutdown(self) -> None:
        """ """
        return self.op_stop()  # Default is to stop the machine

    def op_shutdown_checker(self) -> types.states.TaskState:
        return self.op_stop_checker()  # Default is to check if machine has stopped

    def op_deleted_checker(self) -> types.states.TaskState:
        """
        Checks if a machine has been removed
        """
        return types.states.TaskState.FINISHED

    @typing.final
    def finish(self) -> None:
        """
        Invoked when the core notices that the deployment of a service has finished.
        (No matter wether it is for cache or for an user)
        """
        logger.debug('Finished machine %s', self._name)

    @typing.final
    def error_reason(self) -> str:
        """
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).
        """
        return self._reason

    @typing.final
    def destroy(self) -> types.states.TaskState:
        """
        Invoked for destroying a deployed service
        """
        self._queue = FixedUserService._destroy_queue.copy()  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def cancel(self) -> types.states.TaskState:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.
        """
        logger.debug('Canceling %s with taskid=%s, vmid=%s', self._name, self._task, self._vmid)
        return self.destroy()

    @staticmethod
    def _op2str(op: types.services.Operation) -> str:
        return op.name

    def _debug(self, txt: str) -> None:
        # logger.debug('_name {0}: {1}'.format(txt, self._name))
        # logger.debug('_ip {0}: {1}'.format(txt, self._ip))
        # logger.debug('_mac {0}: {1}'.format(txt, self._mac))
        # logger.debug('_vmId {0}: {1}'.format(txt, self._vmId))
        logger.debug(
            'Queue at %s for %s: %s, mac:%s, vmid:%s, task:%s',
            txt,
            self._name,
            [FixedUserService._op2str(op) for op in self._queue],
            self._mac,
            self._vmid,
            self._task,
        )


# This is a map of operations to methods
# types.services.Operations, duwe to the fact that can be overrided some of them, must be invoked via instance
# We use __name__ later to use them, so we can use type checking and invoke them via instance instead of class
# Note that ERROR and FINISH are not here, as they final states not needing to be executed
_EXECUTORS: typing.Final[
    collections.abc.Mapping[types.services.Operation, collections.abc.Callable[[FixedUserService], None]]
] = {
    types.services.Operation.CREATE: FixedUserService.op_create,
    types.services.Operation.START: FixedUserService.op_start,
    types.services.Operation.STOP: FixedUserService.op_stop,
    types.services.Operation.DELETE: FixedUserService.op_delete,
    types.services.Operation.SNAPSHOT_CREATE: FixedUserService.op_snapshot_create,
    types.services.Operation.SNAPSHOT_RECOVER: FixedUserService.op_snapshot_recover,
    types.services.Operation.PROCESS_TOKEN: FixedUserService.op_process_token,
    types.services.Operation.SHUTDOWN: FixedUserService.op_shutdown,
    types.services.Operation.NOP: FixedUserService.op_nop,
    # Retry operation has no executor, look "retry_later" method
}

# Same af before, but for check methods
_CHECKERS: typing.Final[
    collections.abc.Mapping[types.services.Operation, collections.abc.Callable[[FixedUserService], types.states.TaskState]]
] = {
    types.services.Operation.CREATE: FixedUserService.op_create_checker,
    types.services.Operation.START: FixedUserService.op_start_checker,
    types.services.Operation.STOP: FixedUserService.op_stop_checker,
    types.services.Operation.DELETE: FixedUserService.op_deleted_checker,
    types.services.Operation.SNAPSHOT_CREATE: FixedUserService.op_snapshot_create_checker,
    types.services.Operation.SNAPSHOT_RECOVER: FixedUserService.op_snapshot_recover_checker,
    types.services.Operation.PROCESS_TOKEN: FixedUserService.op_process_token_checker,
    types.services.Operation.SHUTDOWN: FixedUserService.op_shutdown_checker,
    types.services.Operation.NOP: FixedUserService.op_nop_checker,
    # Retry operation can be inserted by a executor, so it will need a checker
    types.services.Operation.RETRY: FixedUserService.op_retry_checker,
}
