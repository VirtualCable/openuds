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
from uds.core.services.specializations.dynamic_machine.dynamic_userservice import DynamicUserService, Operation
from uds.core.managers.userservice import UserServiceManager
from uds.core.util import autoserializable

from . import client


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service_linked import ProxmoxServiceLinked
    from .publication import ProxmoxPublication

logger = logging.getLogger(__name__)


class OldOperation(enum.IntEnum):
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

    UNKNOWN = 99

    @staticmethod
    def from_int(value: int) -> 'OldOperation':
        try:
            return OldOperation(value)
        except ValueError:
            return OldOperation.UNKNOWN

    def to_operation(self) -> 'Operation':
        return {
            OldOperation.CREATE: Operation.CREATE,
            OldOperation.START: Operation.START,
            OldOperation.STOP: Operation.STOP,
            OldOperation.SHUTDOWN: Operation.SHUTDOWN,
            OldOperation.REMOVE: Operation.REMOVE,
            OldOperation.WAIT: Operation.WAIT,
            OldOperation.ERROR: Operation.ERROR,
            OldOperation.FINISH: Operation.FINISH,
            OldOperation.RETRY: Operation.NOP,
            OldOperation.GET_MAC: Operation.START_COMPLETED,
            OldOperation.GRACEFUL_STOP: Operation.SHUTDOWN,
            OldOperation.UNKNOWN: Operation.UNKNOWN,
        }[self]


# The difference between "SHUTDOWN" and "GRACEFUL_STOP" is that the first one
# is used to "best try to stop" the machine to move to L2 (that is, if it cannot be stopped,
# it will be moved to L2 anyway, but keeps running), and the second one is used to "best try to stop"
# the machine when destoying it (that is, if it cannot be stopped, it will be destroyed anyway after a
# timeout of at most GUEST_SHUTDOWN_WAIT seconds)

# UP_STATES = ('up', 'reboot_in_progress', 'powering_up', 'restoring_state')


class ProxmoxUserserviceLinked(DynamicUserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing Proxmox deployments (user machines in this case) is here.

    """

    # : Recheck every this seconds by default (for task methods)
    suggested_delay = 12

    _task = autoserializable.StringField(default='')

    # own vars
    # _name: str
    # _ip: str
    # _mac: str
    # _task: str
    # _vmid: str
    # _reason: str
    # _queue: list[int]

    def _store_task(self, upid: 'client.types.UPID') -> None:
        self._task = ','.join([upid.node, upid.upid])

    def _retrieve_task(self) -> tuple[str, str]:
        vals = self._task.split(',')
        return (vals[0], vals[1])

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

    def op_reset(self) -> None:
        if self._vmid:
            self.service().provider().reset_machine(int(self._vmid))

    def op_create(self) -> None:
        return super().op_create()

    def op_create_completed(self) -> None:
        # Retreive network info and store it
        return super().op_create_completed()

    def op_start(self) -> None:
        return super().op_start()

    def op_stop(self) -> None:
        return super().op_stop()

    def op_shutdown(self) -> None:
        return super().op_shutdown()
    
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
        script = (
            'import sys\n'
            'if sys.platform == "win32":\n'
            'from uds import operations\n'
            f'''operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", struct.pack('!IsIs', 1, '{username}'.encode('utf8'), 2, '{password}'.encode('utf8')), True)'''
        )
        # Post script to service
        #         operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", packet, True)
        try:
            UserServiceManager().send_script(self.db_obj(), script)
        except Exception as e:
            logger.info('Exception sending loggin to %s: %s', self.db_obj(), e)

    def migrate_old_queue(self) -> None:
        """
        Migrates the old queue to the new one
        """
        self._queue = [OldOperation.from_int(i).to_operation() for i in self._queue]
