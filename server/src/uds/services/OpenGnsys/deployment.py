# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2021 Virtual Cable S.L.U.
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
import pickle  # nosec: not insecure, we are loading our own data
import logging
import typing

from uds.core import services
from uds.core.managers.crypto import CryptoManager
from uds.core.util.state import State
from uds.core.util import log
from uds.core.util.model import getSqlDatetimeAsUnix

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import OGService
    from .publication import OGPublication
    from uds.core.util.storage import Storage

logger = logging.getLogger(__name__)

opCreate, opError, opFinish, opRemove, opRetry, opStart = range(6)


class OGDeployment(services.UserService):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.
    """

    # : Recheck every N seconds by default (for task methods)
    suggestedTime = 20

    _name: str = 'unknown'
    _ip: str = ''
    _mac: str = ''
    _machineId: str = ''
    _stamp: int = 0
    _reason: str = ''

    _queue: typing.List[
        int
    ]  # Do not initialize mutable, just declare and it is initialized on "initialize"
    _uuid: str

    def initialize(self) -> None:
        self._queue = []

    def service(self) -> 'OGService':
        return typing.cast('OGService', super().service())

    def publication(self) -> 'OGPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OGPublication', pub)

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
                self._machineId.encode('utf8'),
                self._reason.encode('utf8'),
                str(self._stamp).encode('utf8'),
                pickle.dumps(self._queue, protocol=0),
            ]
        )

    def unmarshal(self, data: bytes) -> None:
        """
        Does nothing here also, all data are kept at environment storage
        """
        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._machineId = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._stamp = int(vals[6].decode('utf8'))
            self._queue = pickle.loads(
                vals[7]
            )  # nosec: not insecure, we are loading our own data

    def getName(self) -> str:
        return self._name

    def getUniqueId(self) -> str:
        return self._mac.upper()

    def getIp(self) -> str:
        return self._ip

    def setReady(self) -> str:
        """
        Notifies the current "deadline" to the user, before accessing by UDS
        The machine has been already been started.
        The problem is that currently there is no way that a machine is in FACT started.
        OpenGnsys will try it best by sending an WOL
        """
        dbs = self.dbObj()
        if not dbs:
            return State.FINISHED

        try:
            # First, check Machine is alive..
            status = self.__checkMachineReady()
            if status == State.FINISHED:
                self.service().notifyDeadline(
                    self._machineId, dbs.deployed_service.getDeadline()
                )
                return State.FINISHED

            if status == State.ERROR:
                return State.ERROR

            # Machine powered off, check what to do...
            if self.service().isRemovableIfUnavailable():
                return self.__error(
                    'Machine is unavailable and service has "Remove if unavailable" flag active.'
                )

            # Try to start it, and let's see
            self._queue = [opStart, opFinish]
            return self.__executeQueue()

        except Exception as e:
            return self.__error(f'Error setting ready state: {e}')

    def deployForUser(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self.__initQueueForDeploy()
        return self.__executeQueue()

    def deployForCache(self, cacheLevel: int) -> str:
        """
        Deploys an service instance for cache
        """
        self.__initQueueForDeploy()  # No Level2 Cache possible
        return self.__executeQueue()

    def __initQueueForDeploy(self) -> None:
        self._queue = [opCreate, opFinish]

    def __checkMachineReady(self) -> str:
        logger.debug(
            'Checking that state of machine %s (%s) is ready',
            self._machineId,
            self._name,
        )

        try:
            status = self.service().status(self._machineId)
        except Exception as e:
            logger.exception('Exception at checkMachineReady')
            return self.__error(f'Error checking machine: {e}')

        # possible status are ("off", "oglive", "busy", "linux", "windows", "macos" o "unknown").
        if status['status'] in ("linux", "windows", "macos"):
            return State.FINISHED

        return State.RUNNING

    def __getCurrentOp(self) -> int:
        if len(self._queue) == 0:
            return opFinish

        return self._queue[0]

    def __popCurrentOp(self) -> int:
        if len(self._queue) == 0:
            return opFinish

        res = self._queue.pop(0)
        return res

    def __error(self, reason: typing.Any) -> str:
        """
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self.__error(reason)"
        """
        logger.debug('Setting error state, reason: %s', reason)
        self.doLog(log.LogLevel.ERROR, reason)

        if self._machineId:
            try:
                self.service().unreserve(self._machineId)
            except Exception as e:
                logger.warning('Error unreserving machine: %s', e)

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
            opRemove: self.__remove,
            opStart: self.__start,
        }

        try:
            execFnc: typing.Optional[typing.Callable[[], str]] = fncs.get(op)

            if execFnc is None:
                return self.__error(
                    f'Unknown operation found at execution queue ({op})'
                )

            execFnc()

            return State.RUNNING
        except Exception as e:
            # logger.exception('Got Exception')
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

    def __create(self) -> str:
        """
        Deploys a machine from template for user/cache
        """
        r: typing.Any = None
        token = CryptoManager().randomString(32)
        try:
            r = self.service().reserve()
            self.service().notifyEvents(r['id'], token, self._uuid)
        except Exception as e:
            # logger.exception('Creating machine')
            if r:  # Reservation was done, unreserve it!!!
                logger.error('Error on notifyEvent (machine was reserved): %s', e)
                try:
                    self.service().unreserve(self._machineId)
                except Exception as ei:
                    # Error unreserving reserved machine on creation
                    logger.error('Error unreserving errored machine: %s', ei)

            raise Exception(f'Error creating reservation: {e}') from e

        self._machineId = r['id']
        self._name = r['name']
        self._mac = r['mac']
        self._ip = r['ip']
        self._stamp = getSqlDatetimeAsUnix()

        self.doLog(
            log.LogLevel.INFO,
            f'Reserved machine {self._name}: id: {self._machineId}, mac: {self._mac}, ip: {self._ip}',
        )

        # Store actor version & Known ip
        dbs = self.dbObj()
        if dbs:
            dbs.properties['actor_version'] = '1.1-OpenGnsys'
            dbs.properties['token'] = token
            dbs.logIP(self._ip)

        return State.RUNNING

    def __start(self) -> str:
        if self._machineId:
            self.service().powerOn(self._machineId)
        return State.RUNNING

    def __remove(self) -> str:
        """
        Removes a machine from system
        Avoids "double unreserve" in case the reservation was made from release
        """
        dbs = self.dbObj()
        if dbs:
            # On release callback, we will set a property on DB called "from_release"
            # so we can avoid double unreserve
            if dbs.properties.get('from_release') is None:
                self.service().unreserve(self._machineId)
        return State.RUNNING

    # Check methods
    def __checkCreate(self) -> str:
        """
        Checks the state of a deploy for an user or cache
        """
        return self.__checkMachineReady()

    # Alias for poweron check
    __checkStart = __checkCreate

    def __checkRemoved(self) -> str:
        """
        Checks if a machine has been removed
        """
        return State.FINISHED  # No check at all, always true

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
            opRemove: self.__checkRemoved,
            opStart: self.__checkStart,
        }

        try:
            chkFnc: typing.Optional[
                typing.Optional[typing.Callable[[], str]]
            ] = fncs.get(op)

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
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        self._queue = [opRemove, opFinish]
        return self.__executeQueue()

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
            opRemove: 'remove',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
        }.get(op, '????')

    def __debug(self, txt) -> None:
        logger.debug(
            'State at %s: name: %s, ip: %s, mac: %s, machine:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._machineId,
            [OGDeployment.__op2str(op) for op in self._queue],
        )
