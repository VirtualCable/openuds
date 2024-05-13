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

from uds.core import types

from ....utils.generators import limited_iterator
from ....utils.test import UDSTestCase
from ....utils import MustBeOfType

# from ....utils.generators import limited_iterator
from . import fixtures


@dataclasses.dataclass
class DynamicPublicationIterationInfo:
    queue: list[types.services.Operation]
    service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    user_service_calls: list[mock._Call] = dataclasses.field(default_factory=list)
    state: str = types.states.TaskState.RUNNING

    def __mul__(self, other: int) -> list['DynamicPublicationIterationInfo']:
        return [self] * other


class DynamicPublicationTest(UDSTestCase):
    def check_iterations(
        self,
        service: 'fixtures.DynamicTestingService',
        publication: 'fixtures.DynamicTestingPublicationQueue',
        iterations_info: list[DynamicPublicationIterationInfo],
    ) -> None:
        self.maxDiff = None
        first: bool = True

        for iteration, info in enumerate(iterations_info, 1):
            # Clear mocks
            service.mock.reset_mock()
            publication.mock.reset_mock()

            if first:  # First iteration is call for deploy
                state = publication.publish()
                first = False
            else:
                state = publication.check_state()
            self.assertEqual(
                state, info.state, f' ************ State: {iteration} {state}: {publication._reason}'
            )

            # Assert queues are the same, and if not, show the difference ONLY
            diff = set(info.queue) ^ set(publication._queue)
            self.assertEqual(
                publication._queue,
                info.queue,
                f' ************ Queue: {iteration} {diff}',
            )
            self.assertEqual(
                service.mock.mock_calls,
                info.service_calls,
                f' ************ Service calls: {iteration} {service.mock.mock_calls}',
            )
            self.assertEqual(
                publication.mock.mock_calls,
                info.user_service_calls,
                f'************ Userservice calls: {iteration} {publication.mock.mock_calls}',
            )

    def test_publication_queue_works_fine(self) -> None:
        service = fixtures.create_dynamic_service()
        publication = fixtures.create_dynamic_publication_queue(service)
        self.check_iterations(service, publication, EXPECTED_DEPLOY_ITERATIONS_INFO)

    def test_publication_fails_on_initialize(self) -> None:
        service = fixtures.create_dynamic_service()
        publication = fixtures.create_dynamic_publication(service)
        # Mock op_initialize and make it fail with an exception
        with mock.patch.object(publication, 'op_initialize', side_effect=Exception('Test')):
            state = publication.publish()
            self.assertEqual(state, types.states.TaskState.ERROR)
            # Check that the reason is the exception
            self.assertEqual(publication._reason, 'Test')
            # Check that the queue is empty (only ERROR operation)
            self.assertEqual(publication._queue, [types.services.Operation.ERROR])

    def test_publication_fails_on_create(self) -> None:
        service = fixtures.create_dynamic_service()
        publication = fixtures.create_dynamic_publication(service)
        # Mock op_create and make it fail with an exception
        with mock.patch.object(publication, 'op_create', side_effect=Exception('Test')):
            state = publication.publish()  # Firt iteration is INITIALIZE
            self.assertEqual(state, types.states.TaskState.RUNNING)  # Should work
            state = publication.check_state()  # Second iteration is CREATE
            self.assertEqual(state, types.states.TaskState.ERROR)
            # Check that the reason is the exception
            self.assertEqual(publication._reason, 'Test')
            # Check that the queue is empty (only ERROR operation)
            self.assertEqual(publication._queue, [types.services.Operation.ERROR])

    def test_publication_fails_on_create_completed(self) -> None:
        service = fixtures.create_dynamic_service()
        publication = fixtures.create_dynamic_publication(service)
        # Mock op_create_completed and make it fail with an exception
        with mock.patch.object(publication, 'op_create_completed', side_effect=Exception('Test')):
            state = publication.publish()
            self.assertEqual(state, types.states.TaskState.RUNNING)  # Should work
            state = publication.check_state()
            self.assertEqual(state, types.states.TaskState.RUNNING)  # Should work
            state = publication.check_state()
            self.assertEqual(state, types.states.TaskState.ERROR)
            # Check that the reason is the exception
            self.assertEqual(publication._reason, 'Test')
            # Check that the queue is empty (only ERROR operation)
            self.assertEqual(publication._queue, [types.services.Operation.ERROR])

    def test_publication_max_retries_executor(self) -> None:
        service = fixtures.create_dynamic_service()
        publication = fixtures.create_dynamic_publication(service)
        publication._queue = [
            types.services.Operation.NOP,
            types.services.Operation.CUSTOM_3,
            types.services.Operation.CUSTOM_3,
            types.services.Operation.FINISH,
        ]

        fixtures.DynamicTestingPublication.max_retries = 5

        state = types.states.TaskState.RUNNING
        counter = 0
        for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
            if counter == 5:
                # Replace the first item in queue to NOP, so next check will fail
                publication._queue[0] = types.services.Operation.NOP
            state = publication.check_state()

        self.assertEqual(publication.check_state(), types.states.TaskState.ERROR)
        self.assertEqual(publication.error_reason(), 'Max retries reached')
        self.assertEqual(counter, 11)  # 4 retries + 5 retries after reset + 1 of the reset itself + 1 of initial NOP

    def test_publication_max_retries_checker(self) -> None:
        service = fixtures.create_dynamic_service()
        publication = fixtures.create_dynamic_publication(service)
        publication._queue = [
            types.services.Operation.CUSTOM_3,
            types.services.Operation.CUSTOM_3,
            types.services.Operation.FINISH,
        ]

        fixtures.DynamicTestingPublication.max_retries = 5

        state = types.states.TaskState.RUNNING
        counter = 0
        for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
            if counter == 4:
                # Replace the first item in queue to NOP, so next check will fail
                publication._queue[0] = types.services.Operation.NOP
            state = publication.check_state()

        self.assertEqual(publication.check_state(), types.states.TaskState.ERROR)
        self.assertEqual(publication.error_reason(), 'Max retries reached')
        self.assertEqual(counter, 10)  # 4 retries + 5 retries after reset + 1 of the reset itself
    

