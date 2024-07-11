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
import functools
import logging
import typing
import collections.abc

from uds.core import services, types, consts
from uds.core.util import autoserializable, log
from uds.core.util.model import sql_stamp_seconds

from .. import exceptions

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from . import service

logger = logging.getLogger(__name__)


# Decorator that tests that _vmid is not empty
# Used by some default methods that require a vmid to work
def must_have_vmid(fnc: typing.Callable[[typing.Any], None]) -> typing.Callable[['DynamicUserService'], None]:
    @functools.wraps(fnc)
    def wrapper(self: 'DynamicUserService') -> None:
        if self._vmid == '':
            # Change current operation to NOP and return
            # This is so we do not invoque the "checker" method again an nonexisent vmid
            self._queue[0] = types.services.Operation.NOP
            return  # May not have an vmid on some situations (as first copying disks, and so on)
        return fnc(self)

    return wrapper


class DynamicUserService(services.UserService, autoserializable.AutoSerializable, abc.ABC):
    """
    This class represents a fixed user service, that is, a service that is assigned to an user
    and that will be always the from a "fixed" machine, that is, a machine that is not created.
    """

    suggested_delay = consts.services.SUGGESTED_CHECK_INTERVAL

    # Some customization fields
    # If ip can be manually overriden, normally True... (set by actor, for example)
    can_set_ip: typing.ClassVar[bool] = True
    # How many times we will check for a state before giving up
    max_state_checks: typing.ClassVar[int] = 20
    # How many "retries" operation on same state will be allowed before giving up
    max_retries: typing.ClassVar[int] = consts.services.MAX_RETRIES
    # If store_error_as_finished is true, and an error occurs, the machine is set to FINISHED instead of ERROR
    store_error_as_finished: typing.ClassVar[bool] = False
    # If must wait untill finish queue for destroying the machine
    wait_until_finish_to_destroy: typing.ClassVar[bool] = False

    _name = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _ip = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    # cast is used to ensure that when data is reloaded, it's casted to the correct type
    _queue = autoserializable.ListField[types.services.Operation](cast=types.services.Operation.from_int)
    _is_flagged_for_destroy = autoserializable.BoolField(default=False)

    # Extra info, not serializable, to keep information in case of exception and debug it
    _error_debug_info: typing.Optional[str] = None

    _create_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.INITIALIZE,
        types.services.Operation.CREATE,
        types.services.Operation.CREATE_COMPLETED,
        types.services.Operation.START,
        types.services.Operation.START_COMPLETED,
        types.services.Operation.FINISH,
    ]
    _create_queue_l1_cache: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.INITIALIZE,
        types.services.Operation.CREATE,
        types.services.Operation.CREATE_COMPLETED,
        types.services.Operation.START,
        types.services.Operation.START_COMPLETED,
        types.services.Operation.FINISH,
    ]

    _create_queue_l2_cache: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.INITIALIZE,
        types.services.Operation.CREATE,
        types.services.Operation.CREATE_COMPLETED,
        types.services.Operation.START,
        types.services.Operation.START_COMPLETED,
        types.services.Operation.WAIT,
        types.services.Operation.SUSPEND,
        types.services.Operation.SUSPEND_COMPLETED,
        types.services.Operation.FINISH,
    ]
    # If gracefull_stop, will prepend a soft_shutdown
    _destroy_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.STOP,
        types.services.Operation.STOP_COMPLETED,
        types.services.Operation.DELETE,
        types.services.Operation.DELETE_COMPLETED,
        types.services.Operation.FINISH,
    ]

    _move_to_l1_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.START,
        types.services.Operation.START_COMPLETED,
        types.services.Operation.FINISH,
    ]

    _move_to_l2_queue: typing.ClassVar[list[types.services.Operation]] = [
        types.services.Operation.SUSPEND,
        types.services.Operation.SUSPEND_COMPLETED,
        types.services.Operation.FINISH,
    ]

    @typing.final
    def _reset_checks_counter(self) -> None:
        with self.storage.as_dict() as data:
            data['exec_count'] = 0

    @typing.final
    def _inc_checks_counter(self, op: types.services.Operation) -> typing.Optional[types.states.TaskState]:
        with self.storage.as_dict() as data:
            count = data.get('exec_count', 0) + 1
            data['exec_count'] = count
        if count > self.max_state_checks:
            return self.error(f'Max checks reached on {op}')
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

        if retries > self.max_retries:  # get "own class" max retries
            return self.error(f'Max retries reached')

        return None

    @typing.final
    def _current_op(self) -> types.services.Operation:
        """
        Get the current operation from the queue

        Checks that the queue is upgraded, and if not, migrates it
        Note:
          This method will be here for a while, to ensure future compat with old data.
          Eventually, this mechanincs will be removed, but no date is set for that.
          There is almos not penalty on keeping this here, as it's only an small check
          We also could have used marshal/unmarshal, but this is more clear and easy to maintain
        """
        if not self._queue:
            return types.services.Operation.FINISH

        return self._queue[0]

    @typing.final
    def _set_queue(self, queue: list[types.services.Operation]) -> None:
        """
        Sets the queue of tasks to be executed
        Ensures that we mark it as new format
        """
        self._queue = queue

    @typing.final
    def _generate_name(self) -> str:
        """
        Can be overriden. Generates a unique name for the machine.
        Default implementation uses the name generator with the basename and lenname fields

        Returns:
            str: A unique name for the machine
        """
        return self.name_generator().get(self.service().get_basename(), self.service().get_lenname())

    @typing.final
    def error(self, reason: typing.Union[str, Exception]) -> types.states.TaskState:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self._error(reason)"
        """
        self._error_debug_info = self._debug(repr(reason))
        reason = str(reason)
        logger.debug('Setting error state, reason: %s (%s)', reason, self._queue, stack_info=True, stacklevel=3)
        self.do_log(types.log.LogLevel.ERROR, reason)

        if self._vmid:
            if self.service().should_maintain_on_error() is False:
                try:
                    self.service().delete(self, self._vmid)
                    self._vmid = ''
                except Exception as e:
                    logger.exception('Exception removing machine %s: %s', self._vmid, e)
                    self._vmid = ''
                    self.do_log(types.log.LogLevel.ERROR, f'Error removing machine: {e}')
            else:
                logger.debug('Keep on error is enabled, not removing machine')
                self._set_queue(
                    [types.services.Operation.FINISH]
                    if self.store_error_as_finished
                    else [types.services.Operation.ERROR]
                )
                return types.states.TaskState.FINISHED

        self._set_queue([types.services.Operation.ERROR])
        self._reason = reason
        return types.states.TaskState.ERROR

    @typing.final
    def _execute_queue(self) -> types.states.TaskState:
        self._debug('execute_queue')
        op = self._current_op()

        if op == types.services.Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == types.services.Operation.FINISH:
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
        except exceptions.RetryableError as e:
            # This is a retryable error, so we will retry later
            return self.retry_later()
        except Exception as e:
            logger.exception('Unexpected FixedUserService exception: %s', e)
            return self.error(e)

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
            return self.error('Max retries reached')
        self._queue.insert(0, types.services.Operation.RETRY)
        return types.states.TaskState.FINISHED

    # Utility overrides for type checking...
    # Probably, overriden again on child classes
    def service(self) -> 'service.DynamicService':
        return typing.cast('service.DynamicService', super().service())

    def get_vmname(self) -> str:
        """
        Accesory method to calc the VM name.
        Default implemetation returns "UDS_" + self.get_name() (or consts.NO_MORE_NAMES if no more names are available)

        Returns:
            str: The name of the vm (consts.NO_MORE_NAMES if no more names are available)

        Note:
            Override it if you need a different vm name. It's used to remove duplicates!
        """
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            return consts.NO_MORE_NAMES

        return self.service().sanitized_name(f'UDS_{name}')  # Default implementation

    # overridable, to allow receiving notifications from, for example, services
    def notify(self, message: str, data: typing.Any = None) -> None:
        pass

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
        # Note that get_mac is used for creating a new mac, returning the one of the vm or whatever
        # This is responsibility of the service, not of the user service
        if not self._mac:
            self._mac = self.service().get_mac(self, self._vmid) or ''
        return self._mac

    @typing.final
    def get_ip(self) -> str:
        if self._ip == '':
            try:
                if self._vmid:
                    # Provide self to the service, so it can use some of our methods for whaterever it needs
                    self._ip = self.service().get_ip(self, self._vmid)
            except Exception:
                logger.warning(
                    'Error obtaining IP for %s: %s', self.__class__.__name__, self._vmid, exc_info=True
                )
        return self._ip

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
    def move_to_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        if level == types.services.CacheLevel.L1:
            self._set_queue(self._move_to_l1_queue.copy())
        else:
            self._set_queue(self._move_to_l2_queue.copy())
        return self._execute_queue()

    @typing.final
    def process_ready_from_os_manager(self, data: typing.Any) -> types.states.TaskState:
        # Eat the WAIT operation if it is in the queue
        # At most, we will have one WAIT operation in the queue
        if types.services.Operation.WAIT in self._queue:
            self._queue.remove(types.services.Operation.WAIT)
            # And keep processing
            return self._execute_queue()

        return types.states.TaskState.FINISHED

    @typing.final
    def set_ready(self) -> types.states.TaskState:
        # If already ready, return finished
        try:
            if self.cache.get('ready', '0') == '1':
                self._set_queue([types.services.Operation.FINISH])
            elif self.service().is_running(self, self._vmid):
                self.cache.put('ready', '1', consts.cache.SHORT_CACHE_TIMEOUT // 2)  # short cache timeout
                self._set_queue([types.services.Operation.FINISH])
            else:
                self._set_queue(
                    [
                        types.services.Operation.START,
                        types.services.Operation.START_COMPLETED,
                        types.services.Operation.FINISH,
                    ]
                )
        except Exception as e:
            return self.error(f'Error on setReady: {e}')
        return self._execute_queue()

    def reset(self) -> types.states.TaskState:
        if self._vmid != '':
            self._set_queue(
                [
                    types.services.Operation.RESET,
                    types.services.Operation.RESET_COMPLETED,
                    types.services.Operation.FINISH,
                ]
            )

        return types.states.TaskState.FINISHED

    @typing.final
    def check_state(self) -> types.states.TaskState:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._current_op()

        if op == types.services.Operation.ERROR:
            return types.states.TaskState.ERROR

        if op == types.services.Operation.FINISH:
            # If has a deferred destroy, do it now
            if self.wait_until_finish_to_destroy and self._is_flagged_for_destroy:
                self._is_flagged_for_destroy = False
                # Simply ensures nothing is left on queue and returns FINISHED
                self._set_queue([types.services.Operation.FINISH])
                return self.destroy()
            return types.states.TaskState.FINISHED

        if op != types.services.Operation.WAIT:
            # All operations except WAIT will check against checks counter
            counter_state = self._inc_checks_counter(op)
            if counter_state is not None:
                return counter_state  # Error, Finished or None (eror can return Finished too)

        try:
            if op.is_custom():
                state = self.op_custom_checker(op)
            else:
                operation_checker = _CHECKERS[op]
                state = getattr(self, operation_checker.__name__)()

            if state == types.states.TaskState.FINISHED:
                # Remove finished operation from queue
                top_op = self._queue.pop(0)
                if (
                    top_op != types.services.Operation.RETRY
                ):  # Inserted if a retrayable error occurs on execution queue
                    self._reset_retries_counter()
                return self._execute_queue()

            return state
        except exceptions.RetryableError as e:
            # This is a retryable error, so we will retry later
            # We don not need to push a NOP here, as we will retry the same operation checking again
            # And it has not been removed from the queue
            return types.states.TaskState.RUNNING
        except Exception as e:
            return self.error(e)

    @typing.final
    def destroy(self) -> types.states.TaskState:
        """
        Destroys the service
        """
        self._is_flagged_for_destroy = False  # Reset
        op = self._current_op()

        if op == types.services.Operation.ERROR:
            return self.error('Machine is already in error state!')

        shutdown_operations: list[types.services.Operation] = (
            []
            if not self.service().should_try_soft_shutdown()
            else [types.services.Operation.SHUTDOWN, types.services.Operation.SHUTDOWN_COMPLETED]
        )
        destroy_operations = (
            [types.services.Operation.DESTROY_VALIDATOR] + shutdown_operations + self._destroy_queue
        )  # copy is not needed due to list concatenation

        # If a "paused" state, reset queue to destroy
        if op in (types.services.Operation.FINISH, types.services.Operation.WAIT):
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

    def error_reason(self) -> str:
        return self._reason

    def remove_duplicated_names(self) -> None:
        name = self.get_vmname()
        try:
            for vmid in self.service().perform_find_duplicates(name, self.get_unique_id()):
                userservice = self.db_obj()
                log.log(
                    userservice.service_pool,
                    types.log.LogLevel.WARNING,
                    f'Found duplicated vm {name} with mac {self.get_unique_id()}. Removing it',  # mac is the unique id
                    types.log.LogSource.SERVICE,
                )
                self.service().delete(self, vmid)
                # Retry again in a while if duplicated machines where found, until we remove all of them
                self.retry_later()
        except Exception as e:
            logger.warning('Locating duplicated machines: %s', e)

    # Execution methods
    # Every types.services.Operation has an execution method and a check method
    def op_initialize(self) -> None:
        """
        This method is called when the service is initialized

        By default, tries to locate duplicated machines and remove them.

        If you override this method, you should take care yourself of removing duplicated machines
        (maybe only calling "remove_duplicated_name" method)
        """
        self.remove_duplicated_names()

    @abc.abstractmethod
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

    @must_have_vmid
    def op_start(self) -> None:
        """
        This method is called when the service is started
        """
        if not self.service().is_running(self, self._vmid):
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
        if self.service().is_running(self, self._vmid):
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
        shutdown_stamp = -1
        if not self.service().is_running(self, self._vmid):
            # Already stopped, just finish
            return

        self.service().shutdown(self, self._vmid)
        shutdown_stamp = sql_stamp_seconds()

        with self.storage.as_dict() as data:
            data['shutdown'] = shutdown_stamp

    def op_shutdown_completed(self) -> None:
        """
        This method is called when the service shutdown is completed
        """
        pass

    @must_have_vmid
    def op_suspend(self) -> None:
        """
        This method is called for suspend the service
        """
        # Note that by default suspend is "shutdown" and not "stop" because we want to do clean shutdowns
        self.op_shutdown()

    def op_suspend_completed(self) -> None:
        """
        This method is called when the service suspension is completed
        """
        pass

    @must_have_vmid
    def op_reset(self) -> None:
        """
        This method is called when the service is reset
        """
        self.service().reset(self, self._vmid)

    def op_reset_completed(self) -> None:
        """
        This method is called when the service reset is completed
        """
        pass

    @must_have_vmid
    def op_delete(self) -> None:
        """
        This method is called when the service is removed
        """
        self.service().delete(self, self._vmid)

    def op_delete_completed(self) -> None:
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

    def op_destroy_validator(self) -> None:
        """
        This method is called to check if the userservice has an vmid to stop destroying it if needed
        As it is inserted in the destroy queue as first step, if no vmid is present, it will finish right now
        Note that can be overrided to do something else
        """
        # If does not have vmid, we can finish right now
        if self._vmid == '':
            self._set_queue([types.services.Operation.FINISH])  # so we can finish right now

    def op_custom(self, operation: types.services.Operation) -> None:
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

        return types.states.TaskState.RUNNING

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
        return types.states.TaskState.RUNNING

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
        if self.service().is_running(self, self._vmid) is False:
            return types.states.TaskState.FINISHED

        logger.debug('State is running')
        if sql_stamp_seconds() - shutdown_start > consts.os.MAX_GUEST_SHUTDOWN_WAIT:
            logger.debug('Time is consumed, falling back to stop on vmid %s', self._vmid)
            self.do_log(
                types.log.LogLevel.ERROR,
                f'Could not shutdown machine using soft power off in time ({consts.os.MAX_GUEST_SHUTDOWN_WAIT} seconds). Powering off.',
            )
            # Not stopped by guest in time, but must be stopped normally
            with self.storage.as_dict() as data:
                data['shutdown'] = -1
            # If stop is in queue, mark this as finished, else, add it to queue just after first (our) operation
            if types.services.Operation.STOP not in self._queue:
                # After current operation, add stop
                self._queue.insert(1, types.services.Operation.STOP)
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
        return self.op_shutdown_checker()

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

    def op_reset_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service reset is completed
        """
        return types.states.TaskState.FINISHED

    def op_delete_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is removed
        """
        return types.states.TaskState.FINISHED

    def op_delete_completed_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service removal is completed
        """
        return types.states.TaskState.FINISHED

    def op_wait_checker(self) -> types.states.TaskState:
        """
        Wait will remain in the same state until something external changes it (i.e. poping from the queue)
        """
        return types.states.TaskState.RUNNING

    @typing.final
    def op_nop_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the service is doing nothing
        """
        return types.states.TaskState.FINISHED

    @typing.final
    def op_retry_checker(self) -> types.states.TaskState:
        # If max retrieas has beeen reached, error should already have been set
        if self._queue[0] == types.services.Operation.ERROR:
            return types.states.TaskState.ERROR
        return types.states.TaskState.FINISHED

    def op_destroy_validator_checker(self) -> types.states.TaskState:
        """
        This method is called to check if the userservice has an vmid to stop destroying it if needed
        """
        # If does not have vmid, we can finish right now
        return types.states.TaskState.FINISHED  # If we are here, we have a vmid

    def op_custom_checker(self, operation: types.services.Operation) -> types.states.TaskState:
        """
        This method is called to check if the service is doing a custom operation
        """
        return types.states.TaskState.FINISHED

    # ERROR, FINISH and UNKNOWN are not here, as they are final states not needing to be checked

    @staticmethod
    def _op2str(op: types.services.Operation) -> str:
        return op.name

    def _debug(self, txt: str) -> str:
        return f'Queue at {txt} for {self._name}: {", ".join([DynamicUserService._op2str(op) for op in self._queue])}, mac:{self._mac}, vmId:{self._vmid}'


# This is a map of operations to methods
# types.services.Operation methods, due to the fact that can be overrided, must be invoked via instance
# We use getattr(FNC.__name__, ...) to use them, so we can use type checking and invoke them via instance
# Note that ERROR and FINISH are not here, as they final states not needing to be executed
_EXECUTORS: typing.Final[
    collections.abc.Mapping[types.services.Operation, collections.abc.Callable[[DynamicUserService], None]]
] = {
    types.services.Operation.INITIALIZE: DynamicUserService.op_initialize,
    types.services.Operation.CREATE: DynamicUserService.op_create,
    types.services.Operation.CREATE_COMPLETED: DynamicUserService.op_create_completed,
    types.services.Operation.START: DynamicUserService.op_start,
    types.services.Operation.START_COMPLETED: DynamicUserService.op_start_completed,
    types.services.Operation.STOP: DynamicUserService.op_stop,
    types.services.Operation.STOP_COMPLETED: DynamicUserService.op_stop_completed,
    types.services.Operation.SHUTDOWN: DynamicUserService.op_shutdown,
    types.services.Operation.SHUTDOWN_COMPLETED: DynamicUserService.op_shutdown_completed,
    types.services.Operation.SUSPEND: DynamicUserService.op_suspend,
    types.services.Operation.SUSPEND_COMPLETED: DynamicUserService.op_suspend_completed,
    types.services.Operation.RESET: DynamicUserService.op_reset,
    types.services.Operation.RESET_COMPLETED: DynamicUserService.op_reset_completed,
    types.services.Operation.DELETE: DynamicUserService.op_delete,
    types.services.Operation.DELETE_COMPLETED: DynamicUserService.op_delete_completed,
    types.services.Operation.WAIT: DynamicUserService.op_wait,
    types.services.Operation.NOP: DynamicUserService.op_nop,
    types.services.Operation.DESTROY_VALIDATOR: DynamicUserService.op_destroy_validator,
    # Retry operation has no executor, look "retry_later" method
}

# Same af before, but for check methods
_CHECKERS: typing.Final[
    collections.abc.Mapping[
        types.services.Operation, collections.abc.Callable[[DynamicUserService], types.states.TaskState]
    ]
] = {
    types.services.Operation.INITIALIZE: DynamicUserService.op_initialize_checker,
    types.services.Operation.CREATE: DynamicUserService.op_create_checker,
    types.services.Operation.CREATE_COMPLETED: DynamicUserService.op_create_completed_checker,
    types.services.Operation.START: DynamicUserService.op_start_checker,
    types.services.Operation.START_COMPLETED: DynamicUserService.op_start_completed_checker,
    types.services.Operation.STOP: DynamicUserService.op_stop_checker,
    types.services.Operation.STOP_COMPLETED: DynamicUserService.op_stop_completed_checker,
    types.services.Operation.SHUTDOWN: DynamicUserService.op_shutdown_checker,
    types.services.Operation.SHUTDOWN_COMPLETED: DynamicUserService.op_shutdown_completed_checker,
    types.services.Operation.SUSPEND: DynamicUserService.op_suspend_checker,
    types.services.Operation.SUSPEND_COMPLETED: DynamicUserService.op_suspend_completed_checker,
    types.services.Operation.RESET: DynamicUserService.op_reset_checker,
    types.services.Operation.RESET_COMPLETED: DynamicUserService.op_reset_completed_checker,
    types.services.Operation.DELETE: DynamicUserService.op_delete_checker,
    types.services.Operation.DELETE_COMPLETED: DynamicUserService.op_delete_completed_checker,
    types.services.Operation.WAIT: DynamicUserService.op_wait_checker,
    types.services.Operation.NOP: DynamicUserService.op_nop_checker,
    types.services.Operation.DESTROY_VALIDATOR: DynamicUserService.op_destroy_validator_checker,
    # Retry operation can be inserted by a executor, so it will need a checker
    types.services.Operation.RETRY: DynamicUserService.op_retry_checker,
}
