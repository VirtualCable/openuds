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
import pickle  # nosec: controled data
import enum
import logging
import typing
import collections.abc

from uds.core import services, consts, types
from uds.core.managers.userservice import UserServiceManager
from uds.core.util import log, autoserializable
from uds.core.util.model import sql_stamp_seconds

from .jobs import ProxmoxDeferredRemovalOrig
from . import client


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service_linked import ProxmoxServiceLinked
    from .publication import ProxmoxPublication

logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    """
    Operation codes for Proxmox deployment
    """

    CREATE = 0
    START = 1
    STOP = 2
    SHUTDOWN = 3
    REMOVE = 4
    WAIT = 5
    ERROR = 6
    FINISH = 7
    RETRY = 8
    GET_MAC = 9
    GRACEFUL_STOP = 10

    opUnknown = 99

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.opUnknown


# The difference between "SHUTDOWN" and "GRACEFUL_STOP" is that the first one
# is used to "best try to stop" the machine to move to L2 (that is, if it cannot be stopped,
# it will be moved to L2 anyway, but keeps running), and the second one is used to "best try to stop"
# the machine when destoying it (that is, if it cannot be stopped, it will be destroyed anyway after a
# timeout of at most GUEST_SHUTDOWN_WAIT seconds)

# UP_STATES = ('up', 'reboot_in_progress', 'powering_up', 'restoring_state')