EXPECTED_DEPLOY_ITERATIONS_INFO: typing.Final[list[DynamicPublicationIterationInfo]] = [
    # Initial state for queue
    DynamicPublicationIterationInfo(  # 1, INITIALIZE
        queue=fixtures.PUB_TESTEABLE_OPERATIONS,
        user_service_calls=[
            call.initialize(),
        ],
    ),
    DynamicPublicationIterationInfo(  # 2, CREATE
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[1:],
        user_service_calls=[call.initialize_checker(), call.create()],
    ),
    DynamicPublicationIterationInfo(  # 3, CREATE_COMPLETED
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[2:],
        user_service_calls=[call.create_checker(), call.create_completed()],
    ),
    DynamicPublicationIterationInfo(  # 4, START
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[3:],
        user_service_calls=[call.create_completed_checker()],
        service_calls=[
            call.start(MustBeOfType(fixtures.DynamicTestingPublicationQueue), MustBeOfType(str))
        ],
    ),
    DynamicPublicationIterationInfo(  # 5, START_COMPLETED
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[4:],
        user_service_calls=[call.start_completed()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingPublicationQueue), MustBeOfType(str))
        ],
    ),
    DynamicPublicationIterationInfo(  # 6, STOP
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[5:],
        user_service_calls=[call.start_completed_checker()],
        service_calls=[
            call.stop(MustBeOfType(fixtures.DynamicTestingPublicationQueue), MustBeOfType(str))
        ],
    ),
    DynamicPublicationIterationInfo(  # 7, STOP_COMPLETED
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[6:],
        user_service_calls=[call.stop_completed()],
        service_calls=[
            call.is_running(MustBeOfType(fixtures.DynamicTestingPublicationQueue), MustBeOfType(str))
        ],
    ),
    DynamicPublicationIterationInfo(  # 8, SHUTDOWN
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[7:],
        user_service_calls=[call.stop_completed_checker()],
        service_calls=[
            call.shutdown(MustBeOfType(fixtures.DynamicTestingPublicationQueue), MustBeOfType(str)),
        ],
    ),
    DynamicPublicationIterationInfo(  # 9, SHUTDOWN_COMPLETED
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[8:],
        user_service_calls=[call.shutdown_completed()],
    ),
    DynamicPublicationIterationInfo(  # 10, REMOVE
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[9:],
        user_service_calls=[call.shutdown_completed_checker()],
        service_calls=[
            call.remove(MustBeOfType(fixtures.DynamicTestingPublicationQueue), MustBeOfType(str))
        ],
    ),
    DynamicPublicationIterationInfo(  # 11, REMOVE_COMPLETED
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[10:],
        user_service_calls=[call.remove_checker(), call.remove_completed()],
    ),
    DynamicPublicationIterationInfo(  # 12, NOP
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[11:],
        user_service_calls=[call.remove_completed_checker(), call.nop()],
    ),
    DynamicPublicationIterationInfo(  # 13, DESTROY_VALIDATOR
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[12:],
        user_service_calls=[call.nop_checker(), call.destroy_validator()],
    ),
    DynamicPublicationIterationInfo(  # 14, CUSTOM_1
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[13:],
        user_service_calls=[call.destroy_validator_checker(), call.custom(types.services.Operation.CUSTOM_1)],
    ),
    DynamicPublicationIterationInfo(  # 15, CUSTOM_2
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[14:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_1),
            call.custom(types.services.Operation.CUSTOM_2),
        ],
    ),
    DynamicPublicationIterationInfo(  # 16, CUSTOM_3
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[15:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_2),
            call.custom(types.services.Operation.CUSTOM_3),
        ],
    ),
    DynamicPublicationIterationInfo(  # 17, CUSTOM_4
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[16:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_3),
            call.custom(types.services.Operation.CUSTOM_4),
        ],
    ),
    DynamicPublicationIterationInfo(  # 18, CUSTOM_5
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[17:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_4),
            call.custom(types.services.Operation.CUSTOM_5),
        ],
    ),
    DynamicPublicationIterationInfo(  # 19, CUSTOM_6
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[18:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_5),
            call.custom(types.services.Operation.CUSTOM_6),
        ],
    ),
    DynamicPublicationIterationInfo(  # 20, CUSTOM_7
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[19:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_6),
            call.custom(types.services.Operation.CUSTOM_7),
        ],
    ),
    DynamicPublicationIterationInfo(  # 21, CUSTOM_8
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[20:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_7),
            call.custom(types.services.Operation.CUSTOM_8),
        ],
    ),
    DynamicPublicationIterationInfo(  # 22, CUSTOM_9
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[21:],
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_8),
            call.custom(types.services.Operation.CUSTOM_9),
        ],
    ),
    DynamicPublicationIterationInfo(
        queue=fixtures.PUB_TESTEABLE_OPERATIONS[22:],
        state=types.states.TaskState.FINISHED,
        user_service_calls=[
            call.custom_checker(types.services.Operation.CUSTOM_9),
        ],
    ),  # 28, FINISH
]
