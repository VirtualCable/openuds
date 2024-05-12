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

from uds.core import consts, types
from uds.core.services.generics.dynamic.userservice import DynamicUserService
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import XenLinkedService
    from .publication import XenPublication

logger = logging.getLogger(__name__)


class OldOperation(enum.IntEnum):
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
    def from_int(value: int) -> 'OldOperation':
        try:
            return OldOperation(value)
        except ValueError:
            return OldOperation.UNKNOWN

    def as_operation(self) -> types.services.Operation:
        return {
            OldOperation.CREATE: types.services.Operation.CREATE,
            OldOperation.START: types.services.Operation.START,
            OldOperation.STOP: types.services.Operation.STOP,
            OldOperation.SUSPEND: types.services.Operation.SUSPEND,
            OldOperation.REMOVE: types.services.Operation.DELETE,
            OldOperation.WAIT: types.services.Operation.WAIT,
            OldOperation.ERROR: types.services.Operation.ERROR,
            OldOperation.FINISH: types.services.Operation.FINISH,
            OldOperation.RETRY: types.services.Operation.RETRY,
            OldOperation.CONFIGURE: types.services.Operation.CREATE_COMPLETED,
            OldOperation.PROVISION: types.services.Operation.CREATE_COMPLETED,
            OldOperation.WAIT_SUSPEND: types.services.Operation.NOP,
        }.get(self, types.services.Operation.UNKNOWN)


class XenLinkedDeployment(DynamicUserService, autoserializable.AutoSerializable):
    _task = autoserializable.StringField(default='')

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
            self._queue = [
                i.as_operation() for i in pickle.loads(vals[6])
            ]  # nosec: not insecure, we are loading our own data
            self._task = vals[7].decode('utf8')

        self.mark_for_upgrade()  # Force upgrade

    def _init_queue_for_deployment(self, cache_l2: bool = False) -> None:
        if cache_l2 is False:
            self._queue = [
                OldOperation.CREATE,
                OldOperation.CONFIGURE,
                OldOperation.PROVISION,
                OldOperation.START,
                OldOperation.FINISH,
            ]
        else:
            self._queue = [
                OldOperation.CREATE,
                OldOperation.CONFIGURE,
                OldOperation.PROVISION,
                OldOperation.START,
                OldOperation.WAIT,
                OldOperation.WAIT_SUSPEND,
                OldOperation.SUSPEND,
                OldOperation.FINISH,
            ]

    def op_create(self) -> None:
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

    def op_create_completed(self) -> None:
        """
        Provisions machine & changes the mac of the indicated nic
        """
        with self.service().provider().get_connection() as api:
            api.provision_vm(self._vmid, False)  # Let's try this in "sync" mode, this must be fast enough
            self.service().configure_machine(self._vmid, self.get_unique_id())

    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        with self.service().provider().get_connection() as api:
            task_info = api.get_task_info(self._task)
            if task_info.is_success():
                self._vmid = task_info.result
                return types.states.TaskState.FINISHED
            elif task_info.is_failure():
                raise Exception('Error deploying machine: {}'.format(task_info.result))

        return types.states.TaskState.RUNNING
