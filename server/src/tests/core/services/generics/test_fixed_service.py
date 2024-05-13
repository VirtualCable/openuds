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
import dataclasses
import typing
from unittest import mock

from uds import models
from uds.core import types
from ....utils.test import UDSTestCase
from ....utils.generators import limited_iterator
from . import fixtures


@dataclasses.dataclass
class FixedServiceIterationInfo:
    queue: list[types.services.Operation]
    service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    user_service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    state: str = types.states.TaskState.RUNNING

    def __mul__(self, other: int) -> list['FixedServiceIterationInfo']:
        return [self] * other


EXPECTED_DEPLOY_ITERATIONS_INFO: typing.Final[list[FixedServiceIterationInfo]] = [
    # Initial state for queue
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.CREATE,
            types.services.Operation.SNAPSHOT_CREATE,
            types.services.Operation.PROCESS_TOKEN,
            types.services.Operation.START,
            types.services.Operation.FINISH,
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
            types.services.Operation.NOP,
            types.services.Operation.STOP,
            types.services.Operation.SNAPSHOT_CREATE,
            types.services.Operation.PROCESS_TOKEN,
            types.services.Operation.START,
            types.services.Operation.FINISH,
        ],
        service_calls=[
            mock.call.snapshot_creation(mock.ANY),
        ],
    ),
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.STOP,
            types.services.Operation.SNAPSHOT_CREATE,
            types.services.Operation.PROCESS_TOKEN,
            types.services.Operation.START,
            types.services.Operation.FINISH,
        ],
        user_service_calls=[mock.call.op_stop()],
    ),
    # The current operation is snapshot, so check previous operation (Finished) and then process snapshot
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.SNAPSHOT_CREATE,
            types.services.Operation.PROCESS_TOKEN,
            types.services.Operation.START,
            types.services.Operation.FINISH,
        ],
        service_calls=[
            mock.call.snapshot_creation(mock.ANY),
        ],
        user_service_calls=[mock.call.op_stop_checker()],
    ),
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.PROCESS_TOKEN,
            types.services.Operation.START,
            types.services.Operation.FINISH,
        ],
        user_service_calls=[mock.call.db_obj()],
    ),
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.START,
            types.services.Operation.FINISH,
        ],
        user_service_calls=[mock.call.op_start()],
    ),
    # When in queue is only finish, it's the last iteration
    # (or if queue is empty, but that's not the case here)
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.FINISH,
        ],
        user_service_calls=[mock.call.op_start_checker()],
        state=types.states.TaskState.FINISHED,
    ),
]

EXPECTED_REMOVAL_ITERATIONS_INFO: typing.Final[list[FixedServiceIterationInfo]] = [
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.DELETE,
            types.services.Operation.SNAPSHOT_RECOVER,
            types.services.Operation.FINISH,
        ],
        service_calls=[mock.call.remove_and_free_machine('assigned')],
    ),
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.SNAPSHOT_RECOVER,
            types.services.Operation.FINISH,
        ],
        service_calls=[mock.call.snapshot_recovery(mock.ANY)],
    ),
    FixedServiceIterationInfo(
        queue=[
            types.services.Operation.FINISH,
        ],
        state=types.states.TaskState.FINISHED,
    ),
]


