# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import pickle
import logging
import typing

from uds.core.services import UserDeployment
from uds.core.util.state import State
from uds.core.util import log

from .xen_client import XenPowerState

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import XenLinkedService
    from .publication import XenPublication
    from uds.core.util.storage import Storage

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
    opConfigure,
    opProvision,
    opWaitSuspend,
) = range(12)

NO_MORE_NAMES = 'NO-NAME-ERROR'


class XenLinkedDeployment(UserDeployment):
    # : Recheck every six seconds by default (for task methods)
    suggestedTime = 7

    _name: str = ''
    _ip: str = ''
    _mac: str = ''
    _man: str = ''
    _vmid: str = ''
    _reason: str = ''
    _task = ''
    _queue: typing.List[int]

    def initialize(self) -> None:
        self._queue = []

    def service(self) -> 'XenLinkedService':
        return typing.cast('XenLinkedService', super().service())

    def publication(self) -> 'XenPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('XenPublication', pub)

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
                self._task.encode('utf8'),
            ]
        )

    def unmarshal(self, data: bytes) -> None:
        vals = data.split(b'\1')
        logger.debug('Values: %s', vals)
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._vmid = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._queue = pickle.loads(vals[6])
            self._task = vals[7].decode('utf8')

    def getName(self) -> str:
        if not self._name:
            try:
                self._name = self.nameGenerator().get(
                    self.service().getBaseName(), self.service().getLenName()
                )
            except KeyError:
                return NO_MORE_NAMES
        return self._name

    def setIp(self, ip: str) -> None:
        logger.debug('Setting IP to %s', ip)
        self._ip = ip

    def getUniqueId(self) -> str:
        if not self._mac:
            self._mac = self.macGenerator().get(self.service().getMacRange())
        return self._mac

    def getIp(self) -> str:
        return self._ip

    def setReady(self) -> str:
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            state = self.service().getVMPowerState(self._vmid)

            if state != XenPowerState.running:
                self._queue = [opStart, opFinish]
                return self.__executeQueue()

            self.cache.put('ready', '1', 30)                
        except Exception as e:
            # On case of exception, log an an error and return as if the operation was executed
            self.doLog(log.ERROR, 'Error setting machine state: {}'.format(e))
            # return self.__error('Machine is not available anymore')

        return State.FINISHED

    def reset(self) -> None:
        if self._vmid:
            self.service().resetVM(self._vmid)  # Reset in sync

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
            self._queue = [opCreate, opConfigure, opProvision, opStart, opFinish]
        else:
            self._queue = [
                opCreate,
                opConfigure,
                opProvision,
                opStart,
                opWait,
                opWaitSuspend,
                opSuspend,
                opFinish,
            ]

    def __getCurrentOp(self) -> int:
        if len(self._queue) == 0:
            return opFinish

        return self._queue[0]

    def __popCurrentOp(self) -> int:
        if len(self._queue) == 0:
            return opFinish

        res = self._queue.pop(0)
        return res

    def __pushFrontOp(self, op: int) -> None:
        self._queue.insert(0, op)

    def __pushBackOp(self, op: int) -> None:
        self._queue.append(op)

    def __error(self, reason: typing.Any) -> str:
        logger.debug('Setting error state, reason: %s', reason)
        self.doLog(log.ERROR, reason)

        if self._vmid != '':  # Powers off and delete VM
            try:
                state = self.service().getVMPowerState(self._vmid)
                if state in (
                    XenPowerState.running,
                    XenPowerState.paused,
                    XenPowerState.suspended,
                ):
                    self.service().stopVM(self._vmid, False)  # In sync mode
                self.service().removeVM(self._vmid)
            except Exception:
                logger.debug('Can\'t set machine %s state to stopped', self._vmid)

        self._queue = [opError]
        self._reason = str(reason)
        return State.ERROR

    def __executeQueue(self) -> str:
        self.__debug('executeQueue')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs: typing.Dict[int, typing.Optional[typing.Callable[[], str]]] = {
            opCreate: self.__create,
            opRetry: self.__retry,
            opStart: self.__startMachine,
            opStop: self.__stopMachine,
            opWaitSuspend: self.__waitSuspend,
            opSuspend: self.__suspendMachine,
            opWait: self.__wait,
            opRemove: self.__remove,
            opConfigure: self.__configure,
            opProvision: self.__provision,
        }

        try:
            execFnc: typing.Optional[typing.Callable[[], str]] = fncs.get(op, None)

            if execFnc is None:
                return self.__error(
                    'Unknown operation found at execution queue ({0})'.format(op)
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

        name = 'UDS service ' + self.service().sanitizeVmName(
            name
        )  # oVirt don't let us to create machines with more than 15 chars!!!
        comments = 'UDS Linked clone'

        self._task = self.service().startDeployFromTemplate(name, comments, templateId)
        if self._task is None:
            raise Exception('Can\'t create machine')

        return State.RUNNING

    def __remove(self) -> str:
        """
        Removes a machine from system
        """
        state = self.service().getVMPowerState(self._vmid)

        if state not in (XenPowerState.halted, XenPowerState.suspended):
            self.__pushFrontOp(opStop)
            self.__executeQueue()
        else:
            self.service().removeVM(self._vmid)

        return State.RUNNING

    def __startMachine(self) -> str:
        """
        Powers on the machine
        """
        task = self.service().startVM(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return State.RUNNING

    def __stopMachine(self) -> str:
        """
        Powers off the machine
        """
        task = self.service().stopVM(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return State.RUNNING

    def __waitSuspend(self) -> str:
        """
        Before suspending, wait for machine to have the SUSPEND feature
        """
        self._task = ''
        return State.RUNNING

    def __suspendMachine(self) -> str:
        """
        Suspends the machine
        """
        task = self.service().suspendVM(self._vmid)

        if task is not None:
            self._task = task
        else:
            self._task = ''

        return State.RUNNING

    def __configure(self):
        """
        Provisions machine & changes the mac of the indicated nic
        """
        self.service().configureVM(self._vmid, self.getUniqueId())

        return State.RUNNING

    def __provision(self):
        """
        Makes machine usable on Xen
        """
        self.service().provisionVM(
            self._vmid, False
        )  # Let's try this in "sync" mode, this must be fast enough

        return State.RUNNING

    # Check methods
    def __checkCreate(self):
        """
        Checks the state of a deploy for an user or cache
        """
        state = self.service().checkTaskFinished(self._task)
        if state[0]:  # Finished
            self._vmid = state[1]
            return State.FINISHED

        return State.RUNNING

    def __checkStart(self):
        """
        Checks if machine has started
        """
        if self.service().checkTaskFinished(self._task)[0]:
            return State.FINISHED
        return State.RUNNING

    def __checkStop(self):
        """
        Checks if machine has stoped
        """
        if self.service().checkTaskFinished(self._task)[0]:
            return State.FINISHED
        return State.RUNNING

    def __checkWaitSuspend(self):
        if self.service().canSuspendVM(self._vmid) is True:
            return State.FINISHED

        return State.RUNNING

    def __checkSuspend(self):
        """
        Check if the machine has suspended
        """
        if self.service().checkTaskFinished(self._task)[0]:
            return State.FINISHED
        return State.RUNNING

    def __checkRemoved(self):
        """
        Checks if a machine has been removed
        """
        return State.FINISHED

    def __checkConfigure(self):
        """
        Checks if change mac operation has finished.

        Changing nic configuration es 1-step operation, so when we check it here, it is already done
        """
        return State.FINISHED

    def __checkProvision(self):
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

        fncs: typing.Dict[int, typing.Optional[typing.Callable[[], str]]] = {
            opCreate: self.__checkCreate,
            opRetry: self.__retry,
            opWait: self.__wait,
            opStart: self.__checkStart,
            opStop: self.__checkStop,
            opWaitSuspend: self.__checkWaitSuspend,
            opSuspend: self.__checkSuspend,
            opRemove: self.__checkRemoved,
            opConfigure: self.__checkConfigure,
            opProvision: self.__checkProvision,
        }

        try:
            chkFnc: typing.Optional[typing.Callable[[], str]] = fncs.get(op, None)

            if chkFnc is None:
                return self.__error(
                    'Unknown operation found at check queue ({})'.format(op)
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
        return self._reason

    def destroy(self) -> str:
        self.__debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self.__getCurrentOp()

        if op == opError:
            return State.FINISHED

        if op == opFinish or op == opWait:
            self._queue = [opStop, opRemove, opFinish]
            return self.__executeQueue()

        self._queue = [op, opStop, opRemove, opFinish]
        # Do not execute anything.here, just continue normally
        return State.RUNNING

    def cancel(self) -> str:
        return self.destroy()

    @staticmethod
    def __op2str(op) -> str:
        return {
            opCreate: 'create',
            opStart: 'start',
            opStop: 'stop',
            opWaitSuspend: 'wait-suspend',
            opSuspend: 'suspend',
            opRemove: 'remove',
            opWait: 'wait',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
            opConfigure: 'configuring',
            opProvision: 'provisioning',
        }.get(op, '????')

    def __debug(self, txt: str) -> None:
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [XenLinkedDeployment.__op2str(op) for op in self._queue],
        )
