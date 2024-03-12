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
from uds.core.services.specializations.fixed_machine.fixed_userservice import FixedUserService, Operation
from uds.core.util import autoserializable

from .openstack import types as openstack_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import service_fixed

logger = logging.getLogger(__name__)


class OpenStackUserServiceFixed(FixedUserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing vmware deployments (user machines in this case) is here.

    """

    # : Recheck every ten seconds by default (for task methods)
    suggested_delay = 4

    # Utility overrides for type checking...
    def service(self) -> 'service_fixed.OpenStackServiceFixed':
        return typing.cast('service_fixed.OpenStackServiceFixed', super().service())

    def set_ready(self) -> types.states.TaskState:
        if self.cache.get('ready') == '1':
            return types.states.TaskState.FINISHED

        try:
            vminfo = self.service().get_machine_info(self._vmid)
        except Exception as e:
            return self._error(f'Machine not found: {e}')

        if vminfo.status == 'stopped':
            self._queue = [Operation.START, Operation.FINISH]
            return self._execute_queue()

        self.cache.put('ready', '1')
        return types.states.TaskState.FINISHED

    def reset(self) -> None:
        """
        OpenStack, reset operation
        """
        if self._vmid != '':
            try:
                self.service().api.reset_server(self._vmid)
            except Exception:  # nosec: if cannot reset, ignore it
                pass  # If could not reset, ignore it...

    def process_ready_from_os_manager(self, data: typing.Any) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def error(self, reason: str) -> types.states.TaskState:
        return self._error(reason)

    def _start_machine(self) -> None:
        try:
            vminfo = self.service().get_machine_info(self._vmid)
        except Exception as e:
            raise Exception('Machine not found on start machine') from e

        if vminfo.power_state != openstack_types.PowerState.RUNNING:
            self.service().api.start_server(self._vmid)  # Start the server