class FixedServiceTest(UDSTestCase):
    def create_elements(
        self,
    ) -> tuple[
        'fixtures.FixedTestingProvider', 'fixtures.FixedTestingService', 'fixtures.FixedTestingUserService'
    ]:
        provider = fixtures.create_fixed_provider()
        service = fixtures.create_fixed_service(provider=provider)
        user_service = fixtures.create_fixed_user_service(service=service)
        return provider, service, user_service

    def check_iterations(
        self,
        service: 'fixtures.FixedTestingService',
        userservice: 'fixtures.FixedTestingUserService',
        iterations: list[FixedServiceIterationInfo],
        removal: bool,
    ) -> None:
        first: bool = True

        for num, iteration in enumerate(iterations, start=1):
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
            # Assert queues are the same, and if not, show the difference ONLY
            diff = [x for x in iteration.queue if x not in userservice._queue]
            self.assertEqual(
                userservice._queue,
                iteration.queue,
                f'Iteration {num} {iteration} {diff}',
            )
            diff_mock_calls = [x for x in iteration.service_calls if x not in service.mock.mock_calls]
            self.assertEqual(
                service.mock.mock_calls,
                iteration.service_calls,
                f'Iteration {num} {iteration} {diff_mock_calls}',
            )
            diff_mock_calls = [x for x in iteration.user_service_calls if x not in userservice.mock.mock_calls]
            self.assertEqual(
                userservice.mock.mock_calls,
                iteration.user_service_calls,
                f'Iteration {num} {iteration} {diff_mock_calls}',
            )

    def deploy_service(
        self,
        service: 'fixtures.FixedTestingService',
        userservice: 'fixtures.FixedTestingUserService',
        max_iterations: int = 100,
    ) -> None:
        if userservice.deploy_for_user(models.User()) != types.states.TaskState.FINISHED:
            while userservice.check_state() != types.states.TaskState.FINISHED and max_iterations > 0:
                max_iterations -= 1

        # Clear mocks
        service.mock.reset_mock()
        userservice.mock.reset_mock()

    def test_service_deploy(self) -> None:
        _prov, service, userservice = self.create_elements()
        self.check_iterations(service, userservice, EXPECTED_DEPLOY_ITERATIONS_INFO, removal=False)

    def test_service_deploy_no_machine(self) -> None:
        _prov, service, userservice = self.create_elements()
        service.available_machines_number = 2
        self.deploy_service(service, userservice)  # Should be deployed without issues
        self.deploy_service(service, userservice)  # Should be deployed without issues, 2nd time
        # And now, should fail to deploy again
        self.assertRaises(Exception, self.deploy_service, service, userservice)

    def test_service_removal(self) -> None:
        _prov, service, userservice = self.create_elements()

        # Ensure fully deployed state for userservice
        self.deploy_service(service, userservice)

        # Userservice is in deployed state, so we can remove it
        self.check_iterations(service, userservice, EXPECTED_REMOVAL_ITERATIONS_INFO, removal=True)
        
    def test_service_set_ready(self) -> None:
        _prov, service, userservice = self.create_elements()
        self.deploy_service(service, userservice)
        # Call for set_ready
        self.assertEqual(userservice.set_ready(), types.states.TaskState.FINISHED)
        # is_ready should have been called
        service.mock.is_ready.assert_called_once()

    def test_service_random_machine_list(self) -> None:
        _prov, service, _userservice = self.create_elements()
        service.machines.value = [f'machine{i}' for i in range(10)]
        for randomized in (True, False):
            service.randomize.value = randomized
            machines_list = service.sorted_assignables_list()
            if randomized:
                self.assertNotEqual(machines_list, service.machines.value)
                self.assertEqual(len(service.machines.value), len(machines_list))
                self.assertEqual(sorted(service.machines.value), sorted(machines_list))
            else:
                self.assertEqual(machines_list, service.machines.value)

    def test_service_keep_on_error(self) -> None:
        for maintain_on_error in (True, False):
            _prov, service, userservice = self.create_elements()
            service.machines.value = [f'machine{i}' for i in range(10)]
            service.maintain_on_error.value = maintain_on_error
            self.deploy_service(service, userservice)
            self.assertEqual(userservice.check_state(), types.states.TaskState.FINISHED)
            
            # Now, ensure that we will raise an exception, overriding is_ready of service
            service.is_ready = mock.MagicMock(side_effect=Exception('Error'))
            if maintain_on_error is False:
                self.assertEqual(userservice.set_ready(), types.states.TaskState.ERROR)
            else:
                self.assertEqual(userservice.set_ready(), types.states.TaskState.FINISHED)
            
    def test_userservice_maintain_on_error_no_created(self) -> None:
        _prov, service, userservice = self.create_elements()
        service.maintain_on_error.value = True
        self.assertFalse(service.allows_errored_userservice_cleanup())
        self.assertTrue(service.should_maintain_on_error())

        # Force failure
        # patch userservice op_start_checker to raise an exception
        with mock.patch.object(userservice, 'op_start_checker', side_effect=Exception('Error')):
            userservice._queue = [types.services.Operation.START]
            userservice._vmid = ''
            self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
            self.assertEqual(userservice.error_reason(), 'Error')

    def test_userservice_maintain_on_error_created(self) -> None:
        _prov, service, userservice = self.create_elements()
        service.maintain_on_error.value = True
        self.assertFalse(service.allows_errored_userservice_cleanup())
        self.assertTrue(service.should_maintain_on_error())

        # Force failure
        # patch userservice op_start_checker to raise an exception, but with a vmid
        with mock.patch.object(userservice, 'op_start_checker', side_effect=Exception('Error')):
            userservice._queue = [types.services.Operation.START]
            userservice._vmid = 'vmid'
            self.assertEqual(userservice.check_state(), types.states.TaskState.FINISHED)

    def test_userservice_max_retries_executor(self) -> None:
        _prov, _service, userservice = self.create_elements()
        # Patch userservice op_start to call retry_later()
        with mock.patch.object(userservice, 'op_start', side_effect=userservice.retry_later):
            userservice._queue = [
                types.services.Operation.NOP,
                types.services.Operation.START,
                types.services.Operation.START,
                types.services.Operation.FINISH,
            ]

            fixtures.FixedTestingUserService.max_retries = 5

            state = types.states.TaskState.RUNNING
            counter = 0
            for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                if counter == 5:
                    # Replace the first item in queue to NOP, so next check will fail
                    userservice._queue[0] = types.services.Operation.NOP
                state = userservice.check_state()

            self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
            self.assertEqual(userservice.error_reason(), 'Max retries reached')
            self.assertEqual(counter, 11)  # 4 retries + 5 retries after reset + 1 of the reset itself + 1 of initial NOP

    def test_userservice_max_retries_checker(self) -> None:
        _prov, _service, userservice = self.create_elements()
        # Patch userservice op_start to call retry_later()
        with mock.patch.object(userservice, 'op_start_checker', side_effect=userservice.retry_later):
            userservice._queue = [
                types.services.Operation.START,
                types.services.Operation.START,
                types.services.Operation.FINISH,
            ]

            fixtures.FixedTestingUserService.max_retries = 5

            state = types.states.TaskState.RUNNING
            counter = 0
            for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                if counter == 4:
                    # Replace the first item in queue to NOP, so next check will fail
                    userservice._queue[0] = types.services.Operation.NOP
                state = userservice.check_state()

            self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
            self.assertIsInstance(userservice.error_reason(), str)
            self.assertEqual(counter, 10)  # 4 retries + 5 retries after reset + 1 of the reset itself
