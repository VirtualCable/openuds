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
import enum
import logging
import pickle  # nosec: not insecure, we are loading our own data
import typing

from uds.core import consts, types
from uds.core.services.generics.dynamic.userservice import DynamicUserService
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:

    from .publication import OpenStackLivePublication
    from .service import OpenStackLiveService


logger = logging.getLogger(__name__)

# How many times we will check for a machine to be ready/stopped/whatever
# 25 = 25 * 5 = 125 seconds (5 is suggested_delay)
CHECK_COUNT_BEFORE_FAILURE: typing.Final[int] = 25


class OldOperation(enum.IntEnum):
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
    def from_int(value: int) -> 'OldOperation':
        try:
            return OldOperation(value)
        except ValueError:
            return OldOperation.UNKNOWN

    def to_operation(self) -> types.services.Operation:
        return {
            OldOperation.CREATE: types.services.Operation.CREATE,
            OldOperation.START: types.services.Operation.START,
            OldOperation.SUSPEND: types.services.Operation.SUSPEND,
            OldOperation.REMOVE: types.services.Operation.DELETE,
            OldOperation.WAIT: types.services.Operation.WAIT,
            OldOperation.ERROR: types.services.Operation.ERROR,
            OldOperation.FINISH: types.services.Operation.FINISH,
            OldOperation.RETRY: types.services.Operation.RETRY,
            OldOperation.STOP: types.services.Operation.STOP,
            OldOperation.UNKNOWN: types.services.Operation.UNKNOWN,
        }.get(self, types.services.Operation.UNKNOWN)


class OpenStackLiveUserService(DynamicUserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.
    """

    # _name: str = ''
    # _ip: str = ''
    # _mac: str = ''
    # _vmid: str = ''
    # _reason: str = ''
    # _queue: list[int] = []


    # Custom queue
    _create_queue = [
        types.services.Operation.CREATE,
        types.services.Operation.FINISH,
    ]
    _create_queue_l1_cache = [
        types.services.Operation.CREATE,
        types.services.Operation.FINISH,
    ]
    # Note that openstack does not implements L2 cache
    _create_queue_l2_cache = [
        types.services.Operation.CREATE,
        types.services.Operation.WAIT,
        types.services.Operation.STOP,
        types.services.Operation.FINISH,
    ]

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
            self._queue = [OldOperation.from_int(i).to_operation() for i in pickle.loads(vals[6])]  # nosec

        self.mark_for_upgrade()  # Flag so manager can save it again with new format


    def op_create(self) -> None:
        """
        Deploys a machine from template for user/cache
        """
        template_id = self.publication().get_template_id()
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = self.service().sanitized_name(name)

        self._vmid = self.service().deploy_from_template(name, template_id).id
        if not self._vmid:
            raise Exception('Can\'t create machine')

        return None
           

    # Check methods
    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        # Checks if machine has been created
        if self.service().is_running(self, self._vmid):
            server_info = self.service().api.get_server(self._vmid).validated()
            self._mac = server_info.addresses[0].mac
            self._ip = server_info.addresses[0].ip
            return types.states.TaskState.FINISHED
        
        return types.states.TaskState.RUNNING

