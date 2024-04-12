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
from unittest.mock import call

from uds import models
from uds.core import types
from ....utils.test import UDSTestCase
from ....utils import MustBeOfType
from ....utils.generators import limited_iterator
from . import fixtures


@dataclasses.dataclass
class DynamicServiceIterationInfo:
    queue: list[types.services.Operation]
    service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    user_service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    state: str = types.states.TaskState.RUNNING

    def __mul__(self, other: int) -> list['DynamicServiceIterationInfo']:
        return [self] * other


class DynamicServiceTest(UDSTestCase):
    def check_iterations(
        self,
        service: 'fixtures.DynamicTestingService',
        userservice: 'fixtures.DynamicTestingUserServiceQueue',
        iterations_info: list[DynamicServiceIterationInfo],
    ) -> None:
        first: bool = True

        for iteration, info in enumerate(iterations_info, 1):
            # Clear mocks
            service.mock.reset_mock()
            userservice.mock.reset_mock()

            if first:  # First iteration is call for deploy
                state = userservice.deploy_for_user(models.User())
                first = False
            else:
                state = userservice.check_state()
            self.assertEqual(
                state, info.state, f' ************ State: {iteration} {state}: {userservice._reason}'
            )

            # Assert queues are the same, and if not, show the difference ONLY
            diff = set(info.queue) ^ set(userservice._queue)
            self.assertEqual(
                userservice._queue,
                info.queue,
                f' ************ Queue: {iteration} {diff}',
            )
            self.assertEqual(
                service.mock.mock_calls,
                info.service_calls,
                f' ************ Service calls: {iteration} {service.mock.mock_calls}',
            )
            self.assertEqual(
                userservice.mock.mock_calls,
                info.user_service_calls,
                f'************ Userservice calls: {iteration} {userservice.mock.mock_calls}',
            )

    def test_userservice_queue_works_fine(self) -> None:
        service = fixtures.create_dynamic_service()
        service.machine_running_flag = False
        userservice = fixtures.create_dynamic_userservice_queue(service)
        userservice._vmid = 'vmid'
        self.check_iterations(service, userservice, EXPECTED_DEPLOY_ITERATIONS_INFO)

    def test_userservice_deploy_for_user(self) -> None:
        service = fixtures.create_dynamic_service()
        userservice = fixtures.create_dynamic_userservice(service)

        state = userservice.deploy_for_user(models.User())
        self.assertEqual(state, types.states.TaskState.RUNNING)

        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            state = userservice.check_state()

        self.assertEqual(state, types.states.TaskState.FINISHED)
        service.mock.start.assert_called_once_with(userservice, userservice._vmid)
        self.assertEqual(service.mock.is_running.call_count, 2)

    def test_userservice_deploy_for_cache_l1(self) -> None:
        service = fixtures.create_dynamic_service()
        service.machine_running_flag = False
        userservice = fixtures.create_dynamic_userservice(service)

        state = userservice.deploy_for_cache(types.services.CacheLevel.L1)
        self.assertEqual(state, types.states.TaskState.RUNNING)

        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            state = userservice.check_state()

        self.assertEqual(state, types.states.TaskState.FINISHED)
        service.mock.start.assert_called_once_with(userservice, userservice._vmid)
        self.assertEqual(service.mock.is_running.call_count, 2)

    def test_userservice_deploy_for_cache_l2(self) -> None:
        service = fixtures.create_dynamic_service()
        service.machine_running_flag = False
        userservice = fixtures.create_dynamic_userservice(service)

        state = userservice.deploy_for_cache(types.services.CacheLevel.L2)
        self.assertEqual(state, types.states.TaskState.RUNNING)

        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            # if cache is L2, will be stuck on types.services.Operations.WAIT until wake up
            if userservice._queue[0] == types.services.Operation.WAIT:
                state = userservice.process_ready_from_os_manager('')  # Wake up
            else:
                state = userservice.check_state()

        self.assertEqual(state, types.states.TaskState.FINISHED)
        service.mock.start.assert_called_once_with(userservice, userservice._vmid)
        # is_running must has been called 3 times:
        # * Before starting, to ensure it's not running
        # * for start check
        # * for suspend check before suspend (to ensure it's running)
        # * for check_suspend after suspend
        self.assertEqual(service.mock.is_running.call_count, 4)
        service.mock.is_running.assert_called_with(userservice, userservice._vmid)
        # And shutdown must be called once
        service.mock.shutdown.assert_called_once_with(userservice, userservice._vmid)

    def test_userservice_removal(self) -> None:
        service = fixtures.create_dynamic_service()
        userservice = fixtures.create_dynamic_userservice(service)

        userservice._vmid = ''
        # If no vmid, will stop after first step
        state = userservice.destroy()
        self.assertEqual(state, types.states.TaskState.RUNNING)
        state = userservice.check_state()
        self.assertEqual(state, types.states.TaskState.FINISHED)

        # With vmid, will go through all the steps
        userservice._vmid = 'vmid'
        service.machine_running_flag = True

        userservice.mock.reset_mock()
        service.mock.reset_mock()

        state = userservice.destroy()
        self.assertEqual(state, types.states.TaskState.RUNNING)

        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            state = userservice.check_state()

        self.assertEqual(state, types.states.TaskState.FINISHED)
        service.mock.stop.assert_called_once_with(userservice, userservice._vmid)
        service.mock.is_running.assert_called_with(userservice, userservice._vmid)
        self.assertEqual(service.mock.is_running.call_count, 2)

        service.mock.remove.assert_called_once_with(userservice, userservice._vmid)

    def test_userservice_maintain_on_error_no_created(self) -> None:
        service = fixtures.create_dynamic_service(maintain_on_error=True)
        userservice = fixtures.create_dynamic_userservice(service)
        self.assertFalse(service.allows_errored_userservice_cleanup())
        self.assertTrue(service.should_maintain_on_error())

        state = userservice.deploy_for_user(models.User())
        self.assertEqual(state, types.states.TaskState.RUNNING)

        # Force failure
        userservice._queue = [types.services.Operation.CUSTOM_1]
        self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
        self.assertEqual(userservice.error_reason(), 'CUSTOM_1')

    def test_userservice_maintain_on_error_created(self) -> None:
        service = fixtures.create_dynamic_service(maintain_on_error=True)
        userservice = fixtures.create_dynamic_userservice(service)
        self.assertFalse(service.allows_errored_userservice_cleanup())
        self.assertTrue(service.should_maintain_on_error())

        state = userservice.deploy_for_user(models.User())
        self.assertEqual(state, types.states.TaskState.RUNNING)
        # Again, to execute "CREATE"
        state = userservice.check_state()
        self.assertEqual(state, types.states.TaskState.RUNNING)
        self.assertTrue(userservice._vmid != '')

        # Now, force failure (will be raise on op_custom_1_checker)
        userservice._queue = [types.services.Operation.CUSTOM_1]
        # Now, no error should be returned, but finish
        self.assertEqual(userservice.check_state(), types.states.TaskState.FINISHED)
        self.assertTrue(userservice._error_debug_info != '')

    def test_userservice_try_soft_shutdown(self) -> None:
        service = fixtures.create_dynamic_service(try_soft_shutdown=True)
        userservice = fixtures.create_dynamic_userservice(service)
        self.assertTrue(service.try_graceful_shutdown())

        # full deploy
        state = userservice.deploy_for_user(models.User())
        self.assertEqual(state, types.states.TaskState.RUNNING)
        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            state = userservice.check_state()

        # Now, destroy it. Should call shutdown instead of stop
        service.mock.reset_mock()
        userservice.mock.reset_mock()

        state = userservice.destroy()
        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            state = userservice.check_state()

        self.assertEqual(state, types.states.TaskState.FINISHED)

        service.mock.shutdown.assert_called_once_with(userservice, userservice._vmid)

    def test_userservice_set_ready(self) -> None:
        service = fixtures.create_dynamic_service()
        userservice = fixtures.create_dynamic_userservice(service)

        # full deploy
        state = userservice.deploy_for_user(models.User())
        self.assertEqual(state, types.states.TaskState.RUNNING)
        for _ in limited_iterator(lambda: state != types.states.TaskState.FINISHED, limit=128):
            state = userservice.check_state()

        # Call for set_ready
        service.mock.reset_mock()
        self.assertEqual(userservice.set_ready(), types.states.TaskState.FINISHED)
        # is_ready should have been called
        service.mock.is_running.assert_called_once()

    def test_userservice_max_retries_executor(self) -> None:
        service = fixtures.create_dynamic_service()
        userservice = fixtures.create_dynamic_userservice(service)
        userservice._queue = [
            types.services.Operation.NOP,
            types.services.Operation.CUSTOM_3,
            types.services.Operation.CUSTOM_3,
            types.services.Operation.FINISH,
        ]

        fixtures.DynamicTestingUserService.max_retries = 5

        state = types.states.TaskState.RUNNING
        counter = 0
        for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
            if counter == 5:
                # Replace the first item in queue to NOP, so next check will fail
                userservice._queue[0] = types.services.Operation.NOP
            state = userservice.check_state()

        self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
        self.assertEqual(userservice.error_reason(), 'Max retries reached')
        self.assertEqual(
            counter, 11
        )  # 4 retries + 5 retries after reset + 1 of the reset itself + 1 of initial NOP

    def test_userservice_max_retries_checker(self) -> None:
        service = fixtures.create_dynamic_service()
        userservice = fixtures.create_dynamic_userservice(service)
        userservice._queue = [
            types.services.Operation.CUSTOM_2,
            types.services.Operation.CUSTOM_2,
            types.services.Operation.FINISH,
        ]

        fixtures.DynamicTestingUserService.max_retries = 5

        state = types.states.TaskState.RUNNING
        counter = 0
        for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
            if counter == 4:
                # Replace the first item in queue to NOP, so next check will fail
                userservice._queue[0] = types.services.Operation.NOP
            state = userservice.check_state()

        self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
        self.assertEqual(userservice.error_reason(), 'Max retries reached')
        self.assertEqual(counter, 10)  # 4 retries + 5 retries after reset + 1 of the reset itself


