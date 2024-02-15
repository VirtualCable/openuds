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

from uds.core import services
from uds.core.services.specializations.fixed_machine.fixed_userservice import FixedUserService, Operation
from uds.core.types.states import State
from uds.core.util import log, autoserializable

from . import client

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from . import service_fixed

logger = logging.getLogger(__name__)


class ProxmoxFixedUserService(FixedUserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing vmware deployments (user machines in this case) is here.

    """

    # : Recheck every ten seconds by default (for task methods)
    suggested_delay = 4

    def _store_task(self, upid: 'client.types.UPID') -> None:
        self._task = '\t'.join([upid.node, upid.upid])

    def _retrieve_task(self) -> tuple[str, str]:
        vals = self._task.split('\t')
        return (vals[0], vals[1])

    # Utility overrides for type checking...
    def service(self) -> 'service_fixed.ProxmoxFixedService':
        return typing.cast('service_fixed.ProxmoxFixedService', super().service())

    def set_ready(self) -> str:
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            vminfo = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError:
            raise  # If connection fails, let it fail on parent
        except Exception as e:
            return self._error(f'Machine not found: {e}')

        if vminfo.status == 'stopped':
            self._queue = [Operation.START, Operation.FINISH]
            return self._execute_queue()

        self.cache.put('ready', '1')
        return State.FINISHED

    def reset(self) -> None:
        """
        o Proxmox, reset operation just shutdowns it until v3 support is removed
        """
        if self._vmid != '':
            try:
                self.service().reset_machine(int(self._vmid))
            except Exception:  # nosec: if cannot reset, ignore it
                pass  # If could not reset, ignore it...

    def process_ready_from_os_manager(self, data: typing.Any) -> str:
        return State.FINISHED

    def error(self, reason: str) -> str:
        return self._error(reason)

    def _start_machine(self) -> None:
        try:
            vminfo = self.service().get_machine_info(int(self._vmid))
        except client.ProxmoxConnectionError:
            self._retry_later()
        except Exception as e:
            raise Exception('Machine not found on start machine') from e

        if vminfo.status == 'stopped':
            self._store_task(self.service().start_machine(int(self._vmid)))

    def _stop_machine(self) -> None:
        try:
            vm_info = self.service().get_machine_info(int(self._vmid))
        except Exception as e:
            raise Exception('Machine not found on stop machine') from e

        if vm_info.status != 'stopped':
            logger.debug('Stopping machine %s', vm_info)
            self._store_task(self.service().stop_machine(int(self._vmid)))

    # Check methods
    def _check_task_finished(self) -> str:
        if self._task == '':
            return State.FINISHED

        node, upid = self._retrieve_task()

        try:
            task = self.service().get_task_info(node, upid)
        except client.ProxmoxConnectionError:
            return State.RUNNING  # Try again later

        if task.is_errored():
            return self._error(task.exitstatus)

        if task.is_completed():
            return State.FINISHED

        return State.RUNNING

    # Check methods
    def _start_checker(self) -> str:
        """
        Checks if machine has started
        """
        return self._check_task_finished()

    def _stop_checker(self) -> str:
        """
        Checks if machine has stoped
        """
        return self._check_task_finished()
