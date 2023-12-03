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
import pickle  # nosec: not insecure, we are loading our own data
import logging
import typing
import collections.abc

from uds.core import services
from uds.core.managers.user_service import UserServiceManager
from uds.core.util.state import State
from uds.core.util import log

from .jobs import OVirtDeferredRemoval

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import OVirtLinkedService
    from .publication import OVirtPublication

logger = logging.getLogger(__name__)

(
    opCreate,
    opStart,
    opStop,
    opSuspend,
    opRemove,
    opWait,
    opError,
    opFinish,
    opRetry,
    opChangeMac,
) = range(10)

NO_MORE_NAMES = 'NO-NAME-ERROR'
UP_STATES = ('up', 'reboot_in_progress', 'powering_up', 'restoring_state')


class OVirtLinkedDeployment(services.UserService):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.

    """

    # : Recheck every six seconds by default (for task methods)
    suggestedTime = 6

    # own vars
    _name: str
    _ip: str
    _mac: str
    _vmid: str
    _reason: str
    _queue: list[int]

    # Utility overrides for type checking...
    def service(self) -> 'OVirtLinkedService':
        return typing.cast('OVirtLinkedService', super().service())

    def publication(self) -> 'OVirtPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OVirtPublication', pub)

    def initialize(self):
        self._name = ''
        self._ip = ''
        self._mac = ''
        self._vmid = ''
        self._reason = ''
        self._queue = []

    # Serializable needed methods
    def marshal(self) -> bytes:
        """
        Does nothing right here, we will use environment storage in this sample
        """
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
        """
        Does nothing here also, all data are keeped at environment storage
        """
        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._vmid = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._queue = pickle.loads(
                vals[6]
            )  # nosec: not insecure, we are loading our own data

    def getName(self) -> str:
        if self._name == '':
            try:
                self._name = self.nameGenerator().get(
                    self.service().getBaseName(), self.service().getLenName()
                )
            except KeyError:
                return NO_MORE_NAMES
        return self._name

    def setIp(self, ip: str) -> None:
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

    def getUniqueId(self) -> str:
        """
        Return and unique identifier for this service.
        In our case, we will generate a mac name, that can be also as sample
        of 'mac' generator use, and probably will get used something like this
        at some services.

        The get method of a mac generator takes one param, that is the mac range
        to use to get an unused mac.
        """
        if self._mac == '':
            self._mac = self.macGenerator().get(self.service().getMacRange())
        return self._mac

    def getIp(self) -> str:
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

    def setReady(self) -> str:
        """
        The method is invoked whenever a machine is provided to an user, right
        before presenting it (via transport rendering) to the user.
        """
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            state = self.service().getMachineState(self._vmid)

            if state == 'unknown':
                return self.__error('Machine is not available anymore')

            if state not in UP_STATES:
                self._queue = [opStart, opFinish]
                return self.__executeQueue()

            self.cache.put('ready', '1')
        except Exception as e:
            self.doLog(log.LogLevel.ERROR, f'Error on setReady: {e}')
            # Treat as operation done, maybe the machine is ready and we can continue

        return State.FINISHED

    def reset(self) -> None:
        """
        o oVirt, reset operation just shutdowns it until v3 support is removed
        """
        if self._vmid != '':
            self.service().stopMachine(self._vmid)

    def getConsoleConnection(
        self,
    ) -> typing.Optional[typing.MutableMapping[str, typing.Any]]:
        return self.service().getConsoleConnection(self._vmid)

    def desktopLogin(
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
        dbUserService = self.dbObj()
        if dbUserService:
            UserServiceManager().sendScript(dbUserService, script)

    def notifyReadyFromOsManager(self, data: typing.Any) -> str:
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for %s', self._name)
        if self.__getCurrentOp() == opWait:
            logger.debug('Machine is ready. Moving to level 2')
            self.__popCurrentOp()  # Remove current state
            return self.__executeQueue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return State.FINISHED

    def deployForUser(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self.__initQueueForDeploy(False)
        return self.__executeQueue()

    def deployForCache(self, cacheLevel: int) -> str:
        """
        Deploys an service instance for cache
        """
        self.__initQueueForDeploy(cacheLevel == self.L2_CACHE)
        return self.__executeQueue()

    def __initQueueForDeploy(self, forLevel2: bool = False) -> None:
        if forLevel2 is False:
            self._queue = [opCreate, opChangeMac, opStart, opFinish]
        else:
            self._queue = [opCreate, opChangeMac, opStart, opWait, opSuspend, opFinish]

    def __checkMachineState(
        self, chkState: typing.Union[list[str], typing.Tuple[str, ...], str]
    ) -> str:
        logger.debug(
            'Checking that state of machine %s (%s) is %s',
            self._vmid,
            self._name,
            chkState,
        )
        state = self.service().getMachineState(self._vmid)

        # If we want to check an state and machine does not exists (except in case that we whant to check this)
        if state == 'unknown' and chkState != 'unknown':
            return self.__error('Machine not found')

        ret = State.RUNNING
        if isinstance(chkState, (list, tuple)):
            for cks in chkState:
                if state == cks:
                    ret = State.FINISHED
                    break
        else:
            if state == chkState:
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

    def __pushFrontOp(self, op: int):
        self._queue.insert(0, op)

    def __error(self, reason: typing.Union[str, Exception]) -> str:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self.__error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.doLog(log.LogLevel.ERROR, reason)

        if self._vmid != '':  # Powers off
            OVirtDeferredRemoval.remove(self.service().parent(), self._vmid)

        self._queue = [opError]
        self._reason = reason
        return State.ERROR

    def __executeQueue(self) -> str:
        self.__debug('executeQueue')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs: dict[int, typing.Optional[collections.abc.Callable[[], str]]] = {
            opCreate: self.__create,
            opRetry: self.__retry,
            opStart: self.__startMachine,
            opStop: self.__stopMachine,
            opSuspend: self.__suspendMachine,
            opWait: self.__wait,
            opRemove: self.__remove,
            opChangeMac: self.__changeMac,
        }

        try:
            execFnc: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op, None)

            if execFnc is None:
                return self.__error(
                    f'Unknown operation found at execution queue ({op})'
                )

            execFnc()

            return State.RUNNING
        except Exception as e:
            return self.__error(e)

    # Queue execution methods
    def __retry(self) -> str:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        checkState method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at checkState
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
        name = self.getName()
        if name == NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        name = self.service().sanitizeVmName(
            name
        )  # oVirt don't let us to create machines with more than 15 chars!!!
        comments = 'UDS Linked clone'

        self._vmid = self.service().deployFromTemplate(name, comments, templateId)
        if self._vmid is None:
            raise Exception('Can\'t create machine')

        return State.RUNNING

    def __remove(self) -> str:
        """
        Removes a machine from system
        """
        state = self.service().getMachineState(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state != 'down':
            self.__pushFrontOp(opStop)
            self.__executeQueue()
        else:
            self.service().removeMachine(self._vmid)

        return State.RUNNING

    def __startMachine(self) -> str:
        """
        Powers on the machine
        """
        state = self.service().getMachineState(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state in UP_STATES:  # Already started, return
            return State.RUNNING

        if state not in ('down', 'suspended'):
            self.__pushFrontOp(
                opRetry
            )  # Will call "check Retry", that will finish inmediatly and again call this one
        self.service().startMachine(self._vmid)

        return State.RUNNING

    def __stopMachine(self) -> str:
        """
        Powers off the machine
        """
        state = self.service().getMachineState(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state == 'down':  # Already stoped, return
            return State.RUNNING

        if state not in ('up', 'suspended'):
            self.__pushFrontOp(
                opRetry
            )  # Will call "check Retry", that will finish inmediatly and again call this one
        else:
            self.service().stopMachine(self._vmid)

        return State.RUNNING

    def __suspendMachine(self) -> str:
        """
        Suspends the machine
        """
        state = self.service().getMachineState(self._vmid)

        if state == 'unknown':
            raise Exception('Machine not found')

        if state == 'suspended':  # Already suspended, return
            return State.RUNNING

        if state != 'up':
            self.__pushFrontOp(
                opRetry
            )  # Remember here, the return State.FINISH will make this retry be "poped" right ar return
        else:
            self.service().suspendMachine(self._vmid)

        return State.RUNNING

    def __changeMac(self) -> str:
        """
        Changes the mac of the first nic
        """
        self.service().updateMachineMac(self._vmid, self.getUniqueId())
        # Fix usb if needed
        self.service().fixUsb(self._vmid)

        return State.RUNNING

    # Check methods
    def __checkCreate(self) -> str:
        """
        Checks the state of a deploy for an user or cache
        """
        return self.__checkMachineState('down')

    def __checkStart(self) -> str:
        """
        Checks if machine has started
        """
        return self.__checkMachineState(UP_STATES)

    def __checkStop(self) -> str:
        """
        Checks if machine has stoped
        """
        return self.__checkMachineState('down')

    def __checkSuspend(self) -> str:
        """
        Check if the machine has suspended
        """
        return self.__checkMachineState('suspended')

    def __checkRemoved(self) -> str:
        """
        Checks if a machine has been removed
        """
        return self.__checkMachineState('unknown')

    def __checkMac(self) -> str:
        """
        Checks if change mac operation has finished.

        Changing nic configuration es 1-step operation, so when we check it here, it is already done
        """
        return State.FINISHED

    def checkState(self) -> str:
        """
        Check what operation is going on, and acts acordly to it
        """
        self.__debug('checkState')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs = {
            opCreate: self.__checkCreate,
            opRetry: self.__retry,
            opWait: self.__wait,
            opStart: self.__checkStart,
            opStop: self.__checkStop,
            opSuspend: self.__checkSuspend,
            opRemove: self.__checkRemoved,
            opChangeMac: self.__checkMac,
        }

        try:
            chkFnc: typing.Optional[
                typing.Optional[collections.abc.Callable[[], str]]
            ] = fncs.get(op, None)

            if chkFnc is None:
                return self.__error(
                    f'Unknown operation found at check queue ({op})'
                )

            state = chkFnc()
            if state == State.FINISHED:
                self.__popCurrentOp()  # Remove runing op
                return self.__executeQueue()

            return state
        except Exception as e:
            return self.__error(e)

    def moveToCache(self, newLevel: int) -> str:
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

    def reasonOfError(self) -> str:
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
        self.__debug('destroy')
        if self._vmid == '':
            self._queue = []
            self._reason = "canceled"
            return State.FINISHED

        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self.__getCurrentOp()

        if op == opError:
            return self.__error('Machine is already in error state!')

        if op in (opFinish, opWait):
            self._queue = [opStop, opRemove, opFinish]
            return self.__executeQueue()

        self._queue = [op, opStop, opRemove, opFinish]
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
    def __op2str(op: int) -> str:
        return {
            opCreate: 'create',
            opStart: 'start',
            opStop: 'stop',
            opSuspend: 'suspend',
            opRemove: 'remove',
            opWait: 'wait',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
            opChangeMac: 'changing mac',
        }.get(op, '????')

    def __debug(self, txt):
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [OVirtLinkedDeployment.__op2str(op) for op in self._queue],
        )