EXPECTED_DEPLOY_ITERATIONS_INFO: typing.Final[list[DynamicServiceIterationInfo]] = [
    # Initial state for queue
    DynamicServiceIterationInfo(  # 1, INITIALIZE
        queue=fixtures.ALL_TESTEABLE_OPERATIONS,
        user_service_calls=[
            call.initialize(),
        ],
    ),
    DynamicServiceIterationInfo(  # 2, CREATE
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[1:],
        user_service_calls=[call.initialize_checker(), call.create()],
    ),
    DynamicServiceIterationInfo(  # 3, CREATE_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[2:],
        user_service_calls=[call.create_checker(), call.create_completed()],
    ),
    DynamicServiceIterationInfo(  # 4, START
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[3:],
        user_service_calls=[call.create_completed_checker()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
            call.start(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
        ],
    ),
    DynamicServiceIterationInfo(  # 5, START_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[4:],
        user_service_calls=[call.start_completed()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str))
        ],
    ),
    DynamicServiceIterationInfo(  # 6, STOP
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[5:],
        user_service_calls=[call.start_completed_checker()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
            call.stop(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
        ],
    ),
    DynamicServiceIterationInfo(  # 7, STOP_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[6:],
        user_service_calls=[call.stop_completed()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str))
        ],
    ),
    DynamicServiceIterationInfo(  # 8, SHUTDOWN
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[7:],
        user_service_calls=[call.stop_completed_checker()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
        ],
    ),
    DynamicServiceIterationInfo(  # 9, SHUTDOWN_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[8:],
        user_service_calls=[call.shutdown_completed()],
    ),
    DynamicServiceIterationInfo(  # 10, SUSPEND
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[9:],
        user_service_calls=[call.shutdown_completed_checker(), call.suspend()],
        service_calls=[],
    ),
    DynamicServiceIterationInfo(  # 11, SUSPEND_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[10:],
        user_service_calls=[call.suspend_checker(), call.suspend_completed()],
        service_calls=[],
    ),
    DynamicServiceIterationInfo(  # 12, RESET
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[11:],
        user_service_calls=[call.suspend_completed_checker()],
        service_calls=[
            call.reset(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
            # In turn, calls stop by default
            call.stop(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str)),
        ],
    ),
    DynamicServiceIterationInfo(  # 13, RESET_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[12:],
        user_service_calls=[call.reset_checker(), call.reset_completed()],
    ),
    DynamicServiceIterationInfo(  # 14, REMOVE
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[13:],
        user_service_calls=[call.reset_completed_checker()],
        service_calls=[call.remove(MustBeOfType(fixtures.DynamicTestingUserServiceQueue), MustBeOfType(str))],
    ),
    DynamicServiceIterationInfo(  # 15, REMOVE_COMPLETED
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[14:],
        user_service_calls=[call.remove_checker(), call.remove_completed()],
    ),
    DynamicServiceIterationInfo(  # 16, WAIT
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[15:],
        user_service_calls=[call.remove_completed_checker(), call.wait()],
    ),
    DynamicServiceIterationInfo(
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[16:],
        user_service_calls=[call.wait_checker(), call.nop()],
    ),  # 17, NOP
    DynamicServiceIterationInfo(  # 18, DESTROY_VALIDATOR
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[17:],
        user_service_calls=[call.nop_checker(), call.destroy_validator()],
    ),
    DynamicServiceIterationInfo(  # 19, CUSTOM_1
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[18:],
        user_service_calls=[call.destroy_validator_checker(), call.custom(types.services.Operation.CUSTOM_1)],
    ),
    DynamicServiceIterationInfo(  # 20, CUSTOM_2
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[19:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_1),
            call.custom(types.services.Operation.CUSTOM_2),
        ],
    ),
    DynamicServiceIterationInfo(  # 21, CUSTOM_3
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[20:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_2),
            call.custom(types.services.Operation.CUSTOM_3),
        ],
    ),
    DynamicServiceIterationInfo(  # 22, CUSTOM_4
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[21:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_3),
            call.custom(types.services.Operation.CUSTOM_4),
        ],
    ),
    DynamicServiceIterationInfo(  # 23, CUSTOM_5
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[22:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_4),
            call.custom(types.services.Operation.CUSTOM_5),
        ],
    ),
    DynamicServiceIterationInfo(  # 24, CUSTOM_6
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[23:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_5),
            call.custom(types.services.Operation.CUSTOM_6),
        ],
    ),
    DynamicServiceIterationInfo(  # 25, CUSTOM_7
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[24:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_6),
            call.custom(types.services.Operation.CUSTOM_7),
        ],
    ),
    DynamicServiceIterationInfo(  # 26, CUSTOM_8
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[25:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_7),
            call.custom(types.services.Operation.CUSTOM_8),
        ],
    ),
    DynamicServiceIterationInfo(  # 27, CUSTOM_9
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[26:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_8),
            call.custom(types.services.Operation.CUSTOM_9),
        ],
    ),
    DynamicServiceIterationInfo(
        queue=fixtures.ALL_TESTEABLE_OPERATIONS[27:],
        state=types.states.TaskState.FINISHED,
        user_service_calls=[call.custom_checker(types.services.Operation.CUSTOM_9)],
    ),  # 28, FINISH
]
