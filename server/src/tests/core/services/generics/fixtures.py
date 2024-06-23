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
import uuid

from uds.core import services, types, ui, environment
from uds.core.services.generics.fixed import service as fixed_service
from uds.core.services.generics.fixed import userservice as fixed_userservice
from uds.core.services.generics.dynamic import service as dynamic_service
from uds.core.services.generics.dynamic import userservice as dynamic_userservice
from uds.core.services.generics.dynamic import publication as dynamic_publication
from uds.core.types.states import TaskState


if typing.TYPE_CHECKING:
    from uds import models


# Testing Fixed Service and related
class FixedTestingUserService(fixed_userservice.FixedUserService):
    mock: 'mock.Mock' = mock.MagicMock()

    def op_start(self) -> None:
        self.mock.op_start()

    def op_stop(self) -> None:
        self.mock.op_stop()

    def op_start_checker(self) -> types.states.TaskState:
        self.mock.op_start_checker()
        return types.states.TaskState.FINISHED

    def op_stop_checker(self) -> types.states.TaskState:
        self.mock.op_stop_checker()
        return types.states.TaskState.FINISHED

    # Exception raiser for tests
    def op_custom(self, operation: types.services.Operation) -> None:
        if operation == types.services.Operation.CUSTOM_1:
            raise Exception('CUSTOM_1')

        if operation == types.services.Operation.CUSTOM_3:
            self.retry_later()  # In this case, will not return it, but should work fine

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        if operation == types.services.Operation.CUSTOM_1:
            raise Exception('CUSTOM_1')
        # custom 2 will be for testing retry_later
        if operation == types.services.Operation.CUSTOM_2:
            return self.retry_later()

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
    randomize = fixed_service.FixedService.randomize
    maintain_on_error = fixed_service.FixedService.maintain_on_error

    user_service_type = FixedTestingUserService
    first_process_called = False
    available_machines_number = 1

    mock: 'mock.Mock' = mock.MagicMock()

    def snapshot_creation(self, userservice_instance: fixed_userservice.FixedUserService) -> None:
        self.mock.snapshot_creation(userservice_instance)
        if not self.first_process_called:
            # We want to call start, then snapshot, again
            # As we have snapshot on top of queue, we need to insert NOP -> STOP
            # This way, NOP will be consumed right now, then start will be called and then
            # this will be called again
            userservice_instance._queue.insert(0, types.services.Operation.STOP)
            userservice_instance._queue.insert(0, types.services.Operation.NOP)
            self.first_process_called = True

    def snapshot_recovery(self, userservice_instance: fixed_userservice.FixedUserService) -> None:
        self.mock.snapshot_recovery(userservice_instance)

    def get_name(self, vmid: str) -> str:
        self.mock.get_machine_name(vmid)
        return f'Machine {vmid}'

    def get_and_assign(self) -> str:
        self.mock.get_and_assign_machine()
        if self.available_machines_number <= 0:
            raise Exception('No machine available')
        self.available_machines_number -= 1
        self.assigned_machine = 'assigned'
        return self.assigned_machine

    def remove_and_free(self, vmid: str) -> types.states.TaskState:
        self.mock.remove_and_free_machine(vmid)
        self.assigned_machine = ''
        return types.states.TaskState.FINISHED

    def is_ready(self, vmid: str) -> bool:
        self.mock.is_ready(vmid)
        return True

    def get_mac(self, vmid: str) -> str:
        self.mock.get_first_network_mac(vmid)
        return '00:00:00:00:00:00'

    def get_ip(self, vmid: str) -> str:
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


def create_fixed_provider() -> FixedTestingProvider:
    uuid_ = str(uuid.uuid4())
    return FixedTestingProvider(environment=environment.Environment.private_environment(uuid), uuid=uuid_)


def create_fixed_service(provider: 'FixedTestingProvider|None') -> FixedTestingService:
    uuid_ = str(uuid.uuid4())
    return FixedTestingService(
        provider=provider or create_fixed_provider(),
        environment=environment.Environment.private_environment(uuid),
        uuid=uuid_,
    )


def create_fixed_user_service(service: 'FixedTestingService|None') -> FixedTestingUserService:
    uuid_ = str(uuid.uuid4())
    return FixedTestingUserService(
        service=service or create_fixed_service(None),
        environment=environment.Environment.private_environment(uuid),
        uuid=uuid_,
    )


# Testing Dynamic Service and related

