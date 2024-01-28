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

from uds.core import services, consts
from uds.core.types.states import State
from uds.core.util import log, auto_serializable

from .xen_client import XenPowerState

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import XenLinkedService
    from .publication import XenPublication
    from uds.core.util.storage import Storage

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


class XenLinkedDeployment(services.UserService, auto_serializable.AutoSerializable):
    # : Recheck every six seconds by default (for task methods)
    suggested_delay = 7

    _name = auto_serializable.StringField(default='')
    _ip = auto_serializable.StringField(default='')
    _mac = auto_serializable.StringField(default='')
    _vmid = auto_serializable.StringField(default='')
    _reason = auto_serializable.StringField(default='')
    _task = auto_serializable.StringField(default='')
    _queue = auto_serializable.ListField[Operation]()

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

        self.flag_for_upgrade()  # Force upgrade

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

    def set_ready(self) -> str:
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            state = self.service().getVMPowerState(self._vmid)

            if state != XenPowerState.running:
                self._queue = [Operation.START, Operation.FINISH]
                return self._execute_from_queue()

            self.cache.put('ready', '1', 30)
        except Exception as e:
            # On case of exception, log an an error and return as if the operation was executed
            self.do_log(log.LogLevel.ERROR, 'Error setting machine state: {}'.format(e))
            # return self.__error('Machine is not available anymore')

        return State.FINISHED

    def reset(self) -> None:
        if self._vmid:
            self.service().resetVM(self._vmid)  # Reset in sync

    def process_ready_from_os_manager(self, data: typing.Any) -> str:
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for %s', self._name)
        if self._get_current_op() == Operation.WAIT:
            logger.debug('Machine is ready. Moving to level 2')
            self._pop_current_op()  # Remove current state
            return self._execute_from_queue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return State.FINISHED

    def deploy_for_user(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._init_queue_for_deployment(False)
        return self._execute_from_queue()

    def deploy_for_cache(self, cacheLevel: int) -> str:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deployment(cacheLevel == self.L2_CACHE)
        return self._execute_from_queue()

    def _init_queue_for_deployment(self, forLevel2: bool = False) -> None:
        if forLevel2 is False:
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

    def _error(self, reason: typing.Any) -> str:
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid != '':  # Powers off and delete VM
            try:
                state = self.service().getVMPowerState(self._vmid)
                if state in (
                    XenPowerState.running,
                    XenPowerState.paused,
                    XenPowerState.suspended,
                ):
                    self.service().stopVM(self._vmid, False)  # In sync mode
                self.service().removeVM(self._vmid)
            except Exception:
                logger.debug('Can\'t set machine %s state to stopped', self._vmid)

        self._queue = [Operation.ERROR]
        self._reason = str(reason)
        return State.ERROR

    def _execute_from_queue(self) -> str:
        self.__debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.ERROR

        if op == Operation.FINISH:
            return State.FINISHED

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

            return State.RUNNING
        except Exception as e:
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> str:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return State.FINISHED

    def _wait(self) -> str:
        """
        Executes opWait, it simply waits something "external" to end
        """
        return State.RUNNING

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

        name = 'UDS service ' + self.service().sanitizeVmName(
            name
        )  # oVirt don't let us to create machines with more than 15 chars!!!
        comments = 'UDS Linked clone'

        self._task = self.service().startDeployFromTemplate(name, comments, templateId)
        if self._task is None:
            raise Exception('Can\'t create machine')

        return State.RUNNING

    def _remove(self) -> str:
        """
        Removes a machine from system
        """
        state = self.service().getVMPowerState(self._vmid)

        if state not in (XenPowerState.halted, XenPowerState.suspended):
            self._push_front_op(Operation.STOP)
            self._execute_from_queue()
        else:
            self.service().removeVM(self._vmid)

        return State.RUNNING

    def _start_machine(self) -> str:
        """
        Powers on the machine
        """
        task = self.service().startVM(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return State.RUNNING

    def _stop_machine(self) -> str:
        """
        Powers off the machine
        """
        task = self.service().stopVM(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return State.RUNNING

    def _wait_suspend(self) -> str:
        """
        Before suspending, wait for machine to have the SUSPEND feature
        """
        self._task = ''
        return State.RUNNING

    def _suspend_machine(self) -> str:
        """
        Suspends the machine
        """
        task = self.service().suspend_machine(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return State.RUNNING

    def _configure(self):
        """
        Provisions machine & changes the mac of the indicated nic
        """
        self.service().configureVM(self._vmid, self.get_unique_id())

        return State.RUNNING

    def _provision(self):
        """
        Makes machine usable on Xen
        """
        self.service().provisionVM(self._vmid, False)  # Let's try this in "sync" mode, this must be fast enough

        return State.RUNNING

    # Check methods
    def _create_checker(self):
        """
        Checks the state of a deploy for an user or cache
        """
        state = self.service().check_task_finished(self._task)
        if state[0]:  # Finished
            self._vmid = state[1]
            return State.FINISHED

        return State.RUNNING

    def _start_checker(self):
        """
        Checks if machine has started
        """
        if self.service().check_task_finished(self._task)[0]:
            return State.FINISHED
        return State.RUNNING

    def _stop_checker(self):
        """
        Checks if machine has stoped
        """
        if self.service().check_task_finished(self._task)[0]:
            return State.FINISHED
        return State.RUNNING

    def _wait_suspend_checker(self):
        if self.service().can_suspend_machine(self._vmid) is True:
            return State.FINISHED

        return State.RUNNING

    def _suspend_checker(self):
        """
        Check if the machine has suspended
        """
        if self.service().check_task_finished(self._task)[0]:
            return State.FINISHED
        return State.RUNNING

    def removed_checker(self):
        """
        Checks if a machine has been removed
        """
        return State.FINISHED

    def _configure_checker(self):
        """
        Checks if change mac operation has finished.

        Changing nic configuration es 1-step operation, so when we check it here, it is already done
        """
        return State.FINISHED

    def _provision_checker(self):
        return State.FINISHED

    def check_state(self) -> str:
        """
        Check what operation is going on, and acts acordly to it
        """
        self.__debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.ERROR

        if op == Operation.FINISH:
            return State.FINISHED

        fncs: dict[int, typing.Optional[collections.abc.Callable[[], str]]] = {
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
            chkFnc: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if chkFnc is None:
                return self._error('Unknown operation found at check queue ({})'.format(op))

            state = chkFnc()
            if state == State.FINISHED:
                self._pop_current_op()  # Remove runing op
                return self._execute_from_queue()

            return state
        except Exception as e:
            return self._error(e)

    def move_to_cache(self, newLevel: int) -> str:
        """
        Moves machines between cache levels
        """
        if Operation.REMOVE in self._queue:
            return State.RUNNING

        if newLevel == self.L1_CACHE:
            self._queue = [Operation.START, Operation.FINISH]
        else:
            self._queue = [Operation.START, Operation.SUSPEND, Operation.FINISH]

        return self._execute_from_queue()

    def error_reason(self) -> str:
        return self._reason

    def destroy(self) -> str:
        self.__debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.FINISHED

        if op == Operation.FINISH or op == Operation.WAIT:
            self._queue = [Operation.STOP, Operation.REMOVE, Operation.FINISH]
            return self._execute_from_queue()

        self._queue = [op, Operation.STOP, Operation.REMOVE, Operation.FINISH]
        # Do not execute anything.here, just continue normally
        return State.RUNNING

    def cancel(self) -> str:
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
