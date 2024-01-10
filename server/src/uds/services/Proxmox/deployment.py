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
import pickle  # nosec: controled data
import logging
import typing
import collections.abc

from uds.core import services
from uds.core.managers.user_service import UserServiceManager
from uds.core.util.state import State
from uds.core.util import log
from uds.core.util.model import sql_stamp_seconds

from .jobs import ProxmoxDeferredRemoval
from . import client


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import ProxmoxLinkedService
    from .publication import ProxmoxPublication

logger = logging.getLogger(__name__)

(
    opCreate,
    opStart,
    opStop,
    opShutdown,
    opRemove,
    opWait,
    opError,
    opFinish,
    opRetry,
    opGetMac,
    opGracelyStop,
) = range(11)

NO_MORE_NAMES = 'NO-NAME-ERROR'
UP_STATES = ('up', 'reboot_in_progress', 'powering_up', 'restoring_state')
GUEST_SHUTDOWN_WAIT = 90  # Seconds


class ProxmoxDeployment(services.UserService):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing Proxmox deployments (user machines in this case) is here.

    """

    # : Recheck every this seconds by default (for task methods)
    suggested_delay = 12

    # own vars
    _name: str
    _ip: str
    _mac: str
    _task: str
    _vmid: str
    _reason: str
    _queue: list[int]

    # Utility overrides for type checking...
    def service(self) -> 'ProxmoxLinkedService':
        return typing.cast('ProxmoxLinkedService', super().service())

    def publication(self) -> 'ProxmoxPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('ProxmoxPublication', pub)

    def initialize(self):
        self._name = ''
        self._ip = ''
        self._mac = ''
        self._task = ''
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
                self._task.encode('utf8'),
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
            self._task = vals[4].decode('utf8')
            self._vmid = vals[5].decode('utf8')
            self._reason = vals[6].decode('utf8')
            self._queue = pickle.loads(vals[7])  # nosec: controled data

    def get_name(self) -> str:
        if self._name == '':
            try:
                self._name = self.name_generator().get(
                    self.service().get_base_name(), self.service().getLenName()
                )
            except KeyError:
                return NO_MORE_NAMES
        return self._name

    def set_ip(self, ip: str) -> None:
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
        return self._ip

    def set_ready(self) -> str:
        if self.cache.get('ready') == '1':
            return State.FINISHED

        try:
            vmInfo = self.service().getMachineInfo(int(self._vmid))
        except client.ProxmoxConnectionError:
            raise  # If connection fails, let it fail on parent
        except Exception as e:
            return self.__error(f'Machine not found: {e}')

        if vmInfo.status == 'stopped':
            self._queue = [opStart, opFinish]
            return self.__executeQueue()

        self.cache.put('ready', '1')
        return State.FINISHED

    def reset(self) -> None:
        """
        o Proxmox, reset operation just shutdowns it until v3 support is removed
        """
        if self._vmid != '':
            try:
                self.service().resetMachine(int(self._vmid))
            except Exception:  # nosec: if cannot reset, ignore it
                pass  # If could not reset, ignore it...

    def get_console_connection(
        self,
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
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
        dbService = self.db_obj()
        if dbService:
            try:
                UserServiceManager().send_script(dbService, script)
            except Exception as e:
                logger.info('Exception sending loggin to %s: %s', dbService, e)

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
            self._queue = [opCreate, opGetMac, opStart, opFinish]
        else:
            self._queue = [opCreate, opGetMac, opStart, opWait, opShutdown, opFinish]

    def __setTask(self, upid: 'client.types.UPID'):
        self._task = ','.join([upid.node, upid.upid])

    def __getTask(self) -> tuple[str, str]:
        vals = self._task.split(',')
        return (vals[0], vals[1])

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

    def __retryLater(self) -> str:
        self.__pushFrontOp(opRetry)
        return State.RUNNING

    def __error(self, reason: typing.Union[str, Exception]) -> str:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self.__error(reason)"
        """
        reason = str(reason)
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._vmid != '':  # Powers off
            ProxmoxDeferredRemoval.remove(self.service().parent(), int(self._vmid))

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

        fncs: collections.abc.Mapping[int, typing.Optional[collections.abc.Callable[[], str]]] = {
            opCreate: self.__create,
            opRetry: self.__retry,
            opStart: self.__startMachine,
            opStop: self.__stopMachine,
            opGracelyStop: self.__gracelyStop,
            opShutdown: self.__shutdownMachine,
            opWait: self.__wait,
            opRemove: self.__remove,
            opGetMac: self.__updateVmMacAndHA,
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
        templateId = self.publication().machine()
        name = self.get_name()
        if name == NO_MORE_NAMES:
            raise Exception(
                'No more names available for this service. (Increase digits for this service to fix)'
            )

        comments = 'UDS Linked clone'

        taskResult = self.service().cloneMachine(name, comments, templateId)

        self.__setTask(taskResult.upid)

        self._vmid = str(taskResult.vmid)

        return State.RUNNING

    def __remove(self) -> str:
        """
        Removes a machine from system
        """
        try:
            vmInfo = self.service().getMachineInfo(int(self._vmid))
        except Exception as e:
            raise Exception('Machine not found on remove machine') from e

        if vmInfo.status != 'stopped':
            logger.debug('Info status: %s', vmInfo)
            self._queue = [opStop, opRemove, opFinish]
            return self.__executeQueue()
        self.__setTask(self.service().removeMachine(int(self._vmid)))

        return State.RUNNING

    def __startMachine(self) -> str:
        try:
            vmInfo = self.service().getMachineInfo(int(self._vmid))
        except client.ProxmoxConnectionError:
            return self.__retryLater()
        except Exception as e:
            raise Exception('Machine not found on start machine') from e

        if vmInfo.status == 'stopped':
            self.__setTask(self.service().startMachine(int(self._vmid)))

        return State.RUNNING

    def __stopMachine(self) -> str:
        try:
            vmInfo = self.service().getMachineInfo(int(self._vmid))
        except Exception as e:
            raise Exception('Machine not found on stop machine') from e

        if vmInfo.status != 'stopped':
            logger.debug('Stopping machine %s', vmInfo)
            self.__setTask(self.service().stopMachine(int(self._vmid)))

        return State.RUNNING

    def __shutdownMachine(self) -> str:
        try:
            vmInfo = self.service().getMachineInfo(int(self._vmid))
        except client.ProxmoxConnectionError:
            return State.RUNNING  # Try again later
        except Exception as e:
            raise Exception('Machine not found on suspend machine') from e

        if vmInfo.status != 'stopped':
            self.__setTask(self.service().shutdownMachine(int(self._vmid)))

        return State.RUNNING

    def __gracelyStop(self) -> str:
        """
        Tries to stop machine using vmware tools
        If it takes too long to stop, or vmware tools are not installed,
        will use "power off" "a las bravas"
        """
        self._task = ''
        shutdown = -1  # Means machine already stopped
        vmInfo = self.service().getMachineInfo(int(self._vmid))
        if vmInfo.status != 'stopped':
            self.__setTask(self.service().shutdownMachine(int(self._vmid)))
            shutdown = sql_stamp_seconds()
        logger.debug('Stoped vm using guest tools')
        self.storage.put_pickle('shutdown', shutdown)
        return State.RUNNING

    def __updateVmMacAndHA(self) -> str:
        try:
            self.service().enableHA(
                int(self._vmid), True
            )  # Enable HA before continuing here

            # Set vm mac address now on first interface
            self.service().setVmMac(int(self._vmid), self.get_unique_id())
        except Exception as e:
            logger.exception('Setting HA and MAC on proxmox')
            raise Exception(f'Error setting MAC and HA on proxmox: {e}') from e
        return State.RUNNING

    # Check methods
    def __checkTaskFinished(self):
        if self._task == '':
            return State.FINISHED

        node, upid = self.__getTask()

        try:
            task = self.service().getTaskInfo(node, upid)
        except client.ProxmoxConnectionError:
            return State.RUNNING  # Try again later

        if task.is_errored():
            return self.__error(task.exitstatus)

        if task.isCompleted():
            return State.FINISHED

        return State.RUNNING

    def __checkCreate(self) -> str:
        """
        Checks the state of a deploy for an user or cache
        """
        return self.__checkTaskFinished()

    def __checkStart(self) -> str:
        """
        Checks if machine has started
        """
        return self.__checkTaskFinished()

    def __checkStop(self) -> str:
        """
        Checks if machine has stoped
        """
        return self.__checkTaskFinished()

    def __checkShutdown(self) -> str:
        """
        Check if the machine has suspended
        """
        return self.__checkTaskFinished()

    def __checkGracelyStop(self) -> str:
        """
        Check if the machine has gracely stopped (timed shutdown)
        """
        shutdown_start = self.storage.getPickle('shutdown')
        logger.debug('Shutdown start: %s', shutdown_start)
        if shutdown_start < 0:  # Was already stopped
            # Machine is already stop
            logger.debug('Machine WAS stopped')
            return State.FINISHED

        if shutdown_start == 0:  # Was shut down a las bravas
            logger.debug('Macine DO NOT HAVE guest tools')
            return self.__checkStop()

        logger.debug('Checking State')
        # Check if machine is already stopped
        if self.service().getMachineInfo(int(self._vmid)).status == 'stopped':
            return State.FINISHED  # It's stopped

        logger.debug('State is running')
        if sql_stamp_seconds() - shutdown_start > GUEST_SHUTDOWN_WAIT:
            logger.debug('Time is consumed, falling back to stop')
            self.do_log(
                log.LogLevel.ERROR,
                f'Could not shutdown machine using soft power off in time ({GUEST_SHUTDOWN_WAIT} seconds). Powering off.',
            )
            # Not stopped by guest in time, but must be stopped normally
            self.storage.put_pickle('shutdown', 0)
            return self.__stopMachine()  # Launch "hard" stop

        return State.RUNNING

    def __checkRemoved(self) -> str:
        """
        Checks if a machine has been removed
        """
        return self.__checkTaskFinished()

    def __checkMac(self) -> str:
        """
        Checks if change mac operation has finished.

        Changing nic configuration es 1-step operation, so when we check it here, it is already done
        """
        return State.FINISHED

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

        fncs = {
            opCreate: self.__checkCreate,
            opRetry: self.__retry,
            opWait: self.__wait,
            opStart: self.__checkStart,
            opStop: self.__checkStop,
            opGracelyStop: self.__checkGracelyStop,
            opShutdown: self.__checkShutdown,
            opRemove: self.__checkRemoved,
            opGetMac: self.__checkMac,
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

    def move_to_cache(self, newLevel: int) -> str:
        """
        Moves machines between cache levels
        """
        if opRemove in self._queue:
            return State.RUNNING

        if newLevel == self.L1_CACHE:
            self._queue = [opStart, opFinish]
        else:
            self._queue = [opStart, opShutdown, opFinish]

        return self.__executeQueue()

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

        lst = [] if not self.service().tryGracelyShutdown() else [opGracelyStop]
        queue = lst + [opStop, opRemove, opFinish]

        if op in (opFinish, opWait):
            self._queue[:] = queue
            return self.__executeQueue()

        self._queue = [op] + queue
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
            opShutdown: 'suspend',
            opGracelyStop: 'gracely stop',
            opRemove: 'remove',
            opWait: 'wait',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
            opGetMac: 'getting mac',
        }.get(op, '????')

    def __debug(self, txt):
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, vmid:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._vmid,
            [ProxmoxDeployment.__op2str(op) for op in self._queue],
        )