ALL_TESTEABLE_OPERATIONS = [
    types.services.Operation.INITIALIZE,
    types.services.Operation.CREATE,
    types.services.Operation.CREATE_COMPLETED,
    types.services.Operation.START,
    types.services.Operation.START_COMPLETED,
    types.services.Operation.STOP,
    types.services.Operation.STOP_COMPLETED,
    types.services.Operation.SHUTDOWN,
    types.services.Operation.SHUTDOWN_COMPLETED,
    types.services.Operation.SUSPEND,
    types.services.Operation.SUSPEND_COMPLETED,
    types.services.Operation.RESET,
    types.services.Operation.RESET_COMPLETED,
    types.services.Operation.DELETE,
    types.services.Operation.DELETE_COMPLETED,
    types.services.Operation.WAIT,
    types.services.Operation.NOP,
    types.services.Operation.DESTROY_VALIDATOR,
    types.services.Operation.CUSTOM_1,
    types.services.Operation.CUSTOM_2,
    types.services.Operation.CUSTOM_3,
    types.services.Operation.CUSTOM_4,
    types.services.Operation.CUSTOM_5,
    types.services.Operation.CUSTOM_6,
    types.services.Operation.CUSTOM_7,
    types.services.Operation.CUSTOM_8,
    types.services.Operation.CUSTOM_9,
    types.services.Operation.FINISH,
]

PUB_TESTEABLE_OPERATIONS = [
    types.services.Operation.INITIALIZE,  # 1
    types.services.Operation.CREATE,  # 2
    types.services.Operation.CREATE_COMPLETED,  # 3
    types.services.Operation.START,  # 4
    types.services.Operation.START_COMPLETED,  # 5
    types.services.Operation.STOP,  # 6
    types.services.Operation.STOP_COMPLETED,  # 7
    types.services.Operation.SHUTDOWN,  # 8
    types.services.Operation.SHUTDOWN_COMPLETED,  # 9
    types.services.Operation.DELETE,  # 10
    types.services.Operation.DELETE_COMPLETED,  # 11
    types.services.Operation.NOP,  # 12
    types.services.Operation.DESTROY_VALIDATOR,  # 13
    types.services.Operation.CUSTOM_1,  # 14
    types.services.Operation.CUSTOM_2,
    types.services.Operation.CUSTOM_3,
    types.services.Operation.CUSTOM_4,
    types.services.Operation.CUSTOM_5,
    types.services.Operation.CUSTOM_6,
    types.services.Operation.CUSTOM_7,
    types.services.Operation.CUSTOM_8,
    types.services.Operation.CUSTOM_9,
    types.services.Operation.FINISH,
]


