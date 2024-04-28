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
from uds.core.util import autoserializable

from .openstack import types as openstack_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

    from .publication import OpenStackLivePublication
    from .service import OpenStackLiveService


logger = logging.getLogger(__name__)

# How many times we will check for a machine to be ready/stopped/whatever
# 25 = 25 * 5 = 125 seconds (5 is suggested_delay)
CHECK_COUNT_BEFORE_FAILURE: typing.Final[int] = 25


class Operation(enum.IntEnum):
    CREATE = 0
    START = 1
    SUSPEND = 2
    REMOVE = 3
    WAIT = 4
    ERROR = 5
    FINISH = 6
    RETRY = 7
    STOP = 8

    UNKNOWN = 99

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.UNKNOWN


class OpenStackLiveUserService(
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
    _check_count = autoserializable.IntegerField(default=CHECK_COUNT_BEFORE_FAILURE)
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
                self._name = 'UDS-U-' + self.name_generator().get(
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
            status = self.service().get_machine_status(self._vmid)

            if status.is_lost():
                return self._error('Machine is not available anymore')

            power_state = self.service().get_machine_power_state(self._vmid)

            if power_state.is_paused():
                self.service().resume_machine(self._vmid)
            elif power_state.is_stopped():
                self.service().start_machine(self._vmid)

            # Right now, we suppose the machine is ready

            self.cache.put('ready', '1')
        except Exception as e:
            self.do_log(types.log.LogLevel.ERROR, 'Error on setReady: {}'.format(e))
            # Treat as operation done, maybe the machine is ready and we can continue

        return types.states.TaskState.FINISHED

    def reset(self) -> types.states.TaskState:
        if self._vmid != '':
            self.service().reset_machine(self._vmid)
            
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
        self._init_queue_for_deploy(types.services.CacheLevel.NONE)
        return self._execute_queue()

    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deploy(level)
        return self._execute_queue()

    def _init_queue_for_deploy(self, level: types.services.CacheLevel) -> None:
        if level in (types.services.CacheLevel.NONE, types.services.CacheLevel.L1):
            self._queue = [Operation.CREATE, Operation.FINISH]
        else:
            self._queue = [Operation.CREATE, Operation.WAIT, Operation.SUSPEND, Operation.FINISH]

    def _check_machine_power_state(self, *check_state: 'openstack_types.PowerState') -> types.states.TaskState:
        self._check_count -= 1
        if self._check_count < 0:
            return self._error('Machine is not {str(check_state)} after {CHECK_COUNT_BEFORE_FAILURE} checks')

        logger.debug(
            'Checking that state of machine %s (%s) is %s (remaining checks: %s)',
            self._vmid,
            self._name,
            check_state,
            self._check_count,
        )
        power_state = self.service().get_machine_power_state(self._vmid)

        ret = types.states.TaskState.RUNNING

        if power_state in check_state:
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

    def _reset_check_count(self) -> None:
        # Check the maximum number of checks before failure
        # So we dont stuck forever on check state to CHECK_COUNT_BEFORE_FAILURE
        self._check_count = CHECK_COUNT_BEFORE_FAILURE

    def _error(self, reason: typing.Any) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            types.states.DeployState.ERROR, so we can do "return self.__error(reason)"
        """
        logger.debug('Setting error state, reason: %s', reason)
        is_creation = self._get_current_op() == Operation.CREATE
        self._queue = [Operation.ERROR]
        self._reason = str(reason)

        self.do_log(types.log.LogLevel.ERROR, self._reason)

        if self._vmid:
            # Creating machines should be deleted on error
            if is_creation or self.service().keep_on_error() is False:  # Powers off & delete it
                try:
                    self.service().delete_machine(self._vmid)
                except Exception:
                    logger.warning('Can\t set machine %s state to stopped', self._vmid)
            else:
                self.do_log(
                    types.log.LogLevel.INFO, 'Keep on error is enabled, machine will not be marked for deletion'
                )
                # Fix queue to FINISH and return it
                self._queue = [Operation.FINISH]
                return types.states.TaskState.FINISHED

        return types.states.TaskState.ERROR

    def _execute_queue(self) -> types.states.TaskState:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        try:
            if op not in _EXECUTE_FNCS:
                return self._error('Unknown operation found at execution queue ({0})'.format(op))

            _EXECUTE_FNCS[op](self)

            return types.states.TaskState.RUNNING
        except Exception as e:
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> None:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns types.states.DeployState.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        pass

    def _wait(self) -> None:
        """
        Executes opWait, it simply waits something "external" to end
        """
        pass

    def _create(self) -> None:
        """
        Deploys a machine from template for user/cache
        """
        templateId = self.publication().get_template_id()
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = self.service().sanitized_name(name)

        self._vmid = self.service().deploy_from_template(name, templateId).id
        if not self._vmid:
            raise Exception('Can\'t create machine')

        self._reset_check_count()

        return None

    def _remove(self) -> None:
        """
        Removes a machine from system
        """
        status = self.service().get_machine_status(self._vmid)

        if status.is_lost():
            raise Exception('Machine not found. (Status {})'.format(status))

        self.service().delete_machine(self._vmid)

    def _start_machine(self) -> None:
        """
        Powers on the machine
        """
        self.service().start_machine(self._vmid)

        self._reset_check_count()

    def _stop_machine(self) -> None:
        """
        Powers off the machine
        """
        self.service().stop_machine(self._vmid)

        self._reset_check_count()

    def _suspend_machine(self) -> None:
        """
        Suspends the machine
        """
        self.service().suspend_machine(self._vmid)

        self._reset_check_count()

    def _check_retry(self) -> types.states.TaskState:
        """
        This method is invoked when a task has been retried.
        """
        return types.states.TaskState.FINISHED

    def _check_wait(self) -> types.states.TaskState:
        """
        This method is invoked when a task is waiting for something.
        """
        return types.states.TaskState.RUNNING

    # Check methods
    def _check_create(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        # Checks if machine has been created
        ret = self._check_machine_power_state(openstack_types.PowerState.RUNNING)
        if ret == types.states.TaskState.FINISHED:
            # If machine is requested to not be removed never, we may end with
            # an empty mac and ip, but no problem. Next time we will get it
            # Get IP & MAC (early stage)
            addr = self.service().get_server_address(self._vmid)
            self._mac, self._ip = addr.mac, addr.ip

        return ret

    def _check_start(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return self._check_machine_power_state(openstack_types.PowerState.RUNNING)

    def _check_stop(self) -> types.states.TaskState:
        """
        Checks if machine has stopped
        """
        return self._check_machine_power_state(
            openstack_types.PowerState.SHUTDOWN,
            openstack_types.PowerState.CRASHED,
            openstack_types.PowerState.SUSPENDED,
        )

    def _check_suspend(self) -> types.states.TaskState:
        """
        Check if the machine has suspended
        """
        return self._check_machine_power_state(openstack_types.PowerState.SUSPENDED)

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

        try:
            if op not in _CHECK_FNCS:
                return self._error('Unknown operation found at execution queue ({0})'.format(op))

            state = _CHECK_FNCS[op](self)
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
        else:  # Currently L2 is not supported
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

        ops = [Operation.STOP, Operation.REMOVE, Operation.FINISH]

        if op == Operation.FINISH or op == Operation.WAIT:
            self._queue = ops
            return self._execute_queue()  # Run it right now

        # If an operation is pending, maybe checking, so we will wait until it finishes
        self._queue = [op] + ops

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
            [OpenStackLiveUserService._op2str(op) for op in self._queue],
        )


# Execution methods
_EXECUTE_FNCS: dict[int, collections.abc.Callable[[OpenStackLiveUserService], None]] = {
    Operation.CREATE: OpenStackLiveUserService._create,
    Operation.RETRY: OpenStackLiveUserService._retry,
    Operation.START: OpenStackLiveUserService._start_machine,
    Operation.STOP: OpenStackLiveUserService._stop_machine,
    Operation.SUSPEND: OpenStackLiveUserService._suspend_machine,
    Operation.WAIT: OpenStackLiveUserService._wait,
    Operation.REMOVE: OpenStackLiveUserService._remove,
}

# Check methods
_CHECK_FNCS: dict[int, collections.abc.Callable[[OpenStackLiveUserService], types.states.TaskState]] = {
    Operation.CREATE: OpenStackLiveUserService._check_create,
    Operation.RETRY: OpenStackLiveUserService._check_retry,
    Operation.WAIT: OpenStackLiveUserService._check_wait,
    Operation.START: OpenStackLiveUserService._check_start,
    Operation.STOP: OpenStackLiveUserService._check_stop,
    Operation.SUSPEND: OpenStackLiveUserService._check_suspend,
    Operation.REMOVE: OpenStackLiveUserService._check_removed,
}