class ProxmoxUserserviceLinked(services.UserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing Proxmox deployments (user machines in this case) is here.

    """

    # : Recheck every this seconds by default (for task methods)
    suggested_delay = 12

    _name = autoserializable.StringField(default='')
    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _task = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()

    # own vars
    # _name: str
    # _ip: str
    # _mac: str
    # _task: str
    # _vmid: str
    # _reason: str
    # _queue: list[int]

    # Utility overrides for type checking...
    def service(self) -> 'ProxmoxServiceLinked':
        return typing.cast('ProxmoxServiceLinked', super().service())

    def publication(self) -> 'ProxmoxPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('ProxmoxPublication', pub)

    def unmarshal(self, data: bytes) -> None:
        """
        Does nothing here also, all data are keeped at environment storage
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._task = vals[4].decode('utf8')
            self._vmid = vals[5].decode('utf8')
            self._reason = vals[6].decode('utf8')
            self._queue = [Operation.from_int(i) for i in pickle.loads(vals[7])]  # nosec: controled data

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
        logger.debug('Setting IP to %s', ip)
        self._ip = ip

    def get_unique_id(self) -> str:
        """
        Return and unique identifier for this service.
        In our case, we will generate a mac name, that can be also as sample
        of 'mac' generator use, and probably will get used something like this
        at some services.

        The get method of a mac generator takes one param, that is the mac range
        to use to get an unused mac.
        """
        if self._mac == '':
            self._mac = self.mac_generator().get(self.service().get_macs_range())
        return self._mac

    def get_ip(self) -> str:
        return self._ip

    def set_ready(self) -> types.states.TaskState:
        if self.cache.get('ready') == '1':
            return types.states.TaskState.FINISHED

        try:
            vmInfo = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError as e:
            return self._error(f'Could not connect to Proxmox: {e}')
        except Exception as e:
            return self._error(f'Machine not found: {e}')

        if vmInfo.status == 'stopped':
            self._queue = [Operation.START, Operation.FINISH]
            return self._execute_queue()

        self.cache.put('ready', '1')
        return types.states.TaskState.FINISHED

    def reset(self) -> types.states.TaskState:
        """
        o Proxmox, reset operation just shutdowns it until v3 support is removed
        """
        if self._vmid != '':
            try:
                self.service().provider().reset_machine(int(self._vmid))
            except Exception:  # nosec: if cannot reset, ignore it
                pass  # If could not reset, ignore it...
                
        return types.states.TaskState.FINISHED

    def get_console_connection(
        self,
    ) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.service().get_console_connection(self._vmid)

    def desktop_login(
        self,
        username: str,
        password: str,
        domain: str = '',  # pylint: disable=unused-argument
    ) -> None:
        script = f'''import sys
if sys.platform == 'win32':
    from uds import operations
    operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", struct.pack('!IsIs', 1, '{username}'.encode('utf8'), 2, '{password}'.encode('utf8')), True)
'''
        # Post script to service
        #         operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", packet, True)
        dbService = self.db_obj()
        if dbService:
            try:
                UserServiceManager().send_script(dbService, script)
            except Exception as e:
                logger.info('Exception sending loggin to %s: %s', dbService, e)

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

    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deploy(level == types.services.CacheLevel.L2)
        return self._execute_queue()

    def _init_queue_for_deploy(self, cache_l2: bool = False) -> None:
        if cache_l2 is False:
            self._queue = [Operation.CREATE, Operation.GET_MAC, Operation.START, Operation.FINISH]
        else:
            self._queue = [
                Operation.CREATE,
                Operation.GET_MAC,
                Operation.START,
                Operation.WAIT,
                Operation.SHUTDOWN,
                Operation.FINISH,
            ]

    def _store_task(self, upid: 'client.types.UPID') -> None:
        self._task = ','.join([upid.node, upid.upid])

    def _retrieve_task(self) -> tuple[str, str]:
        vals = self._task.split(',')
        return (vals[0], vals[1])

    def _get_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    def _pop_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        res = self._queue.pop(0)
        return res

    def _push_front_op(self, op: Operation) -> None:
        self._queue.insert(0, op)

    def _retry_later(self) -> str:
        self._push_front_op(Operation.RETRY)
        return types.states.TaskState.RUNNING

    def _error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            types.states.TaskState.ERROR, so we can do "return self.__error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid != '':  # Powers off
            ProxmoxDeferredRemovalOrig.remove(self.service().provider(), int(self._vmid))

        self._queue = [Operation.ERROR]
        self._reason = reason
        return types.states.TaskState.ERROR

    def _execute_queue(self) -> types.states.TaskState:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        try:
            operation_executor = _EXECUTORS.get(op, None)

            if operation_executor is None:
                return self._error(f'Unknown operation found at execution queue ({op})')

            operation_executor(self)

            return types.states.TaskState.RUNNING
        except Exception as e:
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> None:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns types.states.TaskState.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        pass

    def _retry_checker(self) -> types.states.TaskState:
        """
        This method is not used, because retry operation is never used
        """
        return types.states.TaskState.FINISHED

    def _wait(self) -> None:
        """
        Executes opWait, it simply waits something "external" to end
        """
        pass

    def _wait_checker(self) -> types.states.TaskState:
        """
        Wait checker waits forever, until something external wakes it up
        """
        return types.states.TaskState.RUNNING

    def _create(self) -> None:
        """
        Deploys a machine from template for user/cache
        """
        template_id = self.publication().machine()
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        comments = 'UDS Linked clone'

        task_result = self.service().clone_machine(name, comments, template_id)

        self._store_task(task_result.upid)

        self._vmid = str(task_result.vmid)

    def _remove(self) -> None:
        """
        Removes a machine from system
        """
        try:
            vm_info = self.service().get_machine_info(int(self._vmid))
        except Exception as e:
            raise Exception('Machine not found on remove machine') from e

        if vm_info.status != 'stopped':
            logger.debug('Info status: %s', vm_info)
            self._queue = [Operation.STOP, Operation.REMOVE, Operation.FINISH]
            self._execute_queue()
        self._store_task(self.service().remove_machine(int(self._vmid)))

    def _start_machine(self) -> None:
        try:
            vm_info = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError:
            self._retry_later()
            return
        except Exception as e:
            raise Exception('Machine not found on start machine') from e

        if vm_info.status == 'stopped':
            self._store_task(self.service().provider().start_machine(int(self._vmid)))

    def _stop_machine(self) -> None:
        try:
            vm_info = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError:
            self._retry_later()
            return
        except Exception as e:
            raise Exception('Machine not found on stop machine') from e

        if vm_info.status != 'stopped':
            logger.debug('Stopping machine %s', vm_info)
            self._store_task(self.service().provider().stop_machine(int(self._vmid)))

    def _shutdown_machine(self) -> None:
        try:
            vm_info = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError:
            self._retry_later()
            return
        except Exception as e:
            raise Exception('Machine not found or suspended machine') from e

        if vm_info.status != 'stopped':
            self._store_task(self.service().provider().shutdown_machine(int(self._vmid)))

    def _gracely_stop(self) -> None:
        """
        Tries to stop machine using qemu guest tools
        If it takes too long to stop, or qemu guest tools are not installed,
        will use "power off" "a las bravas"
        """
        self._task = ''
        shutdown = -1  # Means machine already stopped
        try:
            vm_info = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError:
            self._retry_later()
            return
        except Exception as e:
            raise Exception('Machine not found on stop machine') from e

        if vm_info.status != 'stopped':
            self._store_task(self.service().provider().shutdown_machine(int(self._vmid)))
            shutdown = sql_stamp_seconds()
        logger.debug('Stoped vm using guest tools')
        self.storage.save_pickled('shutdown', shutdown)

    def _update_machine_mac_and_ha(self) -> None:
        try:
            # Note: service will only enable ha if it is configured to do so
            self.service().enable_machine_ha(int(self._vmid), True)  # Enable HA before continuing here

            # Set vm mac address now on first interface
            self.service().provider().set_machine_mac(int(self._vmid), self.get_unique_id())
        except client.ProxmoxConnectionError:
            self._retry_later()
            return
        except Exception as e:
            logger.exception('Setting HA and MAC on proxmox')
            raise Exception(f'Error setting MAC and HA on proxmox: {e}') from e

    # Check methods
    def _check_task_finished(self) -> types.states.TaskState:
        if self._task == '':
            return types.states.TaskState.FINISHED

        node, upid = self._retrieve_task()

        try:
            task = self.service().provider().get_task_info(node, upid)
        except client.ProxmoxConnectionError:
            return types.states.TaskState.RUNNING  # Try again later

        if task.is_errored():
            return self._error(task.exitstatus)

        if task.is_completed():
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

    def _create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        return self._check_task_finished()

    def _start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return self._check_task_finished()

    def _stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        """
        return self._check_task_finished()

    def _shutdown_checker(self) -> types.states.TaskState:
        """
        Check if the machine has suspended
        """
        return self._check_task_finished()

    def _graceful_stop_checker(self) -> types.states.TaskState:
        """
        Check if the machine has gracely stopped (timed shutdown)
        """
        shutdown_start = self.storage.read_pickled('shutdown')
        logger.debug('Shutdown start: %s', shutdown_start)
        if shutdown_start < 0:  # Was already stopped
            # Machine is already stop
            logger.debug('Machine WAS stopped')
            return types.states.TaskState.FINISHED

        if shutdown_start == 0:  # Was shut down a las bravas
            logger.debug('Macine DO NOT HAVE guest tools')
            return self._stop_checker()

        logger.debug('Checking State')
        # Check if machine is already stopped
        if self.service().get_machine_info(int(self._vmid)).status == 'stopped':
            return types.states.TaskState.FINISHED  # It's stopped

        logger.debug('State is running')
        if sql_stamp_seconds() - shutdown_start > consts.os.MAX_GUEST_SHUTDOWN_WAIT:
            logger.debug('Time is consumed, falling back to stop')
            self.do_log(
                log.LogLevel.ERROR,
                f'Could not shutdown machine using soft power off in time ({consts.os.MAX_GUEST_SHUTDOWN_WAIT} seconds). Powering off.',
            )
            # Not stopped by guest in time, but must be stopped normally
            self.storage.save_pickled('shutdown', 0)
            self._stop_machine()  # Launch "hard" stop

        return types.states.TaskState.RUNNING

    def _remove_checker(self) -> types.states.TaskState:
        """
        Checks if a machine has been removed
        """
        return self._check_task_finished()

    def _mac_checker(self) -> types.states.TaskState:
        """
        Checks if change mac operation has finished.

        Changing nic configuration is 1-step operation, so when we check it here, it is already done
        """
        return types.states.TaskState.FINISHED

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
            operation_checker = _CHECKERS.get(op, None)

            if operation_checker is None:
                return self._error(f'Unknown operation found at check queue ({op})')

            state = operation_checker(self)
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

    def destroy(self) -> types.states.TaskState:
        """
        Invoked for destroying a deployed service
        """
        self._debug('destroy')
        if self._vmid == '':
            self._queue = []
            self._reason = "canceled"
            return types.states.TaskState.FINISHED

        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self._get_current_op()

        if op == Operation.ERROR:
            return self._error('Machine is already in error state!')

        lst: list[Operation] = [] if not self.service().try_graceful_shutdown() else [Operation.GRACEFUL_STOP]
        queue = lst + [Operation.STOP, Operation.REMOVE, Operation.FINISH]

        if op in (Operation.FINISH, Operation.WAIT):
            self._queue[:] = queue
            return self._execute_queue()

        self._queue = [op] + queue
        # Do not execute anything.here, just continue normally
        return types.states.TaskState.RUNNING

    def cancel(self) -> types.states.TaskState:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

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
            Operation.STOP: 'stop',
            Operation.SHUTDOWN: 'shutdown',
            Operation.GRACEFUL_STOP: 'gracely stop',
            Operation.REMOVE: 'remove',
            Operation.WAIT: 'wait',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
            Operation.GET_MAC: 'getting mac',
        }.get(op, '????')

    def _debug(self, txt: str) -> None:
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [ProxmoxUserserviceLinked._op2str(op) for op in self._queue],
        )


_EXECUTORS: typing.Final[
    collections.abc.Mapping[
        Operation, typing.Optional[collections.abc.Callable[[ProxmoxUserserviceLinked], None]]
    ]
] = {
    Operation.CREATE: ProxmoxUserserviceLinked._create,
    Operation.RETRY: ProxmoxUserserviceLinked._retry,
    Operation.START: ProxmoxUserserviceLinked._start_machine,
    Operation.STOP: ProxmoxUserserviceLinked._stop_machine,
    Operation.GRACEFUL_STOP: ProxmoxUserserviceLinked._gracely_stop,
    Operation.SHUTDOWN: ProxmoxUserserviceLinked._shutdown_machine,
    Operation.WAIT: ProxmoxUserserviceLinked._wait,
    Operation.REMOVE: ProxmoxUserserviceLinked._remove,
    Operation.GET_MAC: ProxmoxUserserviceLinked._update_machine_mac_and_ha,
}


_CHECKERS: dict[
    Operation, typing.Optional[collections.abc.Callable[[ProxmoxUserserviceLinked], types.states.TaskState]]
] = {
    Operation.CREATE: ProxmoxUserserviceLinked._create_checker,
    Operation.RETRY: ProxmoxUserserviceLinked._retry_checker,
    Operation.WAIT: ProxmoxUserserviceLinked._wait_checker,
    Operation.START: ProxmoxUserserviceLinked._start_checker,
    Operation.STOP: ProxmoxUserserviceLinked._stop_checker,
    Operation.GRACEFUL_STOP: ProxmoxUserserviceLinked._graceful_stop_checker,
    Operation.SHUTDOWN: ProxmoxUserserviceLinked._shutdown_checker,
    Operation.REMOVE: ProxmoxUserserviceLinked._remove_checker,
    Operation.GET_MAC: ProxmoxUserserviceLinked._mac_checker,
}