class DynamicTestingUserServiceQueue(dynamic_userservice.DynamicUserService):
    mock: 'mock.Mock' = mock.MagicMock()

    # Override create queue with ALL operations
    _create_queue = ALL_TESTEABLE_OPERATIONS.copy()
    _create_queue_l1_cache = ALL_TESTEABLE_OPERATIONS.copy()
    _create_queue_l2_cache = ALL_TESTEABLE_OPERATIONS.copy()

    def db_obj(self) -> typing.Any:
        self.mock.db_obj()
        return None

    def op_initialize(self) -> None:
        self.mock.initialize()

    def op_create(self) -> None:
        """
        This method is called when the service is created
        """
        self._vmid = 'vmid'  # Set a vmid for testing purposes
        self.mock.create()

    def op_create_completed(self) -> None:
        """
        This method is called when the service creation is completed
        """
        self.mock.create_completed()

    # Default opstart will call service start_machine, so will check there
    # def op_start(self) -> None:

    def op_start_completed(self) -> None:
        """
        This method is called when the service start is completed
        """
        self.mock.start_completed()

    # Default opstop will call service stop_machine, so will check there
    # def op_stop(self) -> None:

    def op_stop_completed(self) -> None:
        """
        This method is called when the service stop is completed
        """
        self.mock.stop_completed()

    # Default opshutdown will call service shutdown_machine, so will check there
    # def op_shutdown(self) -> None:

    def op_shutdown_completed(self) -> None:
        """
        This method is called when the service shutdown is completed
        """
        self.mock.shutdown_completed()

    # Default calls shutdown, but we want to check here
    def op_suspend(self) -> None:
        self.mock.suspend()

    def op_suspend_completed(self) -> None:
        """
        This method is called when the service suspension is completed
        """
        self.mock.suspend_completed()

    # Default opreset will call service reset_machine, so will check there
    # def op_reset(self) -> None:

    def op_reset_completed(self) -> None:
        """
        This method is called when the service reset is completed
        """
        self.mock.reset_completed()

    # Default opremove will call service remove_machine, so will check there
    # def op_delete(self) -> None:

    def op_delete_completed(self) -> None:
        self.mock.remove_completed()

    def op_wait(self) -> None:
        self.mock.wait()

    def op_nop(self) -> None:
        self.mock.nop()

    def op_destroy_validator(self) -> None:
        self.mock.destroy_validator()

    def op_custom(self, operation: types.services.Operation) -> None:
        """
        This method is called when the service is doing a custom operation
        """
        self.mock.custom(operation)

    # ERROR, FINISH and UNKNOWN are not here, as they are final states not needing to be executed

    def op_initialize_checker(self) -> types.states.TaskState:
        self.mock.initialize_checker()
        return types.states.TaskState.FINISHED

    def op_create_checker(self) -> types.states.TaskState:
        self.mock.create_checker()
        return types.states.TaskState.FINISHED

    def op_create_completed_checker(self) -> types.states.TaskState:
        self.mock.create_completed_checker()
        return types.states.TaskState.FINISHED

    def op_start_completed_checker(self) -> types.states.TaskState:
        self.mock.start_completed_checker()
        return types.states.TaskState.FINISHED

    def op_stop_completed_checker(self) -> types.states.TaskState:
        self.mock.stop_completed_checker()
        return types.states.TaskState.FINISHED

    # Use default op_shutdown_checker, as it will check for several parameters
    # def op_shutdown_checker(self) -> types.states.TaskState:

    def op_shutdown_completed_checker(self) -> types.states.TaskState:
        self.mock.shutdown_completed_checker()
        return types.states.TaskState.FINISHED

    def op_suspend_checker(self) -> types.states.TaskState:
        self.mock.suspend_checker()
        return self.op_shutdown_checker()

    def op_suspend_completed_checker(self) -> types.states.TaskState:
        self.mock.suspend_completed_checker()
        return types.states.TaskState.FINISHED

    def op_reset_checker(self) -> types.states.TaskState:
        self.mock.reset_checker()
        return types.states.TaskState.FINISHED

    def op_reset_completed_checker(self) -> types.states.TaskState:
        self.mock.reset_completed_checker()
        return types.states.TaskState.FINISHED

    def op_delete_checker(self) -> types.states.TaskState:
        self.mock.remove_checker()
        return types.states.TaskState.FINISHED

    def op_delete_completed_checker(self) -> types.states.TaskState:
        self.mock.remove_completed_checker()
        return types.states.TaskState.FINISHED

    def op_wait_checker(self) -> types.states.TaskState:
        self.mock.wait_checker()
        return types.states.TaskState.FINISHED  # Ensure we finish right now for wait

    def op_nop_checker(self) -> types.states.TaskState:  # type: ignore  # overriding a final method
        self.mock.nop_checker()
        return types.states.TaskState.FINISHED

    def op_destroy_validator_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the userservice has an vmid to stop destroying it if needed
        """
        self.mock.destroy_validator_checker()
        return types.states.TaskState.FINISHED  # If we are here, we have a vmid

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        self.mock.custom_checker(operation)
        return types.states.TaskState.FINISHED

    # ERROR, FINISH and UNKNOWN are not here, as they are final states not needing to be checked


class DynamicTestingUserService(dynamic_userservice.DynamicUserService):
    mock: 'mock.Mock' = mock.MagicMock()

    def db_obj(self) -> typing.Any:
        self.mock.db_obj()
        return None

    def op_create(self) -> None:
        self._vmid = 'vmid'  # Set a vmid for testing purposes
        typing.cast('DynamicTestingService', self.service()).machine_running_flag = False

    # Exception raiser for tests
    def op_custom(self, operation: types.services.Operation) -> None:
        if operation == types.services.Operation.CUSTOM_1:
            raise Exception('CUSTOM_1')

        if operation == types.services.Operation.CUSTOM_3:
            self.retry_later()  # In this case, will not return it, but should work fine

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        if operation == types.services.Operation.CUSTOM_1:
            raise Exception('CUSTOM_1')
        # custom 2 will be for testing retry_later
        if operation == types.services.Operation.CUSTOM_2:
            return self.retry_later()

        return types.states.TaskState.FINISHED


class DynamicTestingService(dynamic_service.DynamicService):
    type_name = 'Dynamic Service Testing'
    type_type = 'DynamicServiceTesting'
    type_description = 'Dynamic Service Testing description'

    user_service_type = DynamicTestingUserServiceQueue

    mock: 'mock.Mock' = mock.MagicMock()

    # Clone flag
    maintain_on_error = dynamic_service.DynamicService.maintain_on_error
    try_soft_shutdown = dynamic_service.DynamicService.try_soft_shutdown

    machine_running_flag: bool = True

    def get_ip(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> str:
        self.mock.get_ip(caller_instance, vmid)
        return '1.2.3.4'

    def get_mac(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> str:
        self.mock.get_mac(caller_instance, vmid)
        return '02:04:06:08:0A:0C'

    def is_running(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> bool:
        self.mock.is_running(caller_instance, vmid)
        return self.machine_running_flag

    def start(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.start(caller_instance, vmid)
        self.machine_running_flag = True

    def stop(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.stop(caller_instance, vmid)
        self.machine_running_flag = False

    def shutdown(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.shutdown(caller_instance, vmid)
        self.machine_running_flag = False

    def delete(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.remove(caller_instance, vmid)
        self.machine_running_flag = False

    def reset(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.reset(caller_instance, vmid)
        super().reset(caller_instance, vmid)  # Call parent reset, that in order invokes stop

    def suspend(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.suspend(caller_instance, vmid)
        self.machine_running_flag = False


class DynamicTestingPublication(dynamic_publication.DynamicPublication):
    mock: 'mock.Mock' = mock.MagicMock()

    def op_create(self) -> None:
        self.mock.op_create()

    # Exception raiser for tests
    def op_custom(self, operation: types.services.Operation) -> None:
        self.mock.custom(operation)
        if operation == types.services.Operation.CUSTOM_3:
            self.retry_later()  # In this case, will not return it, but should work fine

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        self.mock.custom_checker(operation)
        # custom 2 will be for testing retry_later
        if operation == types.services.Operation.CUSTOM_2:
            return self.retry_later()

        return types.states.TaskState.FINISHED


class DynamicTestingPublicationQueue(dynamic_publication.DynamicPublication):
    mock: 'mock.Mock' = mock.MagicMock()

    _publish_queue = PUB_TESTEABLE_OPERATIONS.copy()
    _destroy_queue = PUB_TESTEABLE_OPERATIONS.copy()

    def op_initialize(self) -> None:
        self.mock.initialize()

    def op_create(self) -> None:
        self._vmid = 'vmid'  # Set a vmid for testing purposes
        self.mock.create()

    def op_create_completed(self) -> None:
        self.mock.create_completed()

    def op_start_completed(self) -> None:
        self.mock.start_completed()

    def op_stop_completed(self) -> None:
        self.mock.stop_completed()

    def op_shutdown_completed(self) -> None:
        self.mock.shutdown_completed()

    def op_delete_completed(self) -> None:
        self.mock.remove_completed()

    def op_nop(self) -> None:
        self.mock.nop()

    def op_destroy_validator(self) -> None:
        self.mock.destroy_validator()

    def op_custom(self, operation: types.services.Operation) -> None:
        self.mock.custom(operation)

    def op_initialize_checker(self) -> types.states.TaskState:
        self.mock.initialize_checker()
        return TaskState.FINISHED

    def op_create_checker(self) -> types.states.TaskState:
        self.mock.create_checker()
        return TaskState.FINISHED

    def op_create_completed_checker(self) -> types.states.TaskState:
        self.mock.create_completed_checker()
        return TaskState.FINISHED

    def op_start_completed_checker(self) -> types.states.TaskState:
        self.mock.start_completed_checker()
        return TaskState.FINISHED

    def op_stop_completed_checker(self) -> types.states.TaskState:
        self.mock.stop_completed_checker()
        return TaskState.FINISHED

    def op_shutdown_completed_checker(self) -> types.states.TaskState:
        self.mock.shutdown_completed_checker()
        return TaskState.FINISHED

    def op_delete_checker(self) -> types.states.TaskState:
        self.mock.remove_checker()
        return TaskState.FINISHED

    def op_delete_completed_checker(self) -> types.states.TaskState:
        self.mock.remove_completed_checker()
        return TaskState.FINISHED

    def op_nop_checker(self) -> types.states.TaskState:
        self.mock.nop_checker()
        return TaskState.FINISHED

    def op_destroy_validator_checker(self) -> types.states.TaskState:
        self.mock.destroy_validator_checker()
        return TaskState.FINISHED

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        self.mock.custom_checker(operation)
        return TaskState.FINISHED


class DynamicTestingServiceForDeferredDeletion(dynamic_service.DynamicService):
    type_name = 'Dynamic Deferred Deletion Testing'
    type_type = 'DynamicDeferredServiceTesting'
    type_description = 'Dynamic Service Testing description'

    mock: 'mock.Mock' = mock.MagicMock()  # Remember, shared between instances

    def execute_delete(self, vmid: str) -> None:
        self.mock.execute_delete(vmid)

    def is_deleted(self, vmid: str) -> bool:
        self.mock.is_deleted(vmid)
        return True

    # Not used, but needed to be implemented due to bein abstract
    def get_ip(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> str:
        return ''

    def get_mac(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> str:
        return ''

    def is_running(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> bool:
        self.mock.is_running(vmid)
        raise Exception('Intended exception')

    def start(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.start(vmid)

    def stop(
        self,
        caller_instance: dynamic_userservice.DynamicUserService | dynamic_publication.DynamicPublication,
        vmid: str,
    ) -> None:
        self.mock.stop(vmid)



class DynamicTestingProvider(services.provider.ServiceProvider):
    type_name = 'Dynamic Provider'
    type_type = 'DynamicProvider'
    type_description = 'Dynamic Provider description'

    offers = [DynamicTestingService, DynamicTestingServiceForDeferredDeletion]


def create_dynamic_provider() -> DynamicTestingProvider:
    uuid_ = str(uuid.uuid4())
    return DynamicTestingProvider(environment=environment.Environment.private_environment(uuid), uuid=uuid_)


def create_dynamic_service(
    provider: 'DynamicTestingProvider|None' = None,
    maintain_on_error: bool = False,
    try_soft_shutdown: bool = False,
) -> DynamicTestingService:
    uuid_ = str(uuid.uuid4())
    service = DynamicTestingService(
        provider=provider or create_dynamic_provider(),
        environment=environment.Environment.private_environment(uuid),
        uuid=uuid_,
    )
    service.mock.reset_mock()  # Mock is shared between instances, so we need to reset it
    service.machine_running_flag = False
    service.maintain_on_error.value = maintain_on_error
    service.try_soft_shutdown.value = try_soft_shutdown
    return service


def create_dynamic_service_for_deferred_deletion(
    provider: 'DynamicTestingProvider|None' = None,
    maintain_on_error: bool = False,
    try_soft_shutdown: bool = False,
) -> DynamicTestingServiceForDeferredDeletion:
    uuid_ = str(uuid.uuid4())
    service = DynamicTestingServiceForDeferredDeletion(
        provider=provider or create_dynamic_provider(),
        environment=environment.Environment.private_environment(uuid),
        uuid=uuid_,
    )
    service.mock.reset_mock()  # Mock is shared between instances, so we need to reset it
    service.maintain_on_error.value = maintain_on_error
    service.try_soft_shutdown.value = try_soft_shutdown
    return service


def create_dynamic_publication_queue(
    service: 'DynamicTestingService|None' = None,
) -> DynamicTestingPublicationQueue:
    uuid_ = str(uuid.uuid4())

    publication = DynamicTestingPublicationQueue(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_dynamic_service(None),
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )
    publication.mock.reset_mock()  # Mock is shared between instances, so we need to reset it
    return publication


def create_dynamic_publication(service: 'DynamicTestingService|None' = None) -> DynamicTestingPublication:
    uuid_ = str(uuid.uuid4())

    publication = DynamicTestingPublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_dynamic_service(None),
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )
    publication.mock.reset_mock()  # Mock is shared between instances, so we need to reset it
    return publication


def create_dynamic_userservice_queue(
    service: 'DynamicTestingService|None' = None, publication: 'DynamicTestingPublication|None' = None
) -> DynamicTestingUserServiceQueue:
    uuid_ = str(uuid.uuid4())
    userservice = DynamicTestingUserServiceQueue(
        service=service or create_dynamic_service(None),
        publication=create_dynamic_publication(None),
        environment=environment.Environment.private_environment(uuid),
        uuid=uuid_,
    )
    userservice.mock.reset_mock()  # Mock is shared between instances, so we need to reset it
    return userservice


def create_dynamic_userservice(
    service: 'DynamicTestingService|None' = None, publication: 'DynamicTestingPublication|None' = None
) -> DynamicTestingUserService:
    uuid_ = str(uuid.uuid4())
    userservice = DynamicTestingUserService(
        service=service or create_dynamic_service(None),
        publication=create_dynamic_publication(None),
        environment=environment.Environment.private_environment(uuid),
        uuid=uuid_,
    )
    userservice.mock.reset_mock()  # Mock is shared between instances, so we need to reset it
    return userservice
