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
import enum
import logging
import typing
import collections.abc

from uds.core import services, types
from uds.core.util import log, autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from . import fixed_service

logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    CREATE = 0
    START = 1
    STOP = 2
    REMOVE = 3
    WAIT = 4
    ERROR = 5
    FINISH = 6
    RETRY = 7
    SNAPSHOT_CREATE = 8  # to recall process_snapshot
    SNAPSHOT_RECOVER = 9  # to recall process_snapshot
    PROCESS_TOKEN = 10
    SOFT_SHUTDOWN = 11

    NOP = 98
    UNKNOWN = 99

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.UNKNOWN


class FixedUserService(services.UserService, autoserializable.AutoSerializable, abc.ABC):
    """
    This class represents a fixed user service, that is, a service that is assigned to an user
    and that will be always the from a "fixed" machine, that is, a machine that is not created.
    """

    suggested_delay = 4

    _name = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _task = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()  # Default is empty list

    _create_queue: typing.ClassVar[list[Operation]] = [
        Operation.CREATE,
        Operation.SNAPSHOT_CREATE,
        Operation.PROCESS_TOKEN,
        Operation.START,
        Operation.FINISH,
    ]
    _destroy_queue: typing.ClassVar[list[Operation]] = [
        Operation.REMOVE,
        Operation.SNAPSHOT_RECOVER,
        Operation.FINISH,
    ]
    _assign_queue: typing.ClassVar[list[Operation]] = [
        Operation.CREATE,
        Operation.SNAPSHOT_CREATE,
        Operation.PROCESS_TOKEN,
        Operation.FINISH,
    ]

    @typing.final
    def _get_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    @typing.final
    def _pop_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue.pop(0)

    @typing.final
    def _push_front_op(self, op: Operation) -> None:
        self._queue.insert(0, op)

    @typing.final
    def _push_back_op(self, op: Operation) -> None:
        self._queue.append(op)

    @typing.final
    def _retry_later(self) -> str:
        self._push_front_op(Operation.RETRY)
        return types.states.TaskState.RUNNING

    def _error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid:
            try:
                self.service().remove_and_free_machine(self._vmid)
                self.service().process_snapshot(remove=True, userservice_instance=self)
                self._vmid = ''
            except Exception as e:
                logger.exception('Exception removing machine: %s', e)

        self._queue = [Operation.ERROR]
        self._reason = reason
        return types.states.TaskState.ERROR

    # Utility overrides for type checking...
    # Probably, overriden again on child classes
    def service(self) -> 'fixed_service.FixedService':
        return typing.cast('fixed_service.FixedService', super().service())

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
                return self.service().get_guest_ip_address(self._vmid)
        except Exception:
            pass
        return ''

    @typing.final
    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._vmid = self.service().get_and_assign_machine()
        self._queue = FixedUserService._create_queue.copy()  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def assign(self, vmid: str) -> types.states.TaskState:
        logger.debug('Assigning from VM {}'.format(vmid))
        self._vmid = vmid
        self._queue = FixedUserService._assign_queue.copy()  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def _execute_queue(self) -> types.states.TaskState:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        fncs: dict[Operation, collections.abc.Callable[[], None]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.START: self._start_machine,
            Operation.STOP: self._stop_machine,
            Operation.WAIT: self._wait,
            Operation.REMOVE: self._remove,
            Operation.SNAPSHOT_CREATE: self._snapshot_create,
            Operation.SNAPSHOT_RECOVER: self._snapshot_recover,
            Operation.PROCESS_TOKEN: self._process_token,
            Operation.SOFT_SHUTDOWN: self._soft_shutdown_machine,
            Operation.NOP: self._nop,
        }

        try:
            operation_runner: typing.Optional[collections.abc.Callable[[], None]] = fncs.get(op, None)

            if not operation_runner:
                return self._error(f'Unknown operation found at execution queue ({op})')

            operation_runner()

            return types.states.TaskState.RUNNING
        except Exception as e:
            logger.exception('Unexpected FixedUserService exception: %s', e)
            return self._error(str(e))

    @typing.final
    def _retry(self) -> None:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        pass

    @typing.final
    def _wait(self) -> None:
        """
        Executes opWait, it simply waits something "external" to end
        """
        pass

    @typing.final
    def _nop(self) -> None:
        """
        Executes opWait, it simply waits something "external" to end
        """
        pass

    @typing.final
    def _create(self) -> None:
        """
        Deploys a machine from template for user/cache
        """
        self._mac = self.service().get_first_network_mac(self._vmid) or ''
        self._name = self.service().get_machine_name(self._vmid) or f'VM-{self._vmid}'

    @typing.final
    def _snapshot_create(self) -> None:
        """
        Creates a snapshot if needed
        """
        # Try to process snaptshots if needed
        self.service().process_snapshot(remove=False, userservice_instance=self)

    @typing.final
    def _snapshot_recover(self) -> None:
        """
        Recovers a snapshot if needed
        """
        self.service().process_snapshot(remove=True, userservice_instance=self)

    @typing.final
    def _process_token(self) -> None:
        # If not to be managed by a token, "autologin" user
        if not self.service().get_token():
            userservice = self.db_obj()
            if userservice:
                userservice.set_in_use(True)

    def _remove(self) -> None:
        """
        Removes the snapshot if needed and releases the machine again
        """
        self.service().remove_and_free_machine(self._vmid)

    # Check methods
    def _create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        return types.states.TaskState.FINISHED

    def _snapshot_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a snapshot creation
        """
        return types.states.TaskState.FINISHED

    def _snapshot_recover_checker(self) -> types.states.TaskState:
        """
        Checks the state of a snapshot recovery
        """
        return types.states.TaskState.FINISHED

    def _process_token_checker(self) -> types.states.TaskState:
        """
        Checks the state of a token processing
        """
        return types.states.TaskState.FINISHED

    def _retry_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def _wait_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def _nop_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def _start_machine(self) -> None:
        """ 
        Override this method to start the machine if needed
        """
        pass

    def _start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return types.states.TaskState.FINISHED

    def _stop_machine(self) -> None:
        """
        Override this method to stop the machine if needed
        """
        pass

    def _stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        """
        return types.states.TaskState.FINISHED

    # Not abstract methods, defaults to stop machine
    def _soft_shutdown_machine(self) -> None:
        """
        """
        return self._stop_machine()  # Default is to stop the machine

    def _soft_shutdown_checker(self) -> types.states.TaskState:
        return self._stop_checker()  # Default is to check if machine has stopped

    def _removed_checker(self) -> types.states.TaskState:
        """
        Checks if a machine has been removed
        """
        return types.states.TaskState.FINISHED

    @typing.final
    def check_state(self) -> types.states.TaskState:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        FNCS: typing.Final[dict[Operation, collections.abc.Callable[[], types.states.TaskState]]] = {
            Operation.CREATE: self._create_checker,
            Operation.RETRY: self._retry_checker,
            Operation.WAIT: self._wait_checker,
            Operation.START: self._start_checker,
            Operation.STOP: self._stop_checker,
            Operation.REMOVE: self._removed_checker,
            Operation.SNAPSHOT_CREATE: self._snapshot_create_checker,
            Operation.SNAPSHOT_RECOVER: self._snapshot_recover_checker,
            Operation.PROCESS_TOKEN: self._process_token_checker,
            Operation.SOFT_SHUTDOWN: self._soft_shutdown_checker,
            Operation.NOP: self._nop_checker,
        }

        try:
            check_function: typing.Optional[collections.abc.Callable[[], types.states.TaskState]] = FNCS.get(op, None)

            if check_function is None:
                return self._error('Unknown operation found at check queue ({0})'.format(op))

            state = check_function()
            if state == types.states.TaskState.FINISHED:
                self._pop_current_op()  # Remove runing op, till now only was "peek"
                return self._execute_queue()

            return state
        except Exception as e:
            logger.exception('Unexpected UserService check exception: %s', e)
            return self._error(str(e))

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
    def _op2str(op: Operation) -> str:
        return {
            Operation.CREATE: 'create',
            Operation.START: 'start',
            Operation.STOP: 'stop',
            Operation.REMOVE: 'remove',
            Operation.WAIT: 'wait',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
            Operation.SNAPSHOT_CREATE: 'snapshot_create',
            Operation.SNAPSHOT_RECOVER: 'snapshot_recover',
            Operation.PROCESS_TOKEN: 'process_token',
        }.get(op, '????')

    def _debug(self, txt: str) -> None:
        # logger.debug('_name {0}: {1}'.format(txt, self._name))
        # logger.debug('_ip {0}: {1}'.format(txt, self._ip))
        # logger.debug('_mac {0}: {1}'.format(txt, self._mac))
        # logger.debug('_vmId {0}: {1}'.format(txt, self._vmId))
        logger.debug(
            'Queue at %s for %s: %s, mac:%s, vmId:%s, task:%s',
            txt,
            self._name,
            [FixedUserService._op2str(op) for op in self._queue],
            self._mac,
            self._vmid,
            self._task,
        )
