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
import logging
import typing

from uds.core import types
from uds.core.services.generics.fixed.userservice import FixedUserService
from uds.core.util import autoserializable

from .proxmox import types as prox_types, exceptions as prox_exceptions

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import service_fixed

logger = logging.getLogger(__name__)


class ProxmoxUserServiceFixed(FixedUserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing vmware deployments (user machines in this case) is here.

    """

    def _store_task(self, upid: 'prox_types.ExecResult') -> None:
        self._task = '\t'.join([upid.node, upid.upid])

    def _retrieve_task(self) -> tuple[str, str]:
        vals = self._task.split('\t')
        return (vals[0], vals[1])

    # Utility overrides for type checking...
    def service(self) -> 'service_fixed.ProxmoxServiceFixed':
        return typing.cast('service_fixed.ProxmoxServiceFixed', super().service())

    def reset(self) -> types.states.TaskState:
        """
        o Proxmox, reset operation just shutdowns it until v3 support is removed
        """
        if self._vmid != '':
            try:
                self.service().provider().api.reset_vm(int(self._vmid))
            except Exception:  # nosec: if cannot reset, ignore it
                pass  # If could not reset, ignore it...
            
        return types.states.TaskState.FINISHED

    def op_start(self) -> None:
        vminfo = self.service().get_vm_info(int(self._vmid)).validate()

        if  not vminfo.status.is_running():
            self._store_task(self.service().provider().api.start_vm(int(self._vmid)))

    # Check methods
    def _check_task_finished(self) -> types.states.TaskState:
        if self._task == '':
            return types.states.TaskState.FINISHED

        node, upid = self._retrieve_task()

        try:
            task = self.service().provider().api.get_task_info(node, upid)
        except prox_exceptions.ProxmoxConnectionError:
            return types.states.TaskState.RUNNING  # Try again later

        if task.is_errored():
            return self.error(task.exitstatus)

        if task.is_completed():
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

    # Check methods
    def op_start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return self._check_task_finished()
