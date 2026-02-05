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

from uds.core import types
from uds.core.services.generics.dynamic.userservice import DynamicUserService
from uds.core.managers.userservice import UserServiceManager
from uds.core.util import autoserializable
import uds.services.Proxmox.proxmox.exceptions

from .proxmox import types as prox_types


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service_linked import ProxmoxServiceLinked
    from .publication import ProxmoxPublication

logger = logging.getLogger(__name__)


class OldOperation(enum.IntEnum):
    """
    OldOperation codes for Proxmox deployment
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

    UNKNOWN = 99

    @staticmethod
    def from_int(value: int) -> 'OldOperation':
        try:
            return OldOperation(value)
        except ValueError:
            return OldOperation.UNKNOWN

    def to_operation(self) -> 'types.services.Operation':
        return {
            OldOperation.CREATE: types.services.Operation.CREATE,
            OldOperation.START: types.services.Operation.START,
            OldOperation.STOP: types.services.Operation.STOP,
            OldOperation.SHUTDOWN: types.services.Operation.SHUTDOWN,
            OldOperation.REMOVE: types.services.Operation.DELETE,
            OldOperation.WAIT: types.services.Operation.WAIT,
            OldOperation.ERROR: types.services.Operation.ERROR,
            OldOperation.FINISH: types.services.Operation.FINISH,
            OldOperation.RETRY: types.services.Operation.NOP,
            OldOperation.GET_MAC: types.services.Operation.START_COMPLETED,
            OldOperation.GRACEFUL_STOP: types.services.Operation.SHUTDOWN,
            OldOperation.UNKNOWN: types.services.Operation.UNKNOWN,
        }[self]


# The difference between "SHUTDOWN" and "GRACEFUL_STOP" is that the first one
# is used to "best try to stop" the machine to move to L2 (that is, if it cannot be stopped,
# it will be moved to L2 anyway, but keeps running), and the second one is used to "best try to stop"
# the machine when destoying it (that is, if it cannot be stopped, it will be destroyed anyway after a
# timeout of at most GUEST_SHUTDOWN_WAIT seconds)

# UP_STATES = ('up', 'reboot_in_progress', 'powering_up', 'restoring_state')


class ProxmoxUserserviceLinked(DynamicUserService):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing Proxmox deployments (user machines in this case) is here.

    """

    _task = autoserializable.StringField(default='')

    def _store_task(self, upid: 'prox_types.ExecResult') -> None:
        self._task = ','.join([upid.node, upid.upid])

    def _retrieve_task(self) -> tuple[str, str]:
        vals = self._task.split(',')
        return (vals[0], vals[1])

    def _check_task_finished(self) -> types.states.TaskState:
        if self._task == '':
            return types.states.TaskState.FINISHED

        node, upid = self._retrieve_task()

        try:
            task = self.service().provider().api.get_task_info(node, upid)
        except uds.services.Proxmox.proxmox.exceptions.ProxmoxConnectionError:
            return types.states.TaskState.RUNNING  # Try again later

        if task.is_errored():
            return self.error(task.exitstatus)

        if task.is_completed():
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

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
            # Load from old format and convert to new one directly
            self._queue = [
                OldOperation.from_int(i).to_operation() for i in pickle.loads(vals[7])
            ]  # nosec: controled data

        self.mark_for_upgrade()  # Flag so manager can save it again with new format

    def op_reset(self) -> None:
        if self._vmid:
            self.service().provider().api.reset_vm(int(self._vmid))

    # No need for op_reset_checker

    # Modificamos la cola de creación para incluir apagado, custom (snapshot) y encendido final
    _create_queue = [
        types.services.Operation.INITIALIZE,
        types.services.Operation.CREATE,
        types.services.Operation.CREATE_COMPLETED,
        types.services.Operation.START,
        types.services.Operation.START_COMPLETED,
        types.services.Operation.SHUTDOWN,  # Apaga la VM tras configurarla
        types.services.Operation.SHUTDOWN_COMPLETED,
        types.services.Operation.CUSTOM_1,  # Crea snapshot con la VM apagada
        types.services.Operation.START,     # Enciende la VM para dejarla lista
        types.services.Operation.START_COMPLETED,
        types.services.Operation.FINISH,
    ]

    def op_create(self) -> None:
        template_id = int(self.publication().get_template_id())
        name = self.get_vmname()

        comments = 'UDS Linked clone'
        task_result = self.service().clone_vm(name, comments, template_id)
        self._store_task(task_result.exec_result)
        self._vmid = str(task_result.vmid)

    # Cuando el usuario libera la máquina, restaurar snapshot antes de dejarla lista
    def release_for_user(self) -> 'types.states.TaskState':
        """
        Método a llamar cuando el usuario libera la máquina: apaga, recupera snapshot y deja encendida.
        """
        self._queue = [
            types.services.Operation.SHUTDOWN,
            types.services.Operation.SHUTDOWN_COMPLETED,
            types.services.Operation.CUSTOM_1,  # Recupera snapshot
            types.services.Operation.START,
            types.services.Operation.START_COMPLETED,
            types.services.Operation.FINISH,
        ]
        return self._execute_queue()

    def op_create_checker(self) -> types.states.TaskState:
        return self._check_task_finished()

    def op_create_completed(self) -> None:
        # Note: service will only enable ha if it is configured to do so
        self.service().enable_vm_ha(int(self._vmid), True)  # Enable HA before continuing here

        # Set vm mac address now on first interface
        self.service().provider().api.set_vm_net_mac(int(self._vmid), self.get_unique_id())

    def launch_custom_operation(self) -> 'types.states.TaskState':
        """
        Añade la operación CUSTOM_1 a la cola y ejecuta la cola de operaciones.
        """
        self._queue.insert(0, types.services.Operation.CUSTOM_1)
        return self._execute_queue()

    def op_custom(self, operation: types.services.Operation) -> None:
        """
        If there is no snapshot, create a snapshot. If there is, restore the snapshot (always with the VM turned off).
        """
        # Check if VMID is set
        if not getattr(self, '_vmid', None):
            self.error('No VMID set')
            return

        vmid = int(self._vmid)
        service = self.service()
        provider = service.provider()
        api = provider.api

        # Helper to ensure VM is powered off before snapshot operations
        def ensure_powered_off() -> bool:
            if service.is_running(self, str(vmid)):
                self._queue.insert(0, types.services.Operation.NOP)
                self._queue.insert(0, types.services.Operation.SHUTDOWN)
                return False
            return True

        try:
            snapshot_id = api.get_current_vm_snapshot(vmid)
        except Exception as e:
            logger.warning(f'Error checking snapshot for VM {vmid}: {e}')
            snapshot_id = None

        # If there is no snapshot, create one
        if not snapshot_id:
            # If it is on, turn it off first
            if not ensure_powered_off():
                return
            try:
                exec_result = api.create_snapshot(vmid, name='UDS Snapshot')
                self._store_task(exec_result)
            except Exception as e:
                logger.warning(f'Error creating snapshot for VM {vmid}: {e}')
                self.error(str(e))
        else:
            # Restore snapshot (must be powered off)
            if not ensure_powered_off():
                return
            try:
                exec_result = api.restore_snapshot(vmid, name=snapshot_id.name)
                self._store_task(exec_result)
            except Exception as e:
                logger.warning(f'Error restoring snapshot for VM {vmid}: {e}')
                self.error(str(e))

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        """
        Check if the snapshot or restore operation has finished.
        """
        return self._check_task_finished()

    def get_console_connection(
        self,
    ) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.service().get_console_connection(self._vmid)

    def desktop_login(
        self,
        username: str,
        password: str,
        domain: str = '',
    ) -> None:
        script = (
            'import sys\n'
            'if sys.platform == "win32":\n'
            'from uds import operations\n'
            f'''operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", struct.pack('!IsIs', 1, '{username}'.encode('utf8'), 2, '{password}'.encode('utf8')), True)'''
        )
        # Post script to service
        #         operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", packet, True)
        try:
            UserServiceManager.manager().send_script(self.db_obj(), script)
        except Exception as e:
            logger.info('Exception sending loggin to %s: %s', self.db_obj(), e)
