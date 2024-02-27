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
from enum import auto
import enum
import pickle  # nosec: not insecure, we are loading our own data
import logging
import typing
import collections.abc

from uds.core import services, types
from uds.core.managers.crypto import CryptoManager
from uds.core.util import log, autoserializable
from uds.core.util.model import sql_stamp_seconds

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import OGService
    from .publication import OpenGnsysPublication
    from uds.core.util.storage import Storage

logger = logging.getLogger(__name__)


class Operation(enum.IntEnum):
    CREATE = 0
    ERROR = 1
    FINISH = 2
    RETRY = 3
    REMOVE = 4
    START = 5

    UNKNOWN = 99

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.UNKNOWN


class OpenGnsysUserService(services.UserService, autoserializable.AutoSerializable):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.
    """

    # : Recheck every N seconds by default (for task methods)
    suggested_delay = 20
    _name = autoserializable.StringField(default='unknown')
    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _machine_id = autoserializable.StringField(default='')
    _stamp = autoserializable.IntegerField(default=0)
    _reason = autoserializable.StringField(default='')
    _queue = autoserializable.ListField[Operation]()

    # _name: str = 'unknown'
    # _ip: str = ''
    # _mac: str = ''
    # _machineId: str = ''
    # _stamp: int = 0
    # _reason: str = ''

    # _queue: list[
    #     int
    # ]  # Do not initialize mutable, just declare and it is initialized on "initialize"
    # _uuid: str

    def initialize(self) -> None:
        self._queue = []

    def service(self) -> 'OGService':
        return typing.cast('OGService', super().service())

    def publication(self) -> 'OpenGnsysPublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OpenGnsysPublication', pub)

    def unmarshal(self, data: bytes) -> None:
        """
        Does nothing here also, all data are kept at environment storage
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.split(b'\1')
        if vals[0] == b'v1':
            self._name = vals[1].decode('utf8')
            self._ip = vals[2].decode('utf8')
            self._mac = vals[3].decode('utf8')
            self._machine_id = vals[4].decode('utf8')
            self._reason = vals[5].decode('utf8')
            self._stamp = int(vals[6].decode('utf8'))
            self._queue = [
                Operation.from_int(i) for i in pickle.loads(vals[7])
            ]  # nosec: not insecure, we are loading our own data

        self.mark_for_upgrade()  # Flag so manager can save it again with new format

    def get_name(self) -> str:
        return self._name

    def get_unique_id(self) -> str:
        return self._mac.upper()

    def get_ip(self) -> str:
        return self._ip

    def set_ready(self) -> types.states.DeployState:
        """
        Notifies the current "deadline" to the user, before accessing by UDS
        The machine has been already been started.
        The problem is that currently there is no way that a machine is in FACT started.
        OpenGnsys will try it best by sending an WOL
        """
        dbs = self.db_obj()
        if not dbs:
            return types.states.DeployState.FINISHED

        try:
            # First, check Machine is alive..
            status = self._check_machine_is_ready()
            if status == types.states.DeployState.FINISHED:
                self.service().notify_deadline(self._machine_id, dbs.deployed_service.get_deadline())
                return types.states.DeployState.FINISHED

            if status == types.states.DeployState.ERROR:
                return types.states.DeployState.ERROR

            # Machine powered off, check what to do...
            if not self.service().try_start_if_unavailable():
                return self._error(
                    'Machine is unavailable and "start if unavailable" is not active'
                )

            # Try to start it, and let's see
            self._queue = [Operation.START, Operation.FINISH]
            return self._execute_queue()

        except Exception as e:
            return self._error(f'Error setting ready state: {e}')

    def deploy_for_user(self, user: 'models.User') -> types.states.DeployState:
        """
        Deploys an service instance for an user.
        """
        logger.debug('Deploying for user')
        self._init_queue_for_deploy()
        return self._execute_queue()

    def deploy_for_cache(self, level: int) -> types.states.DeployState:
        """
        Deploys an service instance for cache
        """
        self._init_queue_for_deploy()  # No Level2 Cache possible
        return self._execute_queue()

    def _init_queue_for_deploy(self) -> None:
        self._queue = [Operation.CREATE, Operation.FINISH]

    def _check_machine_is_ready(self) -> types.states.DeployState:
        logger.debug(
            'Checking that state of machine %s (%s) is ready',
            self._machine_id,
            self._name,
        )

        try:
            status = self.service().status(self._machine_id)
        except Exception as e:
            logger.exception('Exception at checkMachineReady')
            return self._error(f'Error checking machine: {e}')

        # possible status are ("off", "oglive", "busy", "linux", "windows", "macos" o "unknown").
        if status['status'] in ("linux", "windows", "macos"):
            return types.states.DeployState.FINISHED

        return types.states.DeployState.RUNNING

    def _get_current_op(self) -> Operation:
        if len(self._queue) == 0:
            return Operation.FINISH

        return self._queue[0]

    def _pop_current_op(self) -> Operation:
        if len(self._queue) == 0:
            return Operation.FINISH

        res = self._queue.pop(0)
        return res

    def _error(self, reason: typing.Any) -> types.states.DeployState:
        """
        Internal method to set object as error state

        Returns:
            types.states.DeployState.ERROR, so we can do "return self.__error(reason)"
        """
        logger.debug('Setting error state, reason: %s', reason)
        self.do_log(log.LogLevel.ERROR, reason)

        if self._machine_id:
            try:
                self.service().unreserve(self._machine_id)
            except Exception as e:
                logger.warning('Error unreserving machine: %s', e)

        self._queue = [Operation.ERROR]
        self._reason = str(reason)
        return types.states.DeployState.ERROR

    def _execute_queue(self) -> types.states.DeployState:
        self._debug('executeQueue')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.DeployState.ERROR

        if op == Operation.FINISH:
            return types.states.DeployState.FINISHED

        fncs: dict[int, typing.Optional[collections.abc.Callable[[], str]]] = {
            Operation.CREATE: self._create,
            Operation.RETRY: self._retry,
            Operation.REMOVE: self._remove,
            Operation.START: self._start,
        }

        try:
            execFnc: typing.Optional[collections.abc.Callable[[], str]] = fncs.get(op)

            if execFnc is None:
                return self._error(f'Unknown operation found at execution queue ({op})')

            execFnc()

            return types.states.DeployState.RUNNING
        except Exception as e:
            # logger.exception('Got Exception')
            return self._error(e)

    # Queue execution methods
    def _retry(self) -> types.states.DeployState:
        """
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        check_state method will "pop" first item when a check operation returns types.states.DeployState.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at check_state
        """
        return types.states.DeployState.FINISHED

    def _create(self) -> str:
        """
        Deploys a machine from template for user/cache
        """
        r: typing.Any = None
        token = CryptoManager().random_string(32)
        try:
            r = self.service().reserve()
            self.service().notify_endpoints(r['id'], token, self._uuid)
        except Exception as e:
            # logger.exception('Creating machine')
            if r:  # Reservation was done, unreserve it!!!
                logger.error('Error on notifyEvent (machine was reserved): %s', e)
                try:
                    self.service().unreserve(self._machine_id)
                except Exception as ei:
                    # Error unreserving reserved machine on creation
                    logger.error('Error unreserving errored machine: %s', ei)

            raise Exception(f'Error creating reservation: {e}') from e

        self._machine_id = r['id']
        self._name = r['name']
        self._mac = r['mac']
        self._ip = r['ip']
        self._stamp = sql_stamp_seconds()

        self.do_log(
            log.LogLevel.INFO,
            f'Reserved machine {self._name}: id: {self._machine_id}, mac: {self._mac}, ip: {self._ip}',
        )

        # Store actor version & Known ip
        dbs = self.db_obj()
        if dbs:
            dbs.properties['actor_version'] = '1.1-OpenGnsys'
            dbs.properties['token'] = token
            dbs.log_ip(self._ip)

        return types.states.DeployState.RUNNING

    def _start(self) -> str:
        if self._machine_id:
            self.service().power_on(self._machine_id)
        return types.states.DeployState.RUNNING

    def _remove(self) -> str:
        """
        Removes a machine from system
        Avoids "double unreserve" in case the reservation was made from release
        """
        dbs = self.db_obj()
        if dbs:
            # On release callback, we will set a property on DB called "from_release"
            # so we can avoid double unreserve
            if dbs.properties.get('from_release') is None:
                self.service().unreserve(self._machine_id)
        return types.states.DeployState.RUNNING

    # Check methods
    def _create_checker(self) -> types.states.DeployState:
        """
        Checks the state of a deploy for an user or cache
        """
        return self._check_machine_is_ready()

    # Alias for poweron check
    _checkStart = _create_checker

    def _removed_checker(self) -> types.states.DeployState:
        """
        Checks if a machine has been removed
        """
        return types.states.DeployState.FINISHED  # No check at all, always true

    def check_state(self) -> types.states.DeployState:
        """
        Check what operation is going on, and acts acordly to it
        """
        self._debug('check_state')
        op = self._get_current_op()

        if op == Operation.ERROR:
            return types.states.DeployState.ERROR

        if op == Operation.FINISH:
            return types.states.DeployState.FINISHED

        fncs: dict[Operation, typing.Optional[collections.abc.Callable[[], types.states.DeployState]]] = {
            Operation.CREATE: self._create_checker,
            Operation.RETRY: self._retry,
            Operation.REMOVE: self._removed_checker,
            Operation.START: self._checkStart,
        }

        try:
            chkFnc: typing.Optional[typing.Optional[collections.abc.Callable[[], types.states.DeployState]]] = fncs.get(op)

            if chkFnc is None:
                return self._error(f'Unknown operation found at check queue ({op})')

            state = chkFnc()
            if state == types.states.DeployState.FINISHED:
                self._pop_current_op()  # Remove runing op
                return self._execute_queue()

            return state
        except Exception as e:
            return self._error(e)

    def error_reason(self) -> str:
        """
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).
        """
        return self._reason

    def destroy(self) -> types.states.DeployState:
        """
        Invoked for destroying a deployed service
        """
        self._debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        self._queue = [Operation.REMOVE, Operation.FINISH]
        return self._execute_queue()

    def cancel(self) -> types.states.DeployState:
        """
        This is a task method. As that, the excepted return values are
        types.states.DeployState.values RUNNING, FINISHED or ERROR.

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
            Operation.REMOVE: 'remove',
            Operation.ERROR: 'error',
            Operation.FINISH: 'finish',
            Operation.RETRY: 'retry',
        }.get(op, '????')

    def _debug(self, txt: str) -> None:
        logger.debug(
            'types.states.DeployState.at %s: name: %s, ip: %s, mac: %s, machine:%s, queue: %s',
            txt,
            self._name,
            self._ip,
            self._mac,
            self._machine_id,
            [OpenGnsysUserService._op2str(op) for op in self._queue],
        )
