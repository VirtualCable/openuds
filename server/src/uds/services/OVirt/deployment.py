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
#      and/or other materials provided with the distribution.u
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
import collections.abc
import enum
import logging
import pickle  # nosec: not insecure, we are loading our own data
import typing

from uds.core import consts, services
from uds.core.managers.userservice import UserServiceManager
from uds.core.types.states import State
from uds.core.util import autoserializable, log

from .jobs import OVirtDeferredRemoval

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

    from .publication import OVirtPublication
    from .service import OVirtLinkedService

logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    """
    Operation enumeration
    """

    CREATE = 0
    START = 1
    STOP = 2
    SUSPEND = 3
    REMOVE = 4
    WAIT = 5
    ERROR = 6
    FINISH = 7
    RETRY = 8
    CHANGEMAC = 9

    opUnknown = 99

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.opUnknown


UP_STATES: typing.Final[set[str]] = {'up', 'reboot_in_progress', 'powering_up', 'restoring_state'}


class OVirtLinkedDeployment(services.UserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.

    """

    # : Recheck every six seconds by default (for task methods)
    suggested_delay = 6

    _name = autoserializable.StringField(default='')
    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()

    # Utility overrides for type checking...
    def service(self) -> 'OVirtLinkedService':
        return typing.cast('OVirtLinkedService', super().service())

    def publication(self) -> 'OVirtPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OVirtPublication', pub)

    def unmarshal(self, data: bytes) -> None:
        """
        Does nothing here also, all data are keeped at environment storage
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._vmid = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._queue = [
                Operation.from_int(i) for i in pickle.loads(vals[6])
            ]  # nosec: not insecure, we are loading our own data

        self.mark_for_upgrade()  # Flag so manager can save it again with new format

    def get_name(self) -> str:
        if self._name == '':
            try:
                self._name = self.name_generator().get(
                    self.service().get_basename(), self.service().getLenName()
                )
            except KeyError:
                return consts.NO_MORE_NAMES
        return self._name

    def set_ip(self, ip: str) -> None:
        """
        In our case, there is no OS manager associated with this, so this method
        will never get called, but we put here as sample.

        Whenever an os manager actor notifies the broker the state of the service
        (mainly machines), the implementation of that os manager can (an probably will)
        need to notify the IP of the deployed service. Remember that UDS treats with
        IP services, so will probable needed in every service that you will create.
        :note: This IP is the IP of the "consumed service", so the transport can
               access it.
        """
        logger.debug('Setting IP to %s', ip)
        self._ip = ip

    def get_unique_id(self) -> str:
        """
        Return and unique identifier for this service.
        In our case, we will generate a mac name, that can be also as sample
        of 'mac' generator use, and probably will get used something like this
        at some services.

        The get method of a mac generator takes one param, that is the mac range
        to use to get an unused mac.
        """
        if self._mac == '':
            self._mac = self.mac_generator().get(self.service().getMacRange())
        return self._mac

    def get_ip(self) -> str:
        """
        We need to implement this method, so we can return the IP for transports
        use. If no IP is known for this service, this must return None

        If our sample do not returns an IP, IP transport will never work with
        this service. Remember in real cases to return a valid IP address if
        the service is accesible and you alredy know that (for example, because
        the IP has been assigend via setIp by an os manager) or because
        you get it for some other method.

        Storage returns None if key is not stored.

        :note: Keeping the IP address is responsibility of the User Deployment.
               Every time the core needs to provide the service to the user, or
               show the IP to the administrator, this method will get called

        """
        return self._ip

    def set_ready(self) -> str:
        """
        The method is invoked whenever a machine is provided to an user, right
        before presenting it (via transport rendering) to the user.
        """
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            state = self.service().get_machine_state(self._vmid)

            if state == 'unknown':
                return self._error('Machine is not available anymore')

            if state not in UP_STATES:
                self._queue = [Operation.START, Operation.FINISH]
                return self._execute_queue()

            self.cache.put('ready', '1')
        except Exception as e:
            self.do_log(log.LogLevel.ERROR, f'Error on setReady: {e}')
            # Treat as operation done, maybe the machine is ready and we can continue

        return State.FINISHED

    def reset(self) -> None:
        """
        o oVirt, reset operation just shutdowns it until v3 support is removed
        """
        if self._vmid != '':
            self.service().stopMachine(self._vmid)

    def get_console_connection(
        self,
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
        return self.service().getConsoleConnection(self._vmid)

    def desktop_login(
        self,
        username: str,
        password: str,
        domain: str = '',  # pylint: disable=unused-argument
    ) -> None:
        script = f'''import sys
if sys.platform == 'win32':
    from uds import operations
    operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", struct.pack('!IsIs', 1, '{username}'.encode('utf8'), 2, '{password}'.encode('utf8')), True)
'''
        # Post script to service
        #         operations.writeToPipe("\\\\.\\pipe\\VDSMDPipe", packet, True)
        dbUserService = self.db_obj()
        if dbUserService:
            UserServiceManager().send_script(dbUserService, script)

    def process_ready_from_os_manager(self, data: typing.Any) -> str:
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for %s', self._name)
        if self._get_current_op() == Operation.WAIT:
            logger.debug('Machine is ready. Moving to level 2')
            self._pop_current_op()  # Remove current state
            return self._execute_queue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return State.FINISHED

    def deploy_for_user(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._init_queue_for_deploy(False)
        return self._execute_queue()

    def deploy_for_cache(self, cacheLevel: int) -> str:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deploy(cacheLevel == self.L2_CACHE)
        return self._execute_queue()

    def _init_queue_for_deploy(self, forLevel2: bool = False) -> None:
        if forLevel2 is False:
            self._queue = [Operation.CREATE, Operation.CHANGEMAC, Operation.START, Operation.FINISH]
        else:
            self._queue = [
                Operation.CREATE,
                Operation.CHANGEMAC,
                Operation.START,
                Operation.WAIT,
                Operation.SUSPEND,
                Operation.FINISH,
            ]

    def _check_machine_state(self, check_state: collections.abc.Iterable[str]) -> str:
        logger.debug(
            'Checking that state of machine %s (%s) is %s',
            self._vmid,
            self._name,
            check_state,
        )
        state = self.service().get_machine_state(self._vmid)

        # If we want to check an state and machine does not exists (except in case that we whant to check this)
        if state == 'unknown' and check_state != 'unknown':
            return self._error('Machine not found')

        ret = State.RUNNING
        if isinstance(check_state, (list, tuple)):
            for cks in check_state:
                if state == cks:
                    ret = State.FINISHED
                    break
        else:
            if state == check_state:
                ret = State.FINISHED

        return ret

    def _get_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue[0]

    def _pop_current_op(self) -> Operation:
        if not self._queue:
            return Operation.FINISH

        return self._queue.pop(0)

    def _push_front_op(self, op: Operation) -> None:
        self._queue.insert(0, op)

    def _error(self, reason: typing.Union[str, Exception]) -> str:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self.__error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid != '':  # Powers off
            OVirtDeferredRemoval.remove(self.service().provider(), self._vmid)

        self._queue = [Operation.ERROR]
        self._reason = reason
        return State.ERROR

    def _execute_queue(self) -> str:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.ERROR

        if op == Operation.FINISH:
            return State.FINISHED

        fncs: dict[Operation, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.START: self._start_machine,
            Operation.STOP: self._stop_machine,
            Operation.SUSPEND: self._suspend_machine,
            Operation.WAIT: self._wait,
            Operation.REMOVE: self._remove,
            Operation.CHANGEMAC: self._change_mac,
        }

        try:
            operation_runner: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if operation_runner is None:
                return self._error(f'Unknown operation found at execution queue ({op})')

            operation_runner()

            return State.RUNNING
        except Exception as e:
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> str:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return State.FINISHED

    def _wait(self) -> str:
        """
        Executes opWait, it simply waits something "external" to end
        """
        return State.RUNNING

    def _create(self) -> str:
        """
        Deploys a machine from template for user/cache
        """
        template_id = self.publication().get_template_id()
        name = self.get_name()
        if name == consts.NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = self.service().sanitized_name(
            name
        )  # oVirt don't let us to create machines with more than 15 chars!!!
        comments = 'UDS Linked clone'

        self._vmid = self.service().deploy_from_template(name, comments, template_id)
        if self._vmid is None:
            raise Exception('Can\'t create machine')

        return State.RUNNING

    def _remove(self) -> str:
        """
        Removes a machine from system
        """
        state = self.service().get_machine_state(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state != 'down':
            self._push_front_op(Operation.STOP)
            self._execute_queue()
        else:
            self.service().removeMachine(self._vmid)

        return State.RUNNING

    def _start_machine(self) -> str:
        """
        Powers on the machine
        """
        state = self.service().get_machine_state(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state in UP_STATES:  # Already started, return
            return State.RUNNING

        if state not in ('down', 'suspended'):
            self._push_front_op(
                Operation.RETRY
            )  # Will call "check Retry", that will finish inmediatly and again call this one
        self.service().startMachine(self._vmid)

        return State.RUNNING

    def _stop_machine(self) -> str:
        """
        Powers off the machine
        """
        state = self.service().get_machine_state(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state == 'down':  # Already stoped, return
            return State.RUNNING

        if state not in ('up', 'suspended'):
            self._push_front_op(
                Operation.RETRY
            )  # Will call "check Retry", that will finish inmediatly and again call this one
        else:
            self.service().stopMachine(self._vmid)

        return State.RUNNING

    def _suspend_machine(self) -> str:
        """
        Suspends the machine
        """
        state = self.service().get_machine_state(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state == 'suspended':  # Already suspended, return
            return State.RUNNING

        if state != 'up':
            self._push_front_op(
                Operation.RETRY
            )  # Remember here, the return State.FINISH will make this retry be "poped" right ar return
        else:
            self.service().suspend_machine(self._vmid)

        return State.RUNNING

    def _change_mac(self) -> str:
        """
        Changes the mac of the first nic
        """
        self.service().updateMachineMac(self._vmid, self.get_unique_id())
        # Fix usb if needed
        self.service().fixUsb(self._vmid)

        return State.RUNNING

    # Check methods
    def _create_checker(self) -> str:
        """
        Checks the state of a deploy for an user or cache
        """
        return self._check_machine_state('down')

    def _start_checker(self) -> str:
        """
        Checks if machine has started
        """
        return self._check_machine_state(UP_STATES)

    def _stop_checker(self) -> str:
        """
        Checks if machine has stoped
        """
        return self._check_machine_state('down')

    def _suspend_checker(self) -> str:
        """
        Check if the machine has suspended
        """
        return self._check_machine_state('suspended')

    def _remove_checker(self) -> str:
        """
        Checks if a machine has been removed
        """
        return self._check_machine_state('unknown')

    def _mac_checker(self) -> str:
        """
        Checks if change mac operation has finished.

        Changing nic configuration es 1-step operation, so when we check it here, it is already done
        """
        return State.FINISHED

    def check_state(self) -> str:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return State.ERROR

        if op == Operation.FINISH:
            return State.FINISHED

        fncs: dict[Operation, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create_checker,
            Operation.RETRY: self._retry,
            Operation.WAIT: self._wait,
            Operation.START: self._start_checker,
            Operation.STOP: self._stop_checker,
            Operation.SUSPEND: self._suspend_checker,
            Operation.REMOVE: self._remove_checker,
            Operation.CHANGEMAC: self._mac_checker,
        }

        try:
            operation_checker: typing.Optional[typing.Optional[collections.abc.Callable[[], str]]] = fncs.get(op, None)

            if operation_checker is None:
                return self._error(f'Unknown operation found at check queue ({op})')

            state = operation_checker()
            if state == State.FINISHED:
                self._pop_current_op()  # Remove runing op
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)

    def move_to_cache(self, newLevel: int) -> str:
        """
        Moves machines between cache levels
        """
        if Operation.REMOVE in self._queue:
            return State.RUNNING

        if newLevel == self.L1_CACHE:
            self._queue = [Operation.START, Operation.FINISH]
        else:
            self._queue = [Operation.START, Operation.SUSPEND, Operation.FINISH]

        return self._execute_queue()

    def error_reason(self) -> str:
        """
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).
        """
        return self._reason

    def destroy(self) -> str:
        """
        Invoked for destroying a deployed service
        """
        self._debug('destroy')
        if self._vmid == '':
            self._queue = []
            self._reason = "canceled"
            return State.FINISHED

        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self._get_current_op()

        if op == Operation.ERROR:
            return self._error('Machine is already in error state!')

        if op in (Operation.FINISH, Operation.WAIT):
            self._queue = [Operation.STOP, Operation.REMOVE, Operation.FINISH]
            return self._execute_queue()

        self._queue = [op, Operation.STOP, Operation.REMOVE, Operation.FINISH]
        # Do not execute anything.here, just continue normally
        return State.RUNNING

    def cancel(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.
        """
        return self.destroy()

    @staticmethod
    def _op2str(op: Operation) -> str:
        return {
            Operation.CREATE: 'create',
            Operation.START: 'start',
            Operation.STOP: 'stop',
            Operation.SUSPEND: 'suspend',
            Operation.REMOVE: 'remove',
            Operation.WAIT: 'wait',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
            Operation.CHANGEMAC: 'changing mac',
        }.get(op, '????')

    def _debug(self, txt: str) -> None:
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [OVirtLinkedDeployment._op2str(op) for op in self._queue],
        )
