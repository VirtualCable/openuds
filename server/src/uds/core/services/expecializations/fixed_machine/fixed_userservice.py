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
import pickle  # nosec: controled data
import enum
import logging
import typing
import collections.abc

from uds.core import services, consts
from uds.core.managers.user_service import UserServiceManager
from uds.core.types.states import State
from uds.core.util import log, autoserializable
from uds.core.util.model import sql_stamp_seconds

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
    
    _create_queue: typing.ClassVar[typing.List[Operation]] = [Operation.CREATE, Operation.START, Operation.FINISH]
    _destrpy_queue: typing.ClassVar[typing.List[Operation]] = [Operation.REMOVE, Operation.FINISH]

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
    def _push_back_op(self, op) -> None:
        self._queue.append(op)

    @typing.final
    def _retry_later(self) -> str:
        self._push_front_op(Operation.RETRY)
        return State.RUNNING

    def _error(self, reason: typing.Union[str, Exception]) -> str:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        self._queue = [Operation.ERROR]
        self._reason = reason
        return State.ERROR

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
    def deploy_for_user(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._init_queue_for_deploy(False)
        return self._execute_queue()

    @typing.final
    def assign(self, vmid: str) -> str:
        logger.debug('Assigning from VM {}'.format(vmid))
        return self._create(vmid)

    @typing.final
    def _init_queue_for_deploy(self, for_level2: bool = False) -> None:
        self._queue = FixedUserService._create_queue.copy()  # copy is needed to avoid modifying class var

    @typing.final
    def _execute_queue(self) -> str:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.ERROR

        if op == Operation.FINISH:
            return State.FINISHED

        fncs: collections.abc.Mapping[Operation, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.START: self._start_machine,
            Operation.STOP: self._stop_machine,
            Operation.WAIT: self._wait,
            Operation.REMOVE: self._remove,
        }

        try:
            operation_runner: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if not operation_runner:
                return self._error(f'Unknown operation found at execution queue ({op})')

            operation_runner()

            return State.RUNNING
        except Exception as e:
            logger.exception('Unexpected VMware exception: %s', e)
            return self._error(str(e))

    @typing.final
    def _retry(self) -> str:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return State.FINISHED

    @typing.final
    def _wait(self) -> str:
        """
        Executes opWait, it simply waits something "external" to end
        """
        return State.RUNNING

    @typing.final
    def _create(self, vmid: str = '') -> str:
        """
        Deploys a machine from template for user/cache
        """
        self._vmid = vmid or self.service().get_and_assign_machine()
        self._mac = self.service().get_first_network_mac(self._vmid) or ''
        self._name = self.service().get_machine_name(self._vmid) or f'VM-{self._vmid}'

        # Try to process snaptshots if needed
        state = self.service().process_snapshot(remove=False, userservice_instace=self)
        
        if state == State.ERROR:
            return state

        # If not to be managed by a token, "autologin" user
        if not self.service().get_token():
            userService = self.db_obj()
            if userService:
                userService.set_in_use(True)

        return state
    
    @typing.final
    def _remove(self) -> str:
        """
        Removes the snapshot if needed and releases the machine again
        """
        self.service().remove_and_free_machine(self._vmid)

        state = self.service().process_snapshot(remove=True, userservice_instace=self)

        return state

    @abc.abstractmethod
    def _start_machine(self) -> str:
        pass

    @abc.abstractmethod
    def _stop_machine(self) -> str:
        pass

    # Check methods
    def _create_checker(self) -> str:
        """
        Checks the state of a deploy for an user or cache
        """
        return State.FINISHED

    @abc.abstractmethod
    def _start_checker(self) -> str:
        """
        Checks if machine has started
        """
        pass

    @abc.abstractmethod
    def _stop_checker(self) -> str:
        """
        Checks if machine has stoped
        """
        pass

    @abc.abstractmethod
    def _removed_checker(self) -> str:
        """
        Checks if a machine has been removed
        """
        pass

    @typing.final
    def check_state(self) -> str:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.ERROR

        if op == Operation.FINISH:
            return State.FINISHED

        fncs: collections.abc.Mapping[Operation, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create_checker,
            Operation.RETRY: self._retry,
            Operation.WAIT: self._wait,
            Operation.START: self._start_checker,
            Operation.STOP: self._stop_checker,
            Operation.REMOVE: self._removed_checker,
        }

        try:
            check_function: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if check_function is None:
                return self._error('Unknown operation found at check queue ({0})'.format(op))

            state = check_function()
            if state == State.FINISHED:
                self._pop_current_op()  # Remove runing op, till now only was "peek"
                return self._execute_queue()

            return state
        except Exception as e:
            logger.exception('Unexpected VMware exception: %s', e)
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
    def destroy(self) -> str:
        """
        Invoked for destroying a deployed service
        """
        self._queue = FixedUserService._destrpy_queue.copy()  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def cancel(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.
        """
        logger.debug('Canceling %s with taskId=%s, vmId=%s', self._name, self._task, self._vmid)
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
