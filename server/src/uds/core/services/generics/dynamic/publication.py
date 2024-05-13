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
import functools
import logging
import time
import typing

from django.utils.translation import gettext as _
from uds.core import services, types, consts
from uds.core.types.services import Operation
from uds.core.util import autoserializable

from .. import exceptions

if typing.TYPE_CHECKING:
    from .service import DynamicService

logger = logging.getLogger(__name__)


# Decorator that tests that _vmid is not empty
# Used by some default methods that require a vmid to work
def must_have_vmid(fnc: typing.Callable[[typing.Any], None]) -> typing.Callable[['DynamicPublication'], None]:
    @functools.wraps(fnc)
    def wrapper(self: 'DynamicPublication') -> None:
        if self._vmid == '':
            raise exceptions.FatalError(f'No machine id on {self._name} for {fnc}')
        return fnc(self)

    return wrapper


class DynamicPublication(services.Publication, autoserializable.AutoSerializable, abc.ABC):
    # Very simmilar to DynamicUserService, but with some differences
    suggested_delay = consts.services.PUB_SUGGESTED_CHECK_INTERVAL

    # Some customization fields
    # How many times we will check for a state before giving up
    # Publications can take a long time, so we will check it for a long time
    # as long as a couple of hours by default with our suggested delay
    max_state_checks: typing.ClassVar[int] = consts.services.PUB_MAX_STATE_CHECKS
    # How many "retries" operation on same state will be allowed before giving up
    max_retries: typing.ClassVar[int] = consts.services.PUB_MAX_RETRIES

    # If must wait until finish queue for destroying the machine
    wait_until_finish_to_destroy: typing.ClassVar[bool] = False

    _name = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()
    _reason = autoserializable.StringField(default='')
    _is_flagged_for_destroy = autoserializable.BoolField(default=False)

    # Extra info, not serializable, to keep information in case of exception and debug it
    _error_debug_info: typing.Optional[str] = None

    _publish_queue: typing.ClassVar[list[Operation]] = [
        Operation.INITIALIZE,
        Operation.CREATE,
        Operation.CREATE_COMPLETED,
        Operation.FINISH,
    ]
    _destroy_queue: typing.ClassVar[list[Operation]] = [
        Operation.DELETE,
        Operation.DELETE_COMPLETED,
        Operation.FINISH,
    ]

    # Utility overrides for type checking...
    @typing.final
    def _reset_checks_counter(self) -> None:
        with self.storage.as_dict() as data:
            data['exec_count'] = 0

    @typing.final
    def _inc_checks_counter(self, info: typing.Optional[str] = None) -> typing.Optional[types.states.TaskState]:
        with self.storage.as_dict() as data:
            count = data.get('exec_count', 0) + 1
            data['exec_count'] = count
        if count > self.max_state_checks:
            return self._error(f'Max checks reached on {info or "unknown"}')
        return None

    @typing.final
    def _reset_retries_counter(self) -> None:
        with self.storage.as_dict() as data:
            data['retries'] = 0

    @typing.final
    def _inc_retries_counter(self) -> typing.Optional[types.states.TaskState]:
        with self.storage.as_dict() as data:
            retries = data.get('retries', 0) + 1
            data['retries'] = retries

        if (
            retries > self.max_retries
        ):  # Use self to access class variables, so we can override them on subclasses
            return self._error(f'Max retries reached')

        return None

    @typing.final
    def _current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    @typing.final
    def _set_queue(self, queue: list[Operation]) -> None:
        """
        Sets the queue of tasks to be executed
        Ensures that we mark it as new format
        """
        self._queue = queue

    @typing.final
    def _error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        self._error_debug_info = self._debug(repr(reason))
        reason = str(reason)
        logger.error(reason)

        if self._vmid:
            try:
                self.service().delete(self, self._vmid)
                self._vmid = ''
            except Exception as e:
                logger.exception('Exception removing machine: %s', e)

        self._queue = [Operation.ERROR]
        self._reason = reason
        return types.states.TaskState.ERROR

    @typing.final
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
        except exceptions.RetryableError as e:
            # This is a retryable error, so we will retry later
            return self.retry_later()
        except Exception as e:
            logger.exception('Unexpected FixedUserService exception: %s', e)
            return self._error(str(e))

    @typing.final
    def retry_later(self) -> types.states.TaskState:
        """
        Retries the current operation
        For this, we insert a RETRY that will be:
            - If used from a "executor" method, will invoke the "retry_checker" method
            - If used from a "checker" method, will be consumed, and the operation will be retried
        In any case, if we overpass the max retries, we will set the machine to error state
        """
        if self._inc_retries_counter() is not None:
            return self._error('Max retries reached')
        self._queue.insert(0, Operation.RETRY)
        return types.states.TaskState.FINISHED

    def service(self) -> 'DynamicService':
        return typing.cast('DynamicService', super().service())

    def check_space(self) -> bool:
        """
        If the service needs to check space before publication, it should override this method
        """
        return True

    @typing.final
    def publish(self) -> types.states.TaskState:
        """ """
        self._queue = self._publish_queue.copy()
        self._debug('publish')
        return self._execute_queue()

    @typing.final
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
            counter_state = self._inc_checks_counter(self._op2str(op))
            if counter_state is not None:
                return counter_state  # Error, Finished or None

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
                top_op = self._queue.pop(0)  # May have inserted a RETRY, check it
                # And reset retries counter
                if top_op != Operation.RETRY:
                    self._reset_retries_counter()
                return self._execute_queue()

            return state
        except exceptions.RetryableError as e:
            # This is a retryable error, so we will retry later
            # We don not need to push a NOP here, as we will retry the same operation checking again
            # And it has not been removed from the queue
            return types.states.TaskState.RUNNING
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
        if op == Operation.DELETE:
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
            self._queue = [
                op
            ] + self._destroy_queue  # Copy not needed, will be copied anyway due to list concatenation
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
        self._name = self.service().sanitized_name(
            f'UDS-Pub-{self.servicepool_name()}-{int(time.time())%256:2X}-{self.revision()}'
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

    @must_have_vmid
    def op_start(self) -> None:
        """
        This method is called when the service is started
        """
        self.service().start(self, self._vmid)

    def op_start_completed(self) -> None:
        """
        This method is called when the service start is completed
        """
        pass

    @must_have_vmid
    def op_stop(self) -> None:
        """
        This method is called for stopping the service
        """
        self.service().stop(self, self._vmid)

    def op_stop_completed(self) -> None:
        """
        This method is called when the service stop is completed
        """
        pass

    @must_have_vmid
    def op_shutdown(self) -> None:
        """
        This method is called for shutdown the service
        """
        self.service().shutdown(self, self._vmid)

    def op_shutdown_completed(self) -> None:
        """
        This method is called when the service shutdown is completed
        """
        pass

    def op_remove(self) -> None:
        """
        This method is called when the service is removed
        By default, we need a remove machine on the service, use it
        """
        self.service().delete(self, self._vmid)

    def op_remove_completed(self) -> None:
        """
        This method is called when the service removal is completed
        """
        pass

    def op_nop(self) -> None:
        """
        This method is called when the service is doing nothing
        This does nothing, as it's a NOP operation
        """
        pass

    def op_destroy_validator(self) -> None:
        """
        This method is called to check if the userservice has an vmid to stop destroying it if needed
        As it is inserted in the destroy queue as first step, if no vmid is present, it will finish right now
        Note that can be overrided to do something else
        """
        # If does not have vmid, we can finish right now
        if self._vmid == '':
            self._queue[:] = [Operation.FINISH]  # so we can finish right now
            return

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
        if self.service().is_running(self, self._vmid):
            return types.states.TaskState.FINISHED

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
        if self.service().is_running(self, self._vmid) is False:
            return types.states.TaskState.FINISHED

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

    def op_nop_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is doing nothing
        """
        return types.states.TaskState.FINISHED

    @typing.final
    def op_retry_checker(self) -> types.states.TaskState:
        # If max retrieas has beeen reached, error should already have been set
        if self._queue[0] == Operation.ERROR:
            return types.states.TaskState.ERROR
        return types.states.TaskState.FINISHED

    def op_destroy_validator_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is validating the destroy operation
        """
        return types.states.TaskState.FINISHED

    def op_custom_checker(self, operation: Operation) -> types.states.TaskState:
        """
        This method is called to check if the service is doing a custom operation
        """
        return types.states.TaskState.FINISHED

    # ERROR, FINISH and UNKNOWN are not here, as they are final states not needing to be checked

    # We use same operation type for Publication and UserService. We add "unsupported" to
    # cover not defined operations (will raise an exception)
    def op_unsupported(self) -> None:
        raise Exception('Operation not defined')

    def op_unsupported_checker(self) -> types.states.TaskState:
        raise Exception('Operation not defined')

    @staticmethod
    def _op2str(op: Operation) -> str:
        return op.name

    def _debug(self, txt: str) -> str:
        msg = f'Queue at {txt} for {self._name}: {self._queue}, vmid:{self._vmid}'
        logger.debug(
            msg,
        )
        return msg

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
    Operation.SUSPEND: DynamicPublication.op_unsupported,
    Operation.SUSPEND_COMPLETED: DynamicPublication.op_unsupported,
    Operation.RESET: DynamicPublication.op_unsupported,
    Operation.RESET_COMPLETED: DynamicPublication.op_unsupported,
    Operation.DELETE: DynamicPublication.op_remove,
    Operation.DELETE_COMPLETED: DynamicPublication.op_remove_completed,
    Operation.WAIT: DynamicPublication.op_unsupported,
    Operation.NOP: DynamicPublication.op_nop,
    Operation.DESTROY_VALIDATOR: DynamicPublication.op_destroy_validator,
    # Retry operation has no executor, look "retry_later" method
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
    Operation.SUSPEND: DynamicPublication.op_unsupported_checker,
    Operation.SUSPEND_COMPLETED: DynamicPublication.op_unsupported_checker,
    Operation.RESET: DynamicPublication.op_unsupported_checker,
    Operation.RESET_COMPLETED: DynamicPublication.op_unsupported_checker,
    Operation.DELETE: DynamicPublication.op_remove_checker,
    Operation.DELETE_COMPLETED: DynamicPublication.op_remove_completed_checker,
    Operation.WAIT: DynamicPublication.op_unsupported_checker,
    Operation.NOP: DynamicPublication.op_nop_checker,
    Operation.DESTROY_VALIDATOR: DynamicPublication.op_destroy_validator_checker,
    # Retry operation can be inserted by a executor, so it will need a checker
    Operation.RETRY: DynamicPublication.op_retry_checker,
}
