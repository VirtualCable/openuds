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
from enum import auto
import enum
import pickle  # nosec: not insecure, we are loading our own data
import logging
import typing
import collections.abc

from uds.core import services, consts, types
from uds.core.util import log, autoserializable

from . import on

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import OpenNebulaLiveService
    from .publication import OpenNebulaLivePublication
    from uds.core.util.storage import Storage

logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    CREATE = 0
    START = 1
    SHUTDOWN = 2
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


class OpenNebulaLiveDeployment(services.UserService, autoserializable.AutoSerializable):
    # : Recheck every six seconds by default (for task methods)
    suggested_delay = 6

    _name = autoserializable.StringField(default='')
    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()

    #
    # _name: str = ''
    # _ip: str = ''
    # _mac: str = ''
    # _vmid: str = ''
    # _reason: str = ''
    # _queue: list[int]

    def service(self) -> 'OpenNebulaLiveService':
        return typing.cast('OpenNebulaLiveService', super().service())

    def publication(self) -> 'OpenNebulaLivePublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OpenNebulaLivePublication', pub)

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._vmid = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._queue = [Operation.from_int(i) for i in pickle.loads(vals[6])]  # nosec

        self.mark_for_upgrade()  # Flag so manager can save it again with new format

    def get_name(self) -> str:
        if self._name == '':
            try:
                self._name = self.name_generator().get(
                    self.service().get_basename(), self.service().getLenName()
                )
            except KeyError:
                return consts.NO_MORE_NAMES
        return self._name

    def set_ip(self, ip: str) -> None:
        logger.debug('Setting IP to %s', ip)
        self._ip = ip

    def get_unique_id(self) -> str:
        return self._mac.upper()

    def get_ip(self) -> str:
        return self._ip

    def set_ready(self) -> types.states.DeployState:
        if self.cache.get('ready') == '1':
            return types.states.DeployState.FINISHED

        try:
            state = self.service().getMachineState(self._vmid)

            if state == on.types.VmState.UNKNOWN:  # @UndefinedVariable
                return self._error('Machine is not available anymore')

            self.service().startMachine(self._vmid)

            self.cache.put('ready', '1')
        except Exception as e:
            self.do_log(log.LogLevel.ERROR, 'Error on setReady: {}'.format(e))
            # Treat as operation done, maybe the machine is ready and we can continue

        return types.states.DeployState.FINISHED

    def reset(self) -> None:
        if self._vmid != '':
            self.service().resetMachine(self._vmid)

    def get_console_connection(self) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.service().get_console_connection(self._vmid)

    def desktop_login(self, username: str, password: str, domain: str = '') -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.service().desktop_login(self._vmid, username, password, domain)

    def process_ready_from_os_manager(self, data: typing.Any) -> types.states.DeployState:
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for %s', self._name)
        if self._get_current_op() == Operation.WAIT:
            logger.debug('Machine is ready. Moving to level 2')
            self._get_and_pop_current_op()  # Remove current state
            return self._execute_queue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return types.states.DeployState.FINISHED

    def deploy_for_user(self, user: 'models.User') -> types.states.DeployState:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._init_queue_for_deploy(False)
        return self._execute_queue()

    def deploy_for_cache(self, level: int) -> types.states.DeployState:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deploy(level == self.L2_CACHE)
        return self._execute_queue()

    def _init_queue_for_deploy(self, for_level_2: bool = False) -> None:
        if for_level_2 is False:
            self._queue = [Operation.CREATE, Operation.START, Operation.FINISH]
        else:
            self._queue = [
                Operation.CREATE,
                Operation.START,
                Operation.WAIT,
                Operation.SHUTDOWN,
                Operation.FINISH,
            ]

    def _check_machine_state(self, state: on.types.VmState) -> types.states.DeployState:
        logger.debug(
            'Checking that state of machine %s (%s) is %s',
            self._vmid,
            self._name,
            state,
        )
        state = self.service().getMachineState(self._vmid)

        # If we want to check an state and machine does not exists (except in case that we whant to check this)
        if state in [
            on.types.VmState.UNKNOWN,
            on.types.VmState.DONE,
        ]:  # @UndefinedVariable
            return self._error('Machine not found')

        ret = types.states.DeployState.RUNNING

        if isinstance(state, (list, tuple)):
            if state in state:
                ret = types.states.DeployState.FINISHED
        else:
            if state == state:
                ret = types.states.DeployState.FINISHED

        return ret

    def _get_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    def _get_and_pop_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue.pop(0)

    def _push_front_op(self, op: Operation) -> None:
        self._queue.insert(0, op)

    def _error(self, reason: typing.Any) -> types.states.DeployState:
        """
        Internal method to set object as error state

        Returns:
            types.states.DeployState.ERROR, so we can do "return self.__error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid:  # Powers off & delete it
            try:
                self.service().removeMachine(self._vmid)
            except Exception:
                logger.warning('Can\'t set remove errored machine: %s', self._vmid)

        self._queue = [Operation.ERROR]
        self._reason = str(reason)
        return types.states.DeployState.ERROR

    def _execute_queue(self) -> types.states.DeployState:
        self.__debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.DeployState.ERROR

        if op == Operation.FINISH:
            return types.states.DeployState.FINISHED

        fncs: dict[Operation, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.START: self._start_machine,
            Operation.SHUTDOWN: self._shutdown_machine,
            Operation.WAIT: self._wait,
            Operation.REMOVE: self._remove,
        }

        try:
            operation_executor: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if operation_executor is None:
                return self._error('Unknown operation found at execution queue ({0})'.format(op))

            operation_executor()

            return types.states.DeployState.RUNNING
        except Exception as e:
            logger.exception('Got Exception')
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> types.states.DeployState:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns types.states.DeployState.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return types.states.DeployState.FINISHED

    def _wait(self) -> types.states.DeployState:
        """
        Executes opWait, it simply waits something "external" to end
        """
        return types.states.DeployState.RUNNING

    def _create(self) -> str:
        """
        Deploys a machine from template for user/cache
        """
        templateId = self.publication().getTemplateId()
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = self.service().sanitized_name(
            name
        )  # OpenNebula don't let us to create machines with more than 15 chars!!!

        self._vmid = self.service().deploy_from_template(name, templateId)
        if not self._vmid:
            raise Exception('Can\'t create machine')

        # Get IP & MAC (early stage)
        # self._mac, self._ip = self.service().getNetInfo(self._vmid)

        return types.states.DeployState.RUNNING

    def _remove(self) -> str:
        """
        Removes a machine from system
        """
        state = self.service().getMachineState(self._vmid)

        if state == on.types.VmState.UNKNOWN:  # @UndefinedVariable
            raise Exception('Machine not found')

        if state == on.types.VmState.ACTIVE:  # @UndefinedVariable
            subState = self.service().getMachineSubstate(self._vmid)
            if subState < 3:  # Less than running
                logger.info('Must wait before remove: %s', subState)
                self._push_front_op(Operation.RETRY)
                return types.states.DeployState.RUNNING

        self.service().removeMachine(self._vmid)

        return types.states.DeployState.RUNNING

    def _start_machine(self) -> str:
        """
        Powers on the machine
        """
        self.service().startMachine(self._vmid)

        # Get IP & MAC (later stage, after "powering on")
        self._mac, self._ip = self.service().getNetInfo(self._vmid)

        return types.states.DeployState.RUNNING

    def _shutdown_machine(self) -> str:
        """
        Suspends the machine
        """
        self.service().shutdownMachine(self._vmid)
        return types.states.DeployState.RUNNING

    # Check methods
    def _create_checker(self) -> types.states.DeployState:
        """
        Checks the state of a deploy for an user or cache
        """
        return self._check_machine_state(on.types.VmState.ACTIVE)  # @UndefinedVariable

    def _start_checker(self) -> types.states.DeployState:
        """
        Checks if machine has started
        """
        return self._check_machine_state(on.types.VmState.ACTIVE)  # @UndefinedVariable

    def _shutdown_checker(self) -> types.states.DeployState:
        """
        Check if the machine has suspended
        """
        return self._check_machine_state(on.types.VmState.POWEROFF)  # @UndefinedVariable

    def _remove_checker(self) -> types.states.DeployState:
        """
        Checks if a machine has been removed
        """
        return types.states.DeployState.FINISHED  # No check at all, always true

    def check_state(self) -> types.states.DeployState:
        """
        Check what operation is going on, and acts based on it
        """
        self.__debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.DeployState.ERROR

        if op == Operation.FINISH:
            return types.states.DeployState.FINISHED

        fncs: dict[Operation, typing.Optional[collections.abc.Callable[[], types.states.DeployState]]] = {
            Operation.CREATE: self._create_checker,
            Operation.RETRY: self._retry,
            Operation.WAIT: self._wait,
            Operation.START: self._start_checker,
            Operation.SHUTDOWN: self._shutdown_checker,
            Operation.REMOVE: self._remove_checker,
        }

        try:
            chkFnc: typing.Optional[collections.abc.Callable[[], types.states.DeployState]] = fncs.get(op, None)

            if chkFnc is None:
                return self._error('Unknown operation found at check queue ({0})'.format(op))

            state = chkFnc()
            if state == types.states.DeployState.FINISHED:
                self._get_and_pop_current_op()  # Remove runing op
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)

    def move_to_cache(self, level: int) -> types.states.DeployState:
        """
        Moves machines between cache levels
        """
        if Operation.REMOVE in self._queue:
            return types.states.DeployState.RUNNING

        if level == self.L1_CACHE:
            self._queue = [Operation.START, Operation.FINISH]
        else:
            self._queue = [Operation.START, Operation.SHUTDOWN, Operation.FINISH]

        return self._execute_queue()

    def error_reason(self) -> str:
        """
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).
        """
        return self._reason

    def destroy(self) -> types.states.DeployState:
        """
        Invoked for destroying a deployed service
        """
        self.__debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self._get_current_op()

        if op == Operation.ERROR:
            return self._error('Machine is already in error state!')

        if op in [Operation.FINISH, Operation.WAIT, Operation.START, Operation.CREATE]:
            self._queue = [Operation.REMOVE, Operation.FINISH]
            return self._execute_queue()

        self._queue = [op, Operation.REMOVE, Operation.FINISH]
        # Do not execute anything.here, just continue normally
        return types.states.DeployState.RUNNING

    def cancel(self) -> types.states.DeployState:
        """
        This is a task method. As that, the excepted return values are
        types.states.DeployState.values RUNNING, FINISHED or ERROR.

        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.
        """
        return self.destroy()

    @staticmethod
    def __op2str(op: Operation) -> str:
        return {
            Operation.CREATE: 'create',
            Operation.START: 'start',
            Operation.SHUTDOWN: 'shutdown',
            Operation.REMOVE: 'remove',
            Operation.WAIT: 'wait',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
        }.get(op, '????')

    def __debug(self, txt: str) -> None:
        logger.debug(
            'types.states.DeployState.at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [OpenNebulaLiveDeployment.__op2str(op) for op in self._queue],
        )
