#
# Copyright (c) 2024 Virtual Cable S.L.U.
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

from .openshift import types as morph_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import service_fixed

logger = logging.getLogger(__name__)


class OpenshiftUserServiceFixed(FixedUserService, autoserializable.AutoSerializable):
    # : Recheck every ten seconds by default (for task methods)
    suggested_delay = 4

    def service(self) -> 'service_fixed.OpenshiftServiceFixed':
        return typing.cast('service_fixed.OpenshiftServiceFixed', super().service())

    def reset(self) -> types.states.TaskState:
        """
        HPE Openshift, reset operation just restarts the instance.
        """
        if self._vmid != '':
            try:
                self.service().api.restart_instance(self._vmid)
            except Exception:  # nosec: if cannot reset, ignore it
                pass  # If could not reset, ignore it...

        return types.states.TaskState.FINISHED

    def op_start(self) -> None:
        instance = self.service().provider().api.get_instance_info(self._vmid)

        if instance.status.is_off():
            self.service().provider().api.start_instance(self._vmid)

    def op_stop(self) -> None:
        instance = self.service().provider().api.get_instance_info(self._vmid)

        # If instance is not running, do nothing
        if instance.status.is_off():
            logger.debug('Machine %s is already stopped', self._vmid)
            return

        # If instance is running, stop it
        logger.debug('Machine %s is running, stopping it', self._vmid)
        self.service().api.stop_instance(self._vmid)

    # Check methods
    def _check_status(self, *status: morph_types.InstanceStatus) -> types.states.TaskState:
        """
        Checks the status of the instance and returns the appropriate TaskState.
        """
        instance = self.service().provider().api.get_instance_info(self._vmid)

        if instance.status in status:
            return types.states.TaskState.FINISHED
        elif instance.status.is_error():
            return self.error(f'Instance {self._vmid} is in error state: {instance.status}')

        return types.states.TaskState.RUNNING

    # Check methods
    def op_start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return self._check_status(
            morph_types.InstanceStatus.RUNNING,
            morph_types.InstanceStatus.PROVISIONING,
        )

    def op_stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        """
        return self._check_status(
            morph_types.InstanceStatus.STOPPED,
            morph_types.InstanceStatus.SUSPENDED,
        )
