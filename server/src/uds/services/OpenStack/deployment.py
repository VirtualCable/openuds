# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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
import collections.abc
import enum
import logging
import pickle  # nosec: not insecure, we are loading our own data
import typing

from uds.core import consts, services, types
from uds.core.util import autoserializable, log

from . import openstack

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

    from .publication import OpenStackLivePublication
    from .service import OpenStackLiveService


logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    CREATE = 0
    START = 1
    SUSPEND = 2
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


class OpenStackLiveDeployment(
    services.UserService, autoserializable.AutoSerializable
):  # pylint: disable=too-many-public-methods
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.
    """

    _name = autoserializable.StringField(default='')
    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()

    # _name: str = ''
    # _ip: str = ''
    # _mac: str = ''
    # _vmid: str = ''
    # _reason: str = ''
    # _queue: list[int] = []

    # : Recheck every this seconds by default (for task methods)
    suggested_delay = 5

    # For typing check only...
    def service(self) -> 'OpenStackLiveService':
        return typing.cast('OpenStackLiveService', super().service())

    # For typing check only...
    def publication(self) -> 'OpenStackLivePublication':
        return typing.cast('OpenStackLivePublication', super().publication())

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
                    self.service().get_basename(), self.service().get_lenname()
                )
            except KeyError:
                return consts.NO_MORE_NAMES
        return self._name

    def set_ip(self, ip: str) -> None:
        self._ip = ip

    def get_unique_id(self) -> str:
        return self._mac

    def get_ip(self) -> str:
        return self._ip

    def set_ready(self) -> types.states.TaskState:
        """
        The method is invoked whenever a machine is provided to an user, right
        before presenting it (via transport rendering) to the user.
        """
        if self.cache.get('ready') == '1':
            return types.states.TaskState.FINISHED

        try:
            status = self.service().get_machine_state(self._vmid)

            if openstack.status_is_lost(status):
                return self._error('Machine is not available anymore')

            if status == openstack.PAUSED:
                self.service().resume_machine(self._vmid)
            elif status in (openstack.STOPPED, openstack.SHUTOFF):
                self.service().start_machine(self._vmid)

            # Right now, we suppose the machine is ready

            self.cache.put('ready', '1')
        except Exception as e:
            self.do_log(log.LogLevel.ERROR, 'Error on setReady: {}'.format(e))
            # Treat as operation done, maybe the machine is ready and we can continue

        return types.states.TaskState.FINISHED

    def reset(self) -> None:
        if self._vmid != '':
            self.service().reset_machine(self._vmid)

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
        self._init_queue_for_deploy(False)
        return self._execute_queue()

    def deploy_for_cache(self, level: int) -> types.states.TaskState:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deploy(level == self.L2_CACHE)
        return self._execute_queue()

    def _init_queue_for_deploy(self, forLevel2: bool = False) -> None:
        if forLevel2 is False:
            self._queue = [Operation.CREATE, Operation.FINISH]
        else:
            self._queue = [Operation.CREATE, Operation.WAIT, Operation.SUSPEND, Operation.FINISH]

    def _check_machine_state(self, chkState: str) -> types.states.TaskState:
        logger.debug(
            'Checking that state of machine %s (%s) is %s',
            self._vmid,
            self._name,
            chkState,
        )
        status = self.service().get_machine_state(self._vmid)

        # If we want to check an state and machine does not exists (except in case that we whant to check this)
        if openstack.status_is_lost(status):
            return self._error('Machine not available. ({})'.format(status))

        ret = types.states.TaskState.RUNNING
        chkStates = [chkState] if not isinstance(chkState, (list, tuple)) else chkState
        if status in chkStates:
            ret = types.states.TaskState.FINISHED

        return ret

    def _get_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    def _pop_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue.pop(0)

    def _error(self, reason: typing.Any) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            types.states.DeployState.ERROR, so we can do "return self.__error(reason)"
        """
        logger.debug('Setting error state, reason: %s', reason)
        self._queue = [Operation.ERROR]
        self._reason = str(reason)

        self.do_log(log.LogLevel.ERROR, self._reason)

        if self._vmid:  # Powers off & delete it
            try:
                self.service().remove_machine(self._vmid)
            except Exception:
                logger.warning('Can\t set machine %s state to stopped', self._vmid)

        return types.states.TaskState.ERROR

    def _execute_queue(self) -> types.states.TaskState:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        fncs: dict[int, collections.abc.Callable[[], str]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.START: self._start_machine,
            Operation.SUSPEND: self._suspend_machine,
            Operation.WAIT: self._wait,
            Operation.REMOVE: self._remove,
        }

        try:
            if op not in fncs:
                return self._error('Unknown operation found at execution queue ({0})'.format(op))

            fncs[op]()

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
        templateId = self.publication().get_template_id()
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

        return types.states.TaskState.RUNNING

    def _remove(self) -> str:
        """
        Removes a machine from system
        """
        status = self.service().get_machine_state(self._vmid)

        if openstack.status_is_lost(status):
            raise Exception('Machine not found. (Status {})'.format(status))

        self.service().remove_machine(self._vmid)

        return types.states.TaskState.RUNNING

    def _start_machine(self) -> str:
        """
        Powers on the machine
        """
        self.service().start_machine(self._vmid)

        return types.states.TaskState.RUNNING

    def _suspend_machine(self) -> str:
        """
        Suspends the machine
        """
        self.service().suspend_machine(self._vmid)

        return types.states.TaskState.RUNNING

    # Check methods
    def _check_create(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        ret = self._check_machine_state(openstack.ACTIVE)
        if ret == types.states.TaskState.FINISHED:
            # Get IP & MAC (early stage)
            self._mac, self._ip = self.service().get_network_info(self._vmid)

        return ret

    def _check_start(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return self._check_machine_state(openstack.ACTIVE)

    def _check_suspend(self) -> types.states.TaskState:
        """
        Check if the machine has suspended
        """
        return self._check_machine_state(openstack.SUSPENDED)

    def _check_removed(self) -> types.states.TaskState:
        """
        Checks if a machine has been removed
        """
        return types.states.TaskState.FINISHED  # No check at all, always true

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

        fncs: dict[int, collections.abc.Callable[[], types.states.TaskState]] = {
            Operation.CREATE: self._check_create,
            Operation.RETRY: self._retry,
            Operation.WAIT: self._wait,
            Operation.START: self._check_start,
            Operation.SUSPEND: self._check_suspend,
            Operation.REMOVE: self._check_removed,
        }

        try:
            if op not in fncs:
                return self._error('Unknown operation found at execution queue ({0})'.format(op))

            state = fncs[op]()
            if state == types.states.TaskState.FINISHED:
                self._pop_current_op()  # Remove runing op
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)

    def move_to_cache(self, level: int) -> types.states.TaskState:
        """
        Moves machines between cache levels
        """
        if Operation.REMOVE in self._queue:
            return types.states.TaskState.RUNNING

        if level == self.L1_CACHE:
            self._queue = [Operation.START, Operation.FINISH]
        else:
            self._queue = [Operation.START, Operation.SUSPEND, Operation.FINISH]

        return self._execute_queue()

    def error_reason(self) -> str:
        return self._reason

    def destroy(self) -> types.states.TaskState:
        """
        Invoked for destroying a deployed service
        """
        self._debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self._get_current_op()

        if op == Operation.ERROR:
            return self._error('Machine is already in error state!')

        if op == Operation.FINISH or op == Operation.WAIT:
            self._queue = [Operation.REMOVE, Operation.FINISH]
            return self._execute_queue()

        self._queue = [op, Operation.REMOVE, Operation.FINISH]
        # Do not execute anything.here, just continue normally
        return types.states.TaskState.RUNNING

    def cancel(self) -> types.states.TaskState:
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
    def _op2str(op: Operation) -> str:
        return {
            Operation.CREATE: 'create',
            Operation.START: 'start',
            Operation.SUSPEND: 'suspend',
            Operation.REMOVE: 'remove',
            Operation.WAIT: 'wait',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
        }.get(op, '????')

    def _debug(self, txt: str) -> None:
        logger.debug(
            'types.states.DeployState.at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [OpenStackLiveDeployment._op2str(op) for op in self._queue],
        )
