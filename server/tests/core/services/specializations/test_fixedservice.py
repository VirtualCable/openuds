# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
from uds import models
from uds.core import types, services
from ....utils.test import UDSTestCase

from uds.core.services.specializations.fixed_machine import fixed_service, fixed_userservice


class FixedServiceTest(UDSTestCase):
    pass


class FixedUserService(fixed_userservice.FixedUserService):
    started: bool = False
    counter: int = 0

    def _start_machine(self) -> None:
        self.started = True
        self.counter = 2

    def _stop_machine(self) -> None:
        self.started = False
        self.counter = 2

    def _start_checker(self) -> str:
        self.counter = self.counter - 1
        if self.counter <= 0:
            return types.states.State.FINISHED
        return types.states.State.RUNNING

    def _stop_checker(self) -> str:
        self.counter = self.counter - 1
        if self.counter <= 0:
            return types.states.State.FINISHED
        return types.states.State.RUNNING


class FixedService(fixed_service.FixedService):
    token = fixed_service.FixedService.token
    snapshot_type = fixed_service.FixedService.snapshot_type
    machines = fixed_service.FixedService.machines

    snapshot_proccessed: bool = False
    is_remove_snapshot: bool = False
    assigned_machine: str = ''

    user_service_type = FixedUserService

    def process_snapshot(self, remove: bool, userservice_instace: fixed_userservice.FixedUserService) -> str:
        self.snapshot_proccessed = True
        self.is_remove_snapshot = remove
        return super().process_snapshot(remove, userservice_instace)

    def get_machine_name(self, vmid: str) -> str:
        return f'Machine {vmid}'

    def get_and_assign_machine(self) -> str:
        self.assigned_machine = 'assigned'
        return self.assigned_machine

    def remove_and_free_machine(self, vmid: str) -> str:
        self.assigned_machine = ''
        return types.states.State.FINISHED

    def get_first_network_mac(self, vmid: str) -> str:
        raise NotImplementedError()

    def get_guest_ip_address(self, vmid: str) -> str:
        raise NotImplementedError()

    def enumerate_assignables(self) -> list[tuple[str, str]]:
        """
        Returns a list of tuples with the id and the name of the assignables
        """
        return [
            ('1', 'Machine 1'),
            ('2', 'Machine 2'),
            ('3', 'Machine 3'),
        ]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> str:
        """
        Assigns a machine from the assignables
        """
        return types.states.State.FINISHED


class FixedProvider(services.provider.ServiceProvider):
    offers = [FixedService]
