# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import enum
import pickle  # nosec: not insecure, we are loading our own data
import logging
import typing
import collections.abc

from uds.core import services, consts, types
from uds.core.util import autoserializable, log

from .xen_client import XenPowerState

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import XenLinkedService
    from .publication import XenPublication

logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    """
    Operations for deployment
    """

    CREATE = 0
    START = 1
    STOP = 2
    SUSPEND = 3
    REMOVE = 4
    WAIT = 5
    ERROR = 6
    FINISH = 7
    RETRY = 8
    CONFIGURE = 9
    PROVISION = 10
    WAIT_SUSPEND = 11

    UNKNOWN = 99

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.UNKNOWN


class XenLinkedDeployment(services.UserService, autoserializable.AutoSerializable):
    # : Recheck every six seconds by default (for task methods)
    suggested_delay = 7

    _name = autoserializable.StringField(default='')
    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _task = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()

    def initialize(self) -> None:
        self._queue = []

    def service(self) -> 'XenLinkedService':
        return typing.cast('XenLinkedService', super().service())

    def publication(self) -> 'XenPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('XenPublication', pub)

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.split(b'\1')
        logger.debug('Values: %s', vals)
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._vmid = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._queue = pickle.loads(vals[6])  # nosec: not insecure, we are loading our own data
            self._task = vals[7].decode('utf8')

        self.mark_for_upgrade()  # Force upgrade

    def get_name(self) -> str:
        if not self._name:
            try:
                self._name = self.name_generator().get(
                    self.service().get_basename(), self.service().get_lenname()
                )
            except KeyError:
                return consts.NO_MORE_NAMES
        return self._name

    def set_ip(self, ip: str) -> None:
        logger.debug('Setting IP to %s', ip)
        self._ip = ip

    def get_unique_id(self) -> str:
        if not self._mac:
            self._mac = self.mac_generator().get(self.service().get_macs_range())
        return self._mac

    def get_ip(self) -> str:
        return self._ip

    def set_ready(self) -> types.states.TaskState:
        if self.cache.get('ready') == '1':
            return types.states.TaskState.FINISHED

        try:
            state = self.service().get_machine_power_state(self._vmid)

            if state != XenPowerState.running:
                self._queue = [Operation.START, Operation.FINISH]
                return self._execute_queue()

            self.cache.put('ready', '1', 30)
        except Exception as e:
            # On case of exception, log an an error and return as if the operation was executed
            self.do_log(log.LogLevel.ERROR, 'Error setting machine state: {}'.format(e))
            # return self.__error('Machine is not available anymore')

        return types.states.TaskState.FINISHED

    def reset(self) -> types.states.TaskState:
        if self._vmid:
            self.service().reset_machine(self._vmid)  # Reset in sync
            
        return types.states.TaskState.FINISHED

    def process_ready_from_os_manager(self, data: typing.Any) -> types.states.TaskState:
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for %s', self._name)
        if self._get_current_op() == Operation.WAIT:
            logger.debug('Machine is ready. Moving to level 2')
            self._pop_current_op()  # Remove current state
            return self._execute_queue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return types.states.TaskState.FINISHED

    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._init_queue_for_deployment(False)
        return self._execute_queue()

    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deployment(level == types.services.CacheLevel.L2)
        return self._execute_queue()

    def _init_queue_for_deployment(self, cache_l2: bool = False) -> None:
        if cache_l2 is False:
            self._queue = [
                Operation.CREATE,
                Operation.CONFIGURE,
                Operation.PROVISION,
                Operation.START,
                Operation.FINISH,
            ]
        else:
            self._queue = [
                Operation.CREATE,
                Operation.CONFIGURE,
                Operation.PROVISION,
                Operation.START,
                Operation.WAIT,
                Operation.WAIT_SUSPEND,
                Operation.SUSPEND,
                Operation.FINISH,
            ]

    def _get_current_op(self) -> Operation:
        if len(self._queue) == 0:
            return Operation.FINISH

        return self._queue[0]

    def _pop_current_op(self) -> int:
        if len(self._queue) == 0:
            return Operation.FINISH

        return self._queue.pop(0)

    def _push_front_op(self, op: Operation) -> None:
        self._queue.insert(0, op)

    def _push_back_op(self, op: Operation) -> None:
        self._queue.append(op)

    def _error(self, reason: typing.Any) -> types.states.TaskState:
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid != '':  # Powers off and delete VM
            try:
                state = self.service().get_machine_power_state(self._vmid)
                if state in (
                    XenPowerState.running,
                    XenPowerState.paused,
                    XenPowerState.suspended,
                ):
                    self.service().stop_machine(self._vmid, False)  # In sync mode
                self.service().remove_machine(self._vmid)
            except Exception:
                logger.debug('Can\'t set machine %s state to stopped', self._vmid)

        self._queue = [Operation.ERROR]
        self._reason = str(reason)
        return types.states.TaskState.ERROR

    def _execute_queue(self) -> types.states.TaskState:
        self.__debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        fncs: dict[Operation, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.START: self._start_machine,
            Operation.STOP: self._stop_machine,
            Operation.WAIT_SUSPEND: self._wait_suspend,
            Operation.SUSPEND: self._suspend_machine,
            Operation.WAIT: self._wait,
            Operation.REMOVE: self._remove,
            Operation.CONFIGURE: self._configure,
            Operation.PROVISION: self._provision,
        }

        try:
            operation: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if not operation:
                return self._error('Unknown operation found at execution queue ({0})'.format(op))

            operation()

            return types.states.TaskState.RUNNING
        except Exception as e:
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> types.states.TaskState:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns types.states.DeployState.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return types.states.TaskState.FINISHED

    def _wait(self) -> types.states.TaskState:
        """
        Executes opWait, it simply waits something "external" to end
        """
        return types.states.TaskState.RUNNING

    def _create(self) -> str:
        """
        Deploys a machine from template for user/cache
        """
        template_id = self.publication().getTemplateId()
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = 'UDS service ' + self.service().sanitized_name(
            name
        )  # oVirt don't let us to create machines with more than 15 chars!!!
        comments = 'UDS Linked clone'

        self._task = self.service().start_deploy_from_template(name, comments, template_id)
        if not self._task:
            raise Exception('Can\'t create machine')

        return types.states.TaskState.RUNNING

    def _remove(self) -> str:
        """
        Removes a machine from system
        """
        state = self.service().get_machine_power_state(self._vmid)

        if state not in (XenPowerState.halted, XenPowerState.suspended):
            self._push_front_op(Operation.STOP)
            self._execute_queue()
        else:
            self.service().remove_machine(self._vmid)

        return types.states.TaskState.RUNNING

    def _start_machine(self) -> str:
        """
        Powers on the machine
        """
        task = self.service().start_machine(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return types.states.TaskState.RUNNING

    def _stop_machine(self) -> str:
        """
        Powers off the machine
        """
        task = self.service().stop_machine(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return types.states.TaskState.RUNNING

    def _wait_suspend(self) -> str:
        """
        Before suspending, wait for machine to have the SUSPEND feature
        """
        self._task = ''
        return types.states.TaskState.RUNNING

    def _suspend_machine(self) -> str:
        """
        Suspends the machine
        """
        task = self.service().suspend_machine(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return types.states.TaskState.RUNNING

    def _configure(self) -> types.states.TaskState:
        """
        Provisions machine & changes the mac of the indicated nic
        """
        self.service().configure_machine(self._vmid, self.get_unique_id())

        return types.states.TaskState.RUNNING

    def _provision(self) -> types.states.TaskState:
        """
        Makes machine usable on Xen
        """
        self.service().provision_machine(self._vmid, False)  # Let's try this in "sync" mode, this must be fast enough

        return types.states.TaskState.RUNNING

    # Check methods
    def _create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        state = self.service().check_task_finished(self._task)
        if state[0]:  # Finished
            self._vmid = state[1]
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

    def _start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        if self.service().check_task_finished(self._task)[0]:
            return types.states.TaskState.FINISHED
        return types.states.TaskState.RUNNING

    def _stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        """
        if self.service().check_task_finished(self._task)[0]:
            return types.states.TaskState.FINISHED
        return types.states.TaskState.RUNNING

    def _wait_suspend_checker(self) -> types.states.TaskState:
        if self.service().can_suspend_machine(self._vmid) is True:
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

    def _suspend_checker(self) -> types.states.TaskState:
        """
        Check if the machine has suspended
        """
        if self.service().check_task_finished(self._task)[0]:
            return types.states.TaskState.FINISHED
        return types.states.TaskState.RUNNING

    def removed_checker(self) -> types.states.TaskState:
        """
        Checks if a machine has been removed
        """
        return types.states.TaskState.FINISHED

    def _configure_checker(self) -> types.states.TaskState:
        """
        Checks if change mac operation has finished.

        Changing nic configuration es 1-step operation, so when we check it here, it is already done
        """
        return types.states.TaskState.FINISHED

    def _provision_checker(self) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def check_state(self) -> types.states.TaskState:
        """
        Check what operation is going on, and acts acordly to it
        """
        self.__debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        fncs: dict[int, typing.Optional[collections.abc.Callable[[], types.states.TaskState]]] = {
            Operation.CREATE: self._create_checker,
            Operation.RETRY: self._retry,
            Operation.WAIT: self._wait,
            Operation.START: self._start_checker,
            Operation.STOP: self._stop_checker,
            Operation.WAIT_SUSPEND: self._wait_suspend_checker,
            Operation.SUSPEND: self._suspend_checker,
            Operation.REMOVE: self.removed_checker,
            Operation.CONFIGURE: self._configure_checker,
            Operation.PROVISION: self._provision_checker,
        }

        try:
            chkFnc: typing.Optional[collections.abc.Callable[[], types.states.TaskState]] = fncs.get(op, None)

            if chkFnc is None:
                return self._error('Unknown operation found at check queue ({})'.format(op))

            state = chkFnc()
            if state == types.states.TaskState.FINISHED:
                self._pop_current_op()  # Remove runing op
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)

    def move_to_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        """
        Moves machines between cache levels
        """
        if Operation.REMOVE in self._queue:
            return types.states.TaskState.RUNNING

        if level == types.services.CacheLevel.L1:
            self._queue = [Operation.START, Operation.FINISH]
        else:
            self._queue = [Operation.START, Operation.SUSPEND, Operation.FINISH]

        return self._execute_queue()

    def error_reason(self) -> str:
        return self._reason

    def destroy(self) -> types.states.TaskState:
        self.__debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.FINISHED

        if op == Operation.FINISH or op == Operation.WAIT:
            self._queue = [Operation.STOP, Operation.REMOVE, Operation.FINISH]
            return self._execute_queue()

        self._queue = [op, Operation.STOP, Operation.REMOVE, Operation.FINISH]
        # Do not execute anything.here, just continue normally
        return types.states.TaskState.RUNNING

    def cancel(self) -> types.states.TaskState:
        return self.destroy()

    @staticmethod
    def __op2str(op: Operation) -> str:
        return {
            Operation.CREATE: 'create',
            Operation.START: 'start',
            Operation.STOP: 'stop',
            Operation.WAIT_SUSPEND: 'wait-suspend',
            Operation.SUSPEND: 'suspend',
            Operation.REMOVE: 'remove',
            Operation.WAIT: 'wait',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
            Operation.CONFIGURE: 'configuring',
            Operation.PROVISION: 'provisioning',
        }.get(op, '????')

    def __debug(self, txt: str) -> None:
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [XenLinkedDeployment.__op2str(op) for op in self._queue],
        )
