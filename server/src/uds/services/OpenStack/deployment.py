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
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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
import pickle  # nosec: not insecure, we are loading our own data
import logging
import typing
import collections.abc

from uds.core import services
from uds.core.types.states import State
from uds.core.util import log

from . import openstack

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import LiveService
    from .publication import LivePublication


logger = logging.getLogger(__name__)

opCreate, opStart, opSuspend, opRemove, opWait, opError, opFinish, opRetry = range(8)

NO_MORE_NAMES = 'NO-NAME-ERROR'


class LiveDeployment(services.UserService):  # pylint: disable=too-many-public-methods
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.
    """

    _name: str = ''
    _ip: str = ''
    _mac: str = ''
    _vmid: str = ''
    _reason: str = ''
    _queue: list[int] = []

    # : Recheck every this seconds by default (for task methods)
    suggested_delay = 5

    def initialize(self) -> None:
        self._name = ''
        self._ip = ''
        self._mac = ''
        self._vmid = ''
        self._reason = ''
        self._queue = []

    # For typing check only...
    def service(self) -> 'LiveService':
        return typing.cast('LiveService', super().service())

    # For typing check only...
    def publication(self) -> 'LivePublication':
        return typing.cast('LivePublication', super().publication())

    # Serializable needed methods
    def marshal(self) -> bytes:
        return b'\1'.join(
            [
                b'v1',
                self._name.encode('utf8'),
                self._ip.encode('utf8'),
                self._mac.encode('utf8'),
                self._vmid.encode('utf8'),
                self._reason.encode('utf8'),
                pickle.dumps(self._queue, protocol=0),
            ]
        )

    def unmarshal(self, data: bytes) -> None:
        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._vmid = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._queue = pickle.loads(vals[6])  # nosec: not insecure, we are loading our own data

    def get_name(self) -> str:
        if self._name == '':
            try:
                self._name = self.name_generator().get(
                    self.service().get_basename(), self.service().getLenName()
                )
            except KeyError:
                return NO_MORE_NAMES
        return self._name

    def set_ip(self, ip) -> None:
        self._ip = ip

    def get_unique_id(self) -> str:
        return self._mac

    def get_ip(self) -> str:
        return self._ip

    def set_ready(self) -> str:
        """
        The method is invoked whenever a machine is provided to an user, right
        before presenting it (via transport rendering) to the user.
        """
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            status = self.service().getMachineState(self._vmid)

            if openstack.statusIsLost(status):
                return self.__error('Machine is not available anymore')

            if status == openstack.PAUSED:
                self.service().resumeMachine(self._vmid)
            elif status in (openstack.STOPPED, openstack.SHUTOFF):
                self.service().startMachine(self._vmid)

            # Right now, we suppose the machine is ready

            self.cache.put('ready', '1')
        except Exception as e:
            self.do_log(log.LogLevel.ERROR, 'Error on setReady: {}'.format(e))
            # Treat as operation done, maybe the machine is ready and we can continue

        return State.FINISHED

    def reset(self) -> None:
        if self._vmid != '':
            self.service().resetMachine(self._vmid)

    def process_ready_from_os_manager(self, data: typing.Any) -> str:
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for %s', self._name)
        if self.__getCurrentOp() == opWait:
            logger.debug('Machine is ready. Moving to level 2')
            self.__popCurrentOp()  # Remove current state
            return self.__executeQueue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return State.FINISHED

    def deploy_for_user(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self.__initQueueForDeploy(False)
        return self.__executeQueue()

    def deploy_for_cache(self, cacheLevel: int) -> str:
        """
        Deploys an service instance for cache
        """
        self.__initQueueForDeploy(cacheLevel == self.L2_CACHE)
        return self.__executeQueue()

    def __initQueueForDeploy(self, forLevel2: bool = False) -> None:
        if forLevel2 is False:
            self._queue = [opCreate, opFinish]
        else:
            self._queue = [opCreate, opWait, opSuspend, opFinish]

    def __checkMachineState(self, chkState: str) -> str:
        logger.debug(
            'Checking that state of machine %s (%s) is %s',
            self._vmid,
            self._name,
            chkState,
        )
        status = self.service().getMachineState(self._vmid)

        # If we want to check an state and machine does not exists (except in case that we whant to check this)
        if openstack.statusIsLost(status):
            return self.__error('Machine not available. ({})'.format(status))

        ret = State.RUNNING
        chkStates = [chkState] if not isinstance(chkState, (list, tuple)) else chkState
        if status in chkStates:
            ret = State.FINISHED

        return ret

    def __getCurrentOp(self) -> int:
        if not self._queue:
            return opFinish

        return self._queue[0]

    def __popCurrentOp(self) -> int:
        if not self._queue:
            return opFinish

        res = self._queue.pop(0)
        return res

    def __pushFrontOp(self, op: int) -> None:
        self._queue.insert(0, op)

    def __pushBackOp(self, op: int) -> None:
        self._queue.append(op)

    def __error(self, reason: typing.Any) -> str:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self.__error(reason)"
        """
        logger.debug('Setting error state, reason: %s', reason)
        self._queue = [opError]
        self._reason = str(reason)

        self.do_log(log.LogLevel.ERROR, self._reason)

        if self._vmid:  # Powers off & delete it
            try:
                self.service().removeMachine(self._vmid)
            except Exception:
                logger.warning('Can\t set machine %s state to stopped', self._vmid)

        return State.ERROR

    def __executeQueue(self) -> str:
        self.__debug('executeQueue')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs: dict[int, collections.abc.Callable[[], str]] = {
            opCreate: self.__create,
            opRetry: self.__retry,
            opStart: self.__startMachine,
            opSuspend: self.__suspendMachine,
            opWait: self.__wait,
            opRemove: self.__remove,
        }

        try:
            if op not in fncs:
                return self.__error(
                    'Unknown operation found at execution queue ({0})'.format(op)
                )

            fncs[op]()

            return State.RUNNING
        except Exception as e:
            return self.__error(e)

    # Queue execution methods
    def __retry(self) -> str:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return State.FINISHED

    def __wait(self) -> str:
        """
        Executes opWait, it simply waits something "external" to end
        """
        return State.RUNNING

    def __create(self) -> str:
        """
        Deploys a machine from template for user/cache
        """
        templateId = self.publication().getTemplateId()
        name = self.get_name()
        if name == NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = self.service().sanitizeVmName(
            name
        )  # OpenNebula don't let us to create machines with more than 15 chars!!!

        self._vmid = self.service().deployFromTemplate(name, templateId)
        if self._vmid is None:
            raise Exception('Can\'t create machine')

        return State.RUNNING

    def __remove(self) -> str:
        """
        Removes a machine from system
        """
        status = self.service().getMachineState(self._vmid)

        if openstack.statusIsLost(status):
            raise Exception('Machine not found. (Status {})'.format(status))

        self.service().removeMachine(self._vmid)

        return State.RUNNING

    def __startMachine(self) -> str:
        """
        Powers on the machine
        """
        self.service().startMachine(self._vmid)

        return State.RUNNING

    def __suspendMachine(self) -> str:
        """
        Suspends the machine
        """
        self.service().suspendMachine(self._vmid)

        return State.RUNNING

    # Check methods
    def __checkCreate(self) -> str:
        """
        Checks the state of a deploy for an user or cache
        """
        ret = self.__checkMachineState(openstack.ACTIVE)
        if ret == State.FINISHED:
            # Get IP & MAC (early stage)
            self._mac, self._ip = self.service().getNetInfo(self._vmid)

        return ret

    def __checkStart(self) -> str:
        """
        Checks if machine has started
        """
        return self.__checkMachineState(openstack.ACTIVE)

    def __checkSuspend(self) -> str:
        """
        Check if the machine has suspended
        """
        return self.__checkMachineState(openstack.SUSPENDED)

    def __checkRemoved(self) -> str:
        """
        Checks if a machine has been removed
        """
        return State.FINISHED  # No check at all, always true

    def check_state(self) -> str:
        """
        Check what operation is going on, and acts acordly to it
        """
        self.__debug('check_state')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs: dict[int, collections.abc.Callable[[], str]] = {
            opCreate: self.__checkCreate,
            opRetry: self.__retry,
            opWait: self.__wait,
            opStart: self.__checkStart,
            opSuspend: self.__checkSuspend,
            opRemove: self.__checkRemoved,
        }

        try:
            if op not in fncs:
                return self.__error(
                    'Unknown operation found at execution queue ({0})'.format(op)
                )

            state = fncs[op]()
            if state == State.FINISHED:
                self.__popCurrentOp()  # Remove runing op
                return self.__executeQueue()

            return state
        except Exception as e:
            return self.__error(e)

    def move_to_cache(self, newLevel: int) -> str:
        """
        Moves machines between cache levels
        """
        if opRemove in self._queue:
            return State.RUNNING

        if newLevel == self.L1_CACHE:
            self._queue = [opStart, opFinish]
        else:
            self._queue = [opStart, opSuspend, opFinish]

        return self.__executeQueue()

    def error_reason(self) -> str:
        return self._reason

    def destroy(self) -> str:
        """
        Invoked for destroying a deployed service
        """
        self.__debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self.__getCurrentOp()

        if op == opError:
            return self.__error('Machine is already in error state!')

        if op == opFinish or op == opWait:
            self._queue = [opRemove, opFinish]
            return self.__executeQueue()

        self._queue = [op, opRemove, opFinish]
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
    def __op2str(op):
        return {
            opCreate: 'create',
            opStart: 'start',
            opSuspend: 'suspend',
            opRemove: 'remove',
            opWait: 'wait',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
        }.get(op, '????')

    def __debug(self, txt: str) -> None:
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [LiveDeployment.__op2str(op) for op in self._queue],
        )
