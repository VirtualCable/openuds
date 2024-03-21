# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import abc
import collections.abc
import logging
import time
import typing

from django.utils.translation import gettext as _
from uds.core import services, types
from uds.core.types.services import Operation
from uds.core.util import autoserializable

if typing.TYPE_CHECKING:
    from .dynamic_service import DynamicService

logger = logging.getLogger(__name__)


class DynamicPublication(services.Publication, autoserializable.AutoSerializable, abc.ABC):
    # Very simmilar to DynamicUserService, but with some differences
    suggested_delay = 20  # For publications, we can check every 20 seconds

    # Some customization fields
    # How many times we will check for a state before giving up
    max_state_checks: typing.ClassVar[int] = 20
    # If must wait untill finish queue for destroying the machine
    wait_until_finish_to_destroy: typing.ClassVar[bool] = False

    _name = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()
    _reason = autoserializable.StringField(default='')
    _is_flagged_for_destroy = autoserializable.BoolField(default=False)

    _publish_queue: typing.ClassVar[list[Operation]] = [
        Operation.INITIALIZE,
        Operation.CREATE,
        Operation.CREATE_COMPLETED,
        Operation.FINISH,
    ]
    _destroy_queue: typing.ClassVar[list[Operation]] = [
        Operation.REMOVE,
        Operation.REMOVE_COMPLETED,
        Operation.FINISH,
    ]

    # Utility overrides for type checking...
    def _reset_checks_counter(self) -> None:
        with self.storage.as_dict() as data:
            data['exec_count'] = 0

    def _inc_checks_counter(self, info: typing.Optional[str] = None) -> typing.Optional[types.states.TaskState]:
        with self.storage.as_dict() as data:
            count = data.get('exec_count', 0) + 1
            data['exec_count'] = count
        if count > self.max_state_checks:
            return self._error(f'Max checks reached on {info or "unknown"}')
        return None

    def _current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    def _error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        reason = str(reason)
        logger.error(reason)

        if self._vmid:
            try:
                # TODO: Remove VM using service or put it on a "to be removed" queue for a parallel job
                self._vmid = ''
            except Exception as e:
                logger.exception('Exception removing machine: %s', e)

        self._queue = [Operation.ERROR]
        self._reason = reason
        return types.states.TaskState.ERROR

    def service(self) -> 'DynamicService':
        return typing.cast('DynamicService', super().service())

    def check_space(self) -> bool:
        """
        If the service needs to check space before publication, it should override this method
        """
        return True

    def publish(self) -> types.states.TaskState:
        """ """
        self._queue = self._publish_queue.copy()
        self._debug('publish')
        return self._execute_queue()

    def _execute_queue(self) -> types.states.TaskState:
        self._debug('execute_queue')
        op = self._current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            return types.states.TaskState.FINISHED

        try:
            self._reset_checks_counter()  # Reset checks counter

            # For custom operations, we will call the only one method
            if op.is_custom():
                self.op_custom(op)
            else:
                # Invoke using instance, we have overrided methods
                # and we want to use the overrided ones
                operation_runner = _EXECUTORS[op]
                getattr(self, operation_runner.__name__)()

            return types.states.TaskState.RUNNING
        except Exception as e:
            logger.exception('Unexpected FixedUserService exception: %s', e)
            return self._error(str(e))

    def check_state(self) -> types.states.TaskState:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._current_op()

        if op == Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == Operation.FINISH:
            if self.wait_until_finish_to_destroy and self._is_flagged_for_destroy:
                self._is_flagged_for_destroy = False
                self._queue = [Operation.FINISH]  # For destroy to start "clean"
                return self.destroy()
            return types.states.TaskState.FINISHED

        if op != Operation.WAIT:
            # All operations except WAIT will check against checks counter
            state = self._inc_checks_counter(self._op2str(op))
            if state is not None:
                return state  # Error, Finished or None

        try:
            if op.is_custom():
                state = self.op_custom_checker(op)
            else:
                # Invoke using instance, we have overrided methods
                # and we want to use the overrided ones
                operation_checker = _CHECKERS[op]
                state = getattr(self, operation_checker.__name__)()
            if state == types.states.TaskState.FINISHED:
                # Remove runing op
                self._queue.pop(0)
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)

    @typing.final
    def destroy(self) -> types.states.TaskState:
        """
        Destroys the publication (or cancels it if it's in the middle of a creation process)
        """
        self._is_flagged_for_destroy = False  # Reset flag
        op = self._current_op()
        
        # If already removing, do nothing
        if op == Operation.REMOVE:
            return types.states.TaskState.RUNNING

        if op == Operation.ERROR:
            return self._error('Machine is already in error state!')

        # If a "paused" state, reset queue to destroy
        if op == Operation.FINISH:
            self._queue = self._destroy_queue.copy()
            return self._execute_queue()

        # If must wait until finish, flag for destroy and wait
        if self.wait_until_finish_to_destroy:
            self._is_flagged_for_destroy = True
        else:
            # If other operation, wait for finish before destroying
            self._queue = [op] + self._destroy_queue  # Copy not needed, will be copied anyway due to list concatenation
            # Do not execute anything.here, just continue normally
        return types.states.TaskState.RUNNING
    
    def cancel(self) -> types.states.TaskState:
        """
        Cancels the publication (or cancels it if it's in the middle of a creation process)
        This can be overriden, just in case we need some special handling
        """
        return self.destroy()

    @typing.final
    def error_reason(self) -> str:
        return self._reason

    # Execution methods
    # Every Operation has an execution method and a check method
    def op_initialize(self) -> None:
        """
        This method is called when the service is initialized
        Default initialization method sets the name and flags the service as not destroyed
        """
        if self.check_space() is False:
            raise Exception('Not enough space to publish')

        # First we should create a full clone, so base machine do not get fullfilled with "garbage" delta disks...
        # Add a number based on current time to avoid collisions
        self._name = self.service().sanitize_machine_name(
            f'UDS-Pub {self.servicepool_name()}-{int(time.time())%256:2X} {self.revision()}'
        )
        self._is_flagged_for_destroy = False

    @abc.abstractmethod
    def op_create(self) -> None:
        """
        This method is called when the service is created
        At least, we must provide this method
        """
        ...

    def op_create_completed(self) -> None:
        """
        This method is called when the service creation is completed
        """
        pass

    def op_start(self) -> None:
        """
        This method is called when the service is started
        """
        self.service().start_machine(self, self._vmid)

    def op_start_completed(self) -> None:
        """
        This method is called when the service start is completed
        """
        pass

    def op_stop(self) -> None:
        """
        This method is called for stopping the service
        """
        self.service().stop_machine(self, self._vmid)

    def op_stop_completed(self) -> None:
        """
        This method is called when the service stop is completed
        """
        pass

    def op_shutdown(self) -> None:
        """
        This method is called for shutdown the service
        """
        self.service().shutdown_machine(self, self._vmid)

    def op_shutdown_completed(self) -> None:
        """
        This method is called when the service shutdown is completed
        """
        pass

    def op_suspend(self) -> None:
        """
        This method is called for suspend the service
        """
        # Note that by default suspend is "shutdown" and not "stop" because we
        self.service().suspend_machine(self, self._vmid)

    def op_suspend_completed(self) -> None:
        """
        This method is called when the service suspension is completed
        """
        pass

    def op_reset(self) -> None:
        """
        This method is called when the service is reset
        """
        pass

    def op_reset_completed(self) -> None:
        """
        This method is called when the service reset is completed
        """
        self.service().reset_machine(self, self._vmid)

    def op_remove(self) -> None:
        """
        This method is called when the service is removed
        By default, we need a remove machine on the service, use it
        """
        self.service().remove_machine(self, self._vmid)

    def op_remove_completed(self) -> None:
        """
        This method is called when the service removal is completed
        """
        pass

    def op_wait(self) -> None:
        """
        This method is called when the service is waiting
        Basically, will stop the execution of the queue until something external changes it (i.e. poping from the queue)
        Executor does nothing
        """
        pass

    def op_nop(self) -> None:
        """
        This method is called when the service is doing nothing
        This does nothing, as it's a NOP operation
        """
        pass

    def op_custom(self, operation: Operation) -> None:
        """
        This method is called when the service is doing a custom operation
        """
        pass

    # ERROR, FINISH and UNKNOWN are not here, as they are final states not needing to be executed

    def op_initialize_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is initialized
        """
        return types.states.TaskState.FINISHED

    def op_create_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is created
        """
        return types.states.TaskState.FINISHED

    def op_create_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service creation is completed
        """
        return types.states.TaskState.FINISHED

    def op_start_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is started
        """
        return types.states.TaskState.FINISHED

    def op_start_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service start is completed
        """
        return types.states.TaskState.FINISHED

    def op_stop_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is stopped
        """
        return types.states.TaskState.FINISHED

    def op_stop_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service stop is completed
        """
        return types.states.TaskState.FINISHED

    def op_shutdown_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is shutdown
        """
        return types.states.TaskState.FINISHED

    def op_shutdown_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service shutdown is completed
        """
        return types.states.TaskState.FINISHED

    def op_suspend_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is suspended
        """
        return types.states.TaskState.FINISHED

    def op_suspend_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service suspension is completed
        """
        return types.states.TaskState.FINISHED

    def op_reset_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is reset
        """
        return types.states.TaskState.FINISHED

    def op_remove_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is removed
        """
        return types.states.TaskState.FINISHED

    def op_remove_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service removal is completed
        """
        return types.states.TaskState.FINISHED

    def op_wait_checker(self) -> types.states.TaskState:
        """
        Wait will remain in the same state until something external changes it (i.e. poping from the queue)
        """
        return types.states.TaskState.RUNNING

    def op_nop_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is doing nothing
        """
        return types.states.TaskState.FINISHED

    def op_custom_checker(self, operation: Operation) -> types.states.TaskState:
        """
        This method is called to check if the service is doing a custom operation
        """
        return types.states.TaskState.FINISHED

    # ERROR, FINISH and UNKNOWN are not here, as they are final states not needing to be checked

    @staticmethod
    def _op2str(op: Operation) -> str:
        return op.name

    def _debug(self, txt: str) -> None:
        logger.debug(
            'Queue at %s for %s: %s, vmid:%s',
            txt,
            self._name,
            [DynamicPublication._op2str(op) for op in self._queue],
            self._vmid,
        )

    def get_template_id(self) -> str:
        return self._vmid


# This is a map of operations to methods
# Operation methods, due to the fact that can be overrided, must be invoked via instance
# We use getattr(FNC.__name__, ...) to use them, so we can use type checking and invoke them via instance
# Note that ERROR and FINISH are not here, as they final states not needing to be executed
_EXECUTORS: typing.Final[
    collections.abc.Mapping[Operation, collections.abc.Callable[[DynamicPublication], None]]
] = {
    Operation.INITIALIZE: DynamicPublication.op_initialize,
    Operation.CREATE: DynamicPublication.op_create,
    Operation.CREATE_COMPLETED: DynamicPublication.op_create_completed,
    Operation.START: DynamicPublication.op_start,
    Operation.START_COMPLETED: DynamicPublication.op_start_completed,
    Operation.STOP: DynamicPublication.op_stop,
    Operation.STOP_COMPLETED: DynamicPublication.op_stop_completed,
    Operation.SHUTDOWN: DynamicPublication.op_shutdown,
    Operation.SHUTDOWN_COMPLETED: DynamicPublication.op_shutdown_completed,
    Operation.SUSPEND: DynamicPublication.op_suspend,
    Operation.SUSPEND_COMPLETED: DynamicPublication.op_suspend_completed,
    Operation.REMOVE: DynamicPublication.op_remove,
    Operation.REMOVE_COMPLETED: DynamicPublication.op_remove_completed,
    Operation.WAIT: DynamicPublication.op_wait,
    Operation.NOP: DynamicPublication.op_nop,
}

# Same af before, but for check methods
_CHECKERS: typing.Final[
    collections.abc.Mapping[Operation, collections.abc.Callable[[DynamicPublication], types.states.TaskState]]
] = {
    Operation.INITIALIZE: DynamicPublication.op_initialize_checker,
    Operation.CREATE: DynamicPublication.op_create_checker,
    Operation.CREATE_COMPLETED: DynamicPublication.op_create_completed_checker,
    Operation.START: DynamicPublication.op_start_checker,
    Operation.START_COMPLETED: DynamicPublication.op_start_completed_checker,
    Operation.STOP: DynamicPublication.op_stop_checker,
    Operation.STOP_COMPLETED: DynamicPublication.op_stop_completed_checker,
    Operation.SHUTDOWN: DynamicPublication.op_shutdown_checker,
    Operation.SHUTDOWN_COMPLETED: DynamicPublication.op_shutdown_completed_checker,
    Operation.SUSPEND: DynamicPublication.op_suspend_checker,
    Operation.SUSPEND_COMPLETED: DynamicPublication.op_suspend_completed_checker,
    Operation.REMOVE: DynamicPublication.op_remove_checker,
    Operation.REMOVE_COMPLETED: DynamicPublication.op_remove_completed_checker,
    Operation.WAIT: DynamicPublication.op_wait_checker,
    Operation.NOP: DynamicPublication.op_nop_checker,
}
