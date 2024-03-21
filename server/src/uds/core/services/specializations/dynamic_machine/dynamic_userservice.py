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
import abc
import logging
import typing
import collections.abc

from uds.core import services, types, consts
from uds.core.types.services import Operation
from uds.core.util import log, autoserializable
from uds.core.util.model import sql_stamp_seconds

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from . import dynamic_service

logger = logging.getLogger(__name__)


class DynamicUserService(services.UserService, autoserializable.AutoSerializable, abc.ABC):
    """
    This class represents a fixed user service, that is, a service that is assigned to an user
    and that will be always the from a "fixed" machine, that is, a machine that is not created.
    """

    suggested_delay = 5

    # Some customization fields
    # If ip can be manually overriden
    can_set_ip: typing.ClassVar[bool] = False
    # How many times we will check for a state before giving up
    max_state_checks: typing.ClassVar[int] = 20
    # If keep_state_sets_error is true, and an error occurs, the machine is set to FINISHED instead of ERROR
    keep_state_sets_error: typing.ClassVar[bool] = False
    # If must wait untill finish queue for destroying the machine
    wait_until_finish_to_destroy: typing.ClassVar[bool] = False

    _name = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()  # Default is empty list
    _is_flagged_for_destroy = autoserializable.BoolField(default=False)
    # In order to allow migrating from old data, we will mark if the _queue has our format or the old one
    _queue_has_new_format = autoserializable.BoolField(default=False)

    # Note that even if SNAPHSHOT operations are in middel
    # implementations may opt to no have snapshots at all
    # In this case, the process_snapshot method will do nothing
    _create_queue: typing.ClassVar[list[Operation]] = [
        Operation.INITIALIZE,
        Operation.CREATE,
        Operation.CREATE_COMPLETED,
        Operation.START,
        Operation.START_COMPLETED,
        Operation.FINISH,
    ]
    _create_queue_l1_cache: typing.ClassVar[list[Operation]] = [
        Operation.INITIALIZE,
        Operation.CREATE,
        Operation.CREATE_COMPLETED,
        Operation.START,
        Operation.START_COMPLETED,
        Operation.FINISH,
    ]

    _create_queue_l2_cache: typing.ClassVar[list[Operation]] = [
        Operation.INITIALIZE,
        Operation.CREATE,
        Operation.CREATE_COMPLETED,
        Operation.START,
        Operation.START_COMPLETED,
        Operation.WAIT,
        Operation.SUSPEND,
        Operation.SUSPEND_COMPLETED,
        Operation.FINISH,
    ]
    # If gracefull_stop, will prepend a soft_shutdown
    _destroy_queue: typing.ClassVar[list[Operation]] = [
        Operation.STOP,
        Operation.STOP_COMPLETED,
        Operation.REMOVE,
        Operation.REMOVE_COMPLETED,
        Operation.FINISH,
    ]

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
        """
        Get the current operation from the queue
        
        Checks that the queue is upgraded, and if not, migrates it
        Note: 
          This method will be here for a while, to ensure future compat with old data.
          Eventually, this mechanincs will be removed, but no date is set for that.
          There is almos not penalty on keeping this here, as it's only an small check
          We also could have used marshal/unmarshal, but this is more clear and easy to maintain
        """
        if self._queue_has_new_format is False:
            self.migrate_old_queue()
            self._queue_has_new_format = True
            
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]
    
    def _set_queue(self, queue: list[Operation]) -> None:
        """
        Sets the queue of tasks to be executed
        Ensures that we mark it as new format
        """
        self._queue = queue
        self._queue_has_new_format = True
        
    def _retry_again(self) -> types.states.TaskState:
        """
        Retries the current operation
        For this, we insert a NOP that will be consumed instead of the current operationç
        by the queue runner
        """
        self._queue.insert(0, Operation.NOP)
        return types.states.TaskState.RUNNING

    def _generate_name(self) -> str:
        """
        Can be overriden. Generates a unique name for the machine.
        Default implementation uses the name generator with the basename and lenname fields

        Returns:
            str: A unique name for the machine
        """
        return self.name_generator().get(self.service().get_basename(), self.service().get_lenname())

    def _error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid:
            if self.service().keep_on_error() is False:
                try:
                    self.service().remove_machine(self, self._vmid)
                    self._vmid = ''
                except Exception as e:
                    logger.exception('Exception removing machine: %s', e)
            else:
                logger.debug('Keep on error is enabled, not removing machine')
                if self.keep_state_sets_error is False:
                    self._set_queue([Operation.FINISH])
                return types.states.TaskState.FINISHED

        self._set_queue([Operation.ERROR])
        self._reason = reason
        return types.states.TaskState.ERROR

    # Utility overrides for type checking...
    # Probably, overriden again on child classes
    def service(self) -> 'dynamic_service.DynamicService':
        return typing.cast('dynamic_service.DynamicService', super().service())

    @typing.final
    def get_name(self) -> str:
        if self._name == '':
            try:
                self._name = self._generate_name()
            except KeyError:
                return consts.NO_MORE_NAMES
        return self._name

    @typing.final
    def set_ip(self, ip: str) -> None:
        if self.can_set_ip:
            logger.debug('Setting IP to %s', ip)
            self._ip = ip
        else:
            logger.debug('Setting IP to %s (ignored)', ip)

    @typing.final
    def get_unique_id(self) -> str:
        # Provide self to the service, so it can some of our methods to generate the unique id
        # (for example, own mac generator, that will autorelease the mac as soon as the machine is removed)
        if not self._mac:
            self._mac = self.service().get_machine_mac(self, self._vmid) or ''
        return self._mac

    @typing.final
    def get_ip(self) -> str:
        # Provide self to the service, so it can some of our methods to generate the unique id
        try:
            if self._vmid:
                return self.service().get_machine_ip(self, self._vmid)
        except Exception:
            logger.warning('Error obtaining IP for %s: %s', self.__class__.__name__, self._vmid, exc_info=True)
            pass
        return ''

    @typing.final
    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._set_queue(self._create_queue.copy())  # copy is needed to avoid modifying class var
        return self._execute_queue()

    @typing.final
    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        if level == types.services.CacheLevel.L1:
            self._set_queue(self._create_queue_l1_cache.copy())
        else:
            self._set_queue(self._create_queue_l2_cache.copy())
        return self._execute_queue()

    @typing.final
    def set_ready(self) -> types.states.TaskState:
        # If already ready, return finished
        try:
            if self.cache.get('ready') == '1' or self.service().is_machine_running(self, self._vmid):
                self._set_queue([Operation.START_COMPLETED, Operation.FINISH])
            else:
                self._set_queue([Operation.START, Operation.START_COMPLETED, Operation.FINISH])
        except Exception as e:
            return self._error(f'Error on setReady: {e}')
        return self._execute_queue()

    def reset(self) -> types.states.TaskState:
        if self._vmid != '':
            self._set_queue([Operation.RESET, Operation.RESET_COMPLETED, Operation.FINISH])

        return types.states.TaskState.FINISHED

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
                operation_runner = _EXECUTORS[op]

                # Invoke using instance, we have overrided methods
                # and we want to use the overrided ones
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
            # If has a deferred destroy, do it now
            if self.wait_until_finish_to_destroy and self._is_flagged_for_destroy:
                self._is_flagged_for_destroy = False
                # Simply ensures nothing is left on queue and returns FINISHED
                self._set_queue([Operation.FINISH])
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
                state = _CHECKERS[op](self)

            if state == types.states.TaskState.FINISHED:
                # Remove finished operation from queue
                self._queue.pop(0)
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)
        
    @typing.final
    def destroy(self) -> types.states.TaskState:
        """
        Destroys the service
        """
        self._is_flagged_for_destroy = False  # Reset
        op = self._current_op()

        if op == Operation.ERROR:
            return self._error('Machine is already in error state!')

        shutdown_operations: list[Operation] = [] if not self.service().try_graceful_shutdown() else [Operation.SHUTDOWN, Operation.SHUTDOWN_COMPLETED]
        destroy_operations = shutdown_operations + self._destroy_queue  # copy is not needed due to list concatenation

        # If a "paused" state, reset queue to destroy
        if op in (Operation.FINISH, Operation.WAIT):
            self._set_queue(destroy_operations)
            return self._execute_queue()

        # If must wait until finish, flag for destroy and wait
        if self.wait_until_finish_to_destroy:
            self._is_flagged_for_destroy = True
        else:
            # If other operation, wait for finish before destroying
            self._set_queue([op] + destroy_operations)
            # Do not execute anything.here, just continue normally
        return types.states.TaskState.RUNNING


    # Execution methods
    # Every Operation has an execution method and a check method
    def op_initialize(self) -> None:
        """
        This method is called when the service is initialized
        """
        pass

    def op_create(self) -> None:
        """
        This method is called when the service is created
        """
        pass

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
        shutdown_stamp = -1
        is_running = self.service().is_machine_running(self, self._vmid)
        if not is_running:
            # Already stopped, just finish
            return
        
        self.service().shutdown_machine(self, self._vmid)
        shutdown_stamp = sql_stamp_seconds()
        
        with self.storage.as_dict() as data:
            data['shutdown'] = shutdown_stamp

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
        This method is called to check if the service is shutdown in time
        Else, will fall back to stop
        """
        with self.storage.as_dict() as data:
            shutdown_start = data.get('shutdown', -1)
        logger.debug('Shutdown start: %s', shutdown_start)
        
        if shutdown_start < 0:  # Was already stopped
            # Machine is already stop
            logger.debug('Machine WAS stopped')
            return types.states.TaskState.FINISHED

        logger.debug('Checking State')
        # Check if machine is already stopped  (As soon as it is not running, we will consider it stopped)
        if self.service().is_machine_running(self, self._vmid) is False:
            return types.states.TaskState.FINISHED

        logger.debug('State is running')
        if sql_stamp_seconds() - shutdown_start > consts.os.MAX_GUEST_SHUTDOWN_WAIT:
            logger.debug('Time is consumed, falling back to stop on vmid %s', self._vmid)
            self.do_log(
                log.LogLevel.ERROR,
                f'Could not shutdown machine using soft power off in time ({consts.os.MAX_GUEST_SHUTDOWN_WAIT} seconds). Powering off.',
            )
            # Not stopped by guest in time, but must be stopped normally
            with self.storage.as_dict() as data:
                data['shutdown'] = -1
            # If stop is in queue, mark this as finished, else, add it to queue just after first (our) operation
            if Operation.STOP not in self._queue:
                # After current operation, add stop
                self._queue.insert(1, Operation.STOP)
            return types.states.TaskState.FINISHED

        # Not finished yet
        return types.states.TaskState.RUNNING

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
    
    def migrate_old_queue(self) -> None:
        """
        If format has to be converted, override this method and do the conversion here
        Remember to replace self_queue with the new one
        """
        pass

    @staticmethod
    def _op2str(op: Operation) -> str:
        return op.name

    def _debug(self, txt: str) -> None:
        logger.debug(
            'Queue at %s for %s: %s, mac:%s, vmId:%s',
            txt,
            self._name,
            [DynamicUserService._op2str(op) for op in self._queue],
            self._mac,
            self._vmid,
        )


# This is a map of operations to methods
# Operation methods, due to the fact that can be overrided, must be invoked via instance
# We use getattr(FNC.__name__, ...) to use them, so we can use type checking and invoke them via instance
# Note that ERROR and FINISH are not here, as they final states not needing to be executed
_EXECUTORS: typing.Final[
    collections.abc.Mapping[Operation, collections.abc.Callable[[DynamicUserService], None]]
] = {
    Operation.INITIALIZE: DynamicUserService.op_initialize,
    Operation.CREATE: DynamicUserService.op_create,
    Operation.CREATE_COMPLETED: DynamicUserService.op_create_completed,
    Operation.START: DynamicUserService.op_start,
    Operation.START_COMPLETED: DynamicUserService.op_start_completed,
    Operation.STOP: DynamicUserService.op_stop,
    Operation.STOP_COMPLETED: DynamicUserService.op_stop_completed,
    Operation.SHUTDOWN: DynamicUserService.op_shutdown,
    Operation.SHUTDOWN_COMPLETED: DynamicUserService.op_shutdown_completed,
    Operation.SUSPEND: DynamicUserService.op_suspend,
    Operation.SUSPEND_COMPLETED: DynamicUserService.op_suspend_completed,
    Operation.REMOVE: DynamicUserService.op_remove,
    Operation.REMOVE_COMPLETED: DynamicUserService.op_remove_completed,
    Operation.WAIT: DynamicUserService.op_wait,
    Operation.NOP: DynamicUserService.op_nop,
}

# Same af before, but for check methods
_CHECKERS: typing.Final[
    collections.abc.Mapping[Operation, collections.abc.Callable[[DynamicUserService], types.states.TaskState]]
] = {
    Operation.INITIALIZE: DynamicUserService.op_initialize_checker,
    Operation.CREATE: DynamicUserService.op_create_checker,
    Operation.CREATE_COMPLETED: DynamicUserService.op_create_completed_checker,
    Operation.START: DynamicUserService.op_start_checker,
    Operation.START_COMPLETED: DynamicUserService.op_start_completed_checker,
    Operation.STOP: DynamicUserService.op_stop_checker,
    Operation.STOP_COMPLETED: DynamicUserService.op_stop_completed_checker,
    Operation.SHUTDOWN: DynamicUserService.op_shutdown_checker,
    Operation.SHUTDOWN_COMPLETED: DynamicUserService.op_shutdown_completed_checker,
    Operation.SUSPEND: DynamicUserService.op_suspend_checker,
    Operation.SUSPEND_COMPLETED: DynamicUserService.op_suspend_completed_checker,
    Operation.REMOVE: DynamicUserService.op_remove_checker,
    Operation.REMOVE_COMPLETED: DynamicUserService.op_remove_completed_checker,
    Operation.WAIT: DynamicUserService.op_wait_checker,
    Operation.NOP: DynamicUserService.op_nop_checker,
}
