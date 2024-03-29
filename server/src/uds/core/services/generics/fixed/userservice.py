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

from uds.core import services, types
from uds.core.types.services import FixedOperation as Operation
from uds.core.util import log, autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from . import service

logger = logging.getLogger(__name__)


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

    # Note that even if SNAPHSHOT operations are in middel
    # implementations may opt to no have snapshots at all
    # In this case, the process_snapshot method will do nothing
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
    def _current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    @typing.final
    def _retry_later(self) -> str:
        self._queue.insert(0, Operation.RETRY)
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
        # copy is needed to avoid modifying class var, and access using instance allowing to get, if provided, overriden queue
        self._queue = self._create_queue.copy()
        return self._execute_queue()
    
    @typing.final
    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        """
        Fixed Userservice does not provided "cached" elements
        """
        return self._error('Cache not supported')

    @typing.final
    def assign(self, vmid: str) -> types.states.TaskState:
        logger.debug('Assigning from VM {}'.format(vmid))
        self._vmid = vmid
        self._queue = FixedUserService._assign_queue.copy()  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def _execute_queue(self) -> types.states.TaskState:
        self._debug('executeQueue')
        op = self._current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        try:
            operation_runner = _EXEC_FNCS[op]

            # Invoke using instance, we have overrided methods
            # and we want to use the overrided ones
            getattr(self, operation_runner.__name__)()

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

    def remove(self) -> None:
        """
        Removes the snapshot if needed and releases the machine again
        """
        self.service().remove_and_free_machine(self._vmid)

    # Check methods
    def create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        return types.states.TaskState.FINISHED

    def snapshot_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a snapshot creation
        """
        return types.states.TaskState.FINISHED

    def snapshot_recover_checker(self) -> types.states.TaskState:
        """
        Checks the state of a snapshot recovery
        """
        return types.states.TaskState.FINISHED

    def process_token_checker(self) -> types.states.TaskState:
        """
        Checks the state of a token processing
        """
        return types.states.TaskState.FINISHED

    def retry_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def wait_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def nop_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def start_machine(self) -> None:
        """
        Override this method to start the machine if needed
        """
        pass

    def start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return types.states.TaskState.FINISHED

    def stop_machine(self) -> None:
        """
        Override this method to stop the machine if needed
        """
        pass

    def stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        """
        return types.states.TaskState.FINISHED

    # Not abstract methods, defaults to stop machine
    def soft_shutdown_machine(self) -> None:
        """ """
        return self.stop_machine()  # Default is to stop the machine

    def soft_shutdown_checker(self) -> types.states.TaskState:
        return self.stop_checker()  # Default is to check if machine has stopped

    def removed_checker(self) -> types.states.TaskState:
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
        op = self._current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        try:
            check_function = _CHECK_FNCS[op]

            # Invoke using instance, we have overrided methods
            # and we want to use the overrided ones
            state = typing.cast(types.states.TaskState, getattr(self, check_function.__name__)())

            if state == types.states.TaskState.FINISHED:
                self._queue.pop(0)  # Remove finished op
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
            Operation.SOFT_SHUTDOWN: 'soft_shutdown',
            Operation.NOP: 'nop',
            Operation.UNKNOWN: 'unknown',
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


# This is a map of operations to methods
# Operations, duwe to the fact that can be overrided some of them, must be invoked via instance
# We use __name__ later to use them, so we can use type checking and invoke them via instance instead of class
# Note that ERROR and FINISH are not here, as they final states not needing to be executed
_EXEC_FNCS: typing.Final[
    collections.abc.Mapping[Operation, collections.abc.Callable[[FixedUserService], None]]
] = {
    Operation.CREATE: FixedUserService._create,
    Operation.RETRY: FixedUserService._retry,
    Operation.START: FixedUserService.start_machine,
    Operation.STOP: FixedUserService.stop_machine,
    Operation.WAIT: FixedUserService._wait,
    Operation.REMOVE: FixedUserService.remove,
    Operation.SNAPSHOT_CREATE: FixedUserService._snapshot_create,
    Operation.SNAPSHOT_RECOVER: FixedUserService._snapshot_recover,
    Operation.PROCESS_TOKEN: FixedUserService._process_token,
    Operation.SOFT_SHUTDOWN: FixedUserService.soft_shutdown_machine,
    Operation.NOP: FixedUserService._nop,
}

# Same af before, but for check methods
_CHECK_FNCS: typing.Final[
    collections.abc.Mapping[Operation, collections.abc.Callable[[FixedUserService], types.states.TaskState]]
] = {
    Operation.CREATE: FixedUserService.create_checker,
    Operation.RETRY: FixedUserService.retry_checker,
    Operation.WAIT: FixedUserService.wait_checker,
    Operation.START: FixedUserService.start_checker,
    Operation.STOP: FixedUserService.stop_checker,
    Operation.REMOVE: FixedUserService.removed_checker,
    Operation.SNAPSHOT_CREATE: FixedUserService.snapshot_create_checker,
    Operation.SNAPSHOT_RECOVER: FixedUserService.snapshot_recover_checker,
    Operation.PROCESS_TOKEN: FixedUserService.process_token_checker,
    Operation.SOFT_SHUTDOWN: FixedUserService.soft_shutdown_checker,
    Operation.NOP: FixedUserService.nop_checker,
}
