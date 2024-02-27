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
import dataclasses
import typing
import collections.abc
from unittest import mock

from uds import models
from uds.core import services, types
from uds.core.services.specializations.fixed_machine import (
    fixed_service,
    fixed_userservice,
)
from uds.core.ui.user_interface import gui

from ....utils.test import UDSTestCase


@dataclasses.dataclass
class FixedServiceIterationInfo:
    queue: list[fixed_userservice.Operation]
    service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    user_service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    state: str = types.states.TaskState.RUNNING

    def __mul__(self, other: int) -> list['FixedServiceIterationInfo']:
        return [self] * other


EXPECTED_DEPLOY_ITERATIONS_INFO: typing.Final[list[FixedServiceIterationInfo]] = [
    # Initial state for queue
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.CREATE,
            fixed_userservice.Operation.SNAPSHOT_CREATE,
            fixed_userservice.Operation.PROCESS_TOKEN,
            fixed_userservice.Operation.START,
            fixed_userservice.Operation.FINISH,
        ],
        service_calls=[
            mock.call.get_and_assign_machine(),
            mock.call.get_first_network_mac('assigned'),
            mock.call.get_machine_name('assigned'),
        ],
    ),
    # Machine has no snapshot, and it's running, try to stop
    # (this is what our testing example does, but maybe it's not the best approach for all services)
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.NOP,
            fixed_userservice.Operation.STOP,
            fixed_userservice.Operation.SNAPSHOT_CREATE,
            fixed_userservice.Operation.PROCESS_TOKEN,
            fixed_userservice.Operation.START,
            fixed_userservice.Operation.FINISH,
        ],
        service_calls=[
            mock.call.process_snapshot(False, mock.ANY),
        ],
    ),
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.STOP,
            fixed_userservice.Operation.SNAPSHOT_CREATE,
            fixed_userservice.Operation.PROCESS_TOKEN,
            fixed_userservice.Operation.START,
            fixed_userservice.Operation.FINISH,
        ],
        user_service_calls=[mock.call._stop_machine()],
    ),
    # The current operation is snapshot, so check previous operation (Finished) and then process snapshot
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.SNAPSHOT_CREATE,
            fixed_userservice.Operation.PROCESS_TOKEN,
            fixed_userservice.Operation.START,
            fixed_userservice.Operation.FINISH,
        ],
        service_calls=[
            mock.call.process_snapshot(False, mock.ANY),
        ],
        user_service_calls=[mock.call._stop_checker()],
    ),
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.PROCESS_TOKEN,
            fixed_userservice.Operation.START,
            fixed_userservice.Operation.FINISH,
        ],
        user_service_calls=[mock.call.db_obj()],
    ),
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.START,
            fixed_userservice.Operation.FINISH,
        ],
        user_service_calls=[mock.call._start_machine()],
    ),
    # When in queue is only finish, it's the last iteration
    # (or if queue is empty, but that's not the case here)
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.FINISH,
        ],
        user_service_calls=[mock.call._start_checker()],
        state=types.states.TaskState.FINISHED,
    ),
]

EXPECTED_REMOVAL_ITERATIONS_INFO: typing.Final[list[FixedServiceIterationInfo]] = [
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.REMOVE,
            fixed_userservice.Operation.SNAPSHOT_RECOVER,
            fixed_userservice.Operation.FINISH,
        ],
        service_calls=[mock.call.remove_and_free_machine('assigned')],
    ),
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.SNAPSHOT_RECOVER,
            fixed_userservice.Operation.FINISH,
        ],
        service_calls=[mock.call.process_snapshot(True, mock.ANY)],
    ),
    FixedServiceIterationInfo(
        queue=[
            fixed_userservice.Operation.FINISH,
        ],
        state=types.states.TaskState.FINISHED,
    ),
]


class FixedServiceTest(UDSTestCase):
    def create_elements(
        self,
    ) -> tuple['FixedTestingProvider', 'FixedTestingService', 'FixedTestingUserService']:
        environment = self.create_environment()
        prov = FixedTestingProvider(environment=environment)
        service = FixedTestingService(environment=environment, provider=prov)
        user_service = FixedTestingUserService(environment=environment, service=service)

        return prov, service, user_service

    def check_iterations(
        self,
        service: 'FixedTestingService',
        userservice: 'FixedTestingUserService',
        iterations: list[FixedServiceIterationInfo],
        removal: bool,
    ) -> None:
        first: bool = True

        for iteration in iterations:
            # Clear mocks
            service.mock.reset_mock()
            userservice.mock.reset_mock()

            if first:  # First iteration is call for deploy
                if not removal:
                    state = userservice.deploy_for_user(models.User())
                else:
                    state = userservice.destroy()
                first = False
            else:
                state = userservice.check_state()
            self.assertEqual(state, iteration.state, f'Iteration {iteration} {state}')
            self.assertEqual(
                userservice._queue,
                iteration.queue,
                f'Iteration {iteration} {userservice._queue} {iteration.queue}',
            )
            self.assertEqual(
                service.mock.mock_calls,
                iteration.service_calls,
                f'Iteration {iteration} {userservice._queue}',
            )
            self.assertEqual(
                userservice.mock.mock_calls,
                iteration.user_service_calls,
                f'Iteration {iteration} {userservice._queue}',
            )

    def deploy_service(
        self, service: 'FixedTestingService', userservice: 'FixedTestingUserService', max_iterations: int = 100
    ) -> None:
        if userservice.deploy_for_user(models.User()) != types.states.TaskState.FINISHED:
            while userservice.check_state() != types.states.TaskState.FINISHED and max_iterations > 0:
                max_iterations -= 1

        # Clear mocks
        service.mock.reset_mock()
        userservice.mock.reset_mock()

    def test_fixed_service_deploy(self) -> None:
        _prov, service, userservice = self.create_elements()
        self.check_iterations(service, userservice, EXPECTED_DEPLOY_ITERATIONS_INFO, removal=False)
        
    def test_fixed_service_deploy_no_machine(self) -> None:
        _prov, service, userservice = self.create_elements()
        service.available_machines_number = 2
        self.deploy_service(service, userservice)  # Should be deployed without issues
        self.deploy_service(service, userservice)  # Should be deployed without issues, 2nd time
        # And now, should fail to deploy again
        self.assertRaises(Exception, self.deploy_service, service, userservice)

    def test_fixed_service_removal(self) -> None:
        _prov, service, userservice = self.create_elements()

        # Ensure fully deployed state for userservice
        self.deploy_service(service, userservice)

        # Userservice is in deployed state, so we can remove it
        self.check_iterations(service, userservice, EXPECTED_REMOVAL_ITERATIONS_INFO, removal=True)


class FixedTestingUserService(fixed_userservice.FixedUserService):
    mock: 'mock.Mock' = mock.MagicMock()

    def _start_machine(self) -> None:
        self.mock._start_machine()

    def _stop_machine(self) -> None:
        self.mock._stop_machine()

    def _start_checker(self) -> types.states.TaskState:
        self.mock._start_checker()
        return types.states.TaskState.FINISHED

    def _stop_checker(self) -> types.states.TaskState:
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
            userservice_instance._push_front_op(fixed_userservice.Operation.STOP)
            userservice_instance._push_front_op(fixed_userservice.Operation.NOP)
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
            gui.choice_item('1', 'Machine 1'),
            gui.choice_item('2', 'Machine 2'),
            gui.choice_item('3', 'Machine 3'),
        ]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> str:
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
