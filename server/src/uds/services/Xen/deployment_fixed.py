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

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import service_fixed

logger = logging.getLogger(__name__)


class XenFixedUserService(FixedUserService, autoserializable.AutoSerializable):
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
    def service(self) -> 'service_fixed.XenFixedService':
        return typing.cast('service_fixed.XenFixedService', super().service())

    def reset(self) -> types.states.TaskState:
        if self._vmid:
            self.service().reset_vm(self._vmid)  # Reset in sync
            
        return types.states.TaskState.FINISHED

    def process_ready_from_os_manager(self, data: typing.Any) -> types.states.TaskState:
        return types.states.TaskState.FINISHED

    def op_start(self) -> None:
        self._task = self.service().start_vm(self._vmid)

    def op_stop(self) -> None:
        self._task = self.service().stop_vm(self._vmid)

    # Check methods
    def _check_task_finished(self) -> types.states.TaskState:
        if self._task == '':
            return types.states.TaskState.FINISHED

        with self.service().provider().get_connection() as api:
            task_info = api.get_task_info(self._task)
            if task_info.is_failure():
                raise Exception(task_info.result)  # Will set error state
            
            if task_info.is_success():
                return types.states.TaskState.FINISHED
    
        return types.states.TaskState.RUNNING

    # Check methods
    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for an user or cache
        """
        return types.states.TaskState.FINISHED

    def op_start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        return self._check_task_finished()

    def op_stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stoped
        """
        return self._check_task_finished()

    def op_removed_checker(self) -> types.states.TaskState:
        """
        Checks if a machine has been removed
        """
        return self._check_task_finished()
