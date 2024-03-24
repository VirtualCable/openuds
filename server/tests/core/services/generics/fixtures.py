# -*- coding: utf-8 -*-

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
Authot: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import typing
from unittest import mock

from uds.core import services, types, ui
from uds.core.services.generics.fixed import service as fixed_service
from uds.core.services.generics.fixed import userservice as fixed_userservice

if typing.TYPE_CHECKING:
    from uds import models


class FixedTestingUserService(fixed_userservice.FixedUserService):
    mock: 'mock.Mock' = mock.MagicMock()

    def start_machine(self) -> None:
        self.mock._start_machine()

    def stop_machine(self) -> None:
        self.mock._stop_machine()

    def start_checker(self) -> types.states.TaskState:
        self.mock._start_checker()
        return types.states.TaskState.FINISHED

    def stop_checker(self) -> types.states.TaskState:
        self.mock._stop_checker()
        return types.states.TaskState.FINISHED

    def db_obj(self) -> typing.Any:
        self.mock.db_obj()
        return None


class FixedTestingService(fixed_service.FixedService):
    type_name = 'Fixed Service'
    type_type = 'FixedService'
    type_description = 'Fixed Service description'

    token = fixed_service.FixedService.token
    snapshot_type = fixed_service.FixedService.snapshot_type
    machines = fixed_service.FixedService.machines

    user_service_type = FixedTestingUserService
    first_process_called = False
    available_machines_number = 1

    mock: 'mock.Mock' = mock.MagicMock()

    def process_snapshot(self, remove: bool, userservice_instance: fixed_userservice.FixedUserService) -> None:
        self.mock.process_snapshot(remove, userservice_instance)
        if not remove and not self.first_process_called:
            # We want to call start, then snapshot, again
            # As we have snapshot on top of queue, we need to insert NOP -> STOP
            # This way, NOP will be consumed right now, then start will be called and then
            # this will be called again
            userservice_instance._queue.insert(0, types.services.FixedOperation.STOP)
            userservice_instance._queue.insert(0, types.services.FixedOperation.NOP)
            self.first_process_called = True

    def get_machine_name(self, vmid: str) -> str:
        self.mock.get_machine_name(vmid)
        return f'Machine {vmid}'

    def get_and_assign_machine(self) -> str:
        self.mock.get_and_assign_machine()
        if self.available_machines_number <= 0:
            raise Exception('No machine available')
        self.available_machines_number -= 1
        self.assigned_machine = 'assigned'
        return self.assigned_machine

    def remove_and_free_machine(self, vmid: str) -> str:
        self.mock.remove_and_free_machine(vmid)
        self.assigned_machine = ''
        return types.states.TaskState.FINISHED

    def get_first_network_mac(self, vmid: str) -> str:
        self.mock.get_first_network_mac(vmid)
        return '00:00:00:00:00:00'

    def get_guest_ip_address(self, vmid: str) -> str:
        self.mock.get_guest_ip_address(vmid)
        return '10.0.0.10'

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        """
        Returns a list of tuples with the id and the name of the assignables
        """
        self.mock.enumerate_assignables()
        return [
            ui.gui.choice_item('1', 'Machine 1'),
            ui.gui.choice_item('2', 'Machine 2'),
            ui.gui.choice_item('3', 'Machine 3'),
        ]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> types.states.TaskState:
        """
        Assigns a machine from the assignables
        """
        self.mock.assign_from_assignables(assignable_id, user, userservice_instance)
        return types.states.TaskState.FINISHED


class FixedTestingProvider(services.provider.ServiceProvider):
    type_name = 'Fixed Provider'
    type_type = 'FixedProvider'
    type_description = 'Fixed Provider description'

    offers = [FixedTestingService]
