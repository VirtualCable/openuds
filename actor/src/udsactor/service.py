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
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
# pylint: disable=invalid-name

import socket
import time
import os
import subprocess
import shlex
import stat
import typing

from . import platform
from . import rest
from . import types
# from .script_thread import ScriptExecutorThread
from .log import logger


# def setup() -> None:
#     cfg = platform.store.readConfig()

#     if logger.logger.windows:
#         # Logs will also go to windows event log for services
#         logger.logger.serviceLogger = True

#     if cfg.x:
#         logger.setLevel(cfg.get('logLevel', 20000))
#     else:
#         logger.setLevel(20000)


class CommonService:
    _isAlive: bool = True
    _rebootRequested: bool = False
    _loggedIn = False
    _cfg: types.ActorConfigurationType
    _api: rest.REST
    _interfaces: typing.List[types.InterfaceInfoType]

    @staticmethod
    def execute(cmdLine: str, section: str):
        cmd = shlex.split(cmdLine, posix=False)

        if os.path.isfile(cmd[0]):
            if (os.stat(cmd[0]).st_mode & stat.S_IXUSR) != 0:
                try:
                    res = subprocess.check_call(cmd)
                except Exception as e:
                    logger.error('Got exception executing: {} - {}'.format(cmdLine, e))
                    return False
                logger.info('Result of executing cmd was {}'.format(res))
                return True
            logger.error('{} file exists but it it is not executable (needs execution permission by admin/root)'.format(section))
        else:
            logger.error('{} file not found & not executed'.format(section))

        return False

    def __init__(self):
        self._cfg = platform.store.readConfig()
        self._interfaces = []
        self._api = rest.REST(self._cfg.host, self._cfg.validateCert)

        socket.setdefaulttimeout(20)

    def reboot(self) -> None:
        self._rebootRequested = True

    def setReady(self) -> None:
        if self._cfg.own_token and self._interfaces:
            self._api.ready(self._cfg.own_token, self._interfaces)
            # Cleans sensible data
            if self._cfg.config:
                self._cfg._replace(config=self._cfg.config._replace(os=None), data=None)
                platform.store.writeConfig(self._cfg)

    def configureMachine(self) -> bool:
        # Retry configurations, config in case of error 10 times
        counter = 1
        while counter < 10 and self._isAlive:
            counter += 1
            try:
                if self._cfg.config and self._cfg.config.os:
                    osData = self._cfg.config.os
                    if osData.action == 'rename':
                        self.rename(osData.name, osData.username, osData.password, osData.new_password)
                    elif osData.action == 'rename_ad':
                        self.joinDomain(osData.name, osData.ad or '', osData.ou or '', osData.username or '', osData.password or '')

                    if self._rebootRequested:
                        try:
                            platform.operations.reboot()
                        except Exception as e:
                            logger.error('Exception on reboot: {}'.format(e))
                        return False  # Stops service
                break
            except Exception as e:
                logger.error('Got exception operationg machine: {}'.format(e))
                self.doWait(5000)

        return True

    def initialize(self) -> bool:
        if not self._cfg.host:  # Not configured
            return False

        # Wait for Broker to be ready
        while self._isAlive:
            if not self._interfaces:
                self._interfaces = list(platform.operations.getNetworkInfo())
                if not self._interfaces:  # Wait a bit for interfaces to get initialized...
                    self.doWait(5000)
                    continue

            try:
                # If master token is present, initialize and get configuration data
                if self._cfg.master_token:
                    initResult: types.InitializationResultType = self._api.initialize(self._cfg.master_token, self._interfaces)
                    if not initResult.own_token:  # Not managed
                        logger.debug('This host is not managed by UDS Broker (ids: {})'.format(self._interfaces))
                        return False

                    self._cfg = self._cfg._replace(
                        master_token=None,
                        own_token=initResult.own_token,
                        config=types.ActorDataConfigurationType(
                            unique_id=initResult.unique_id,
                            max_idle=initResult.max_idle,
                            os=initResult.os
                        )
                    )

                # On first successfull initialization request, master token will dissapear so it will be no more available (not needed anyway)
                platform.store.writeConfig(self._cfg)

                break  # Initial configuration done..
            except rest.RESTConnectionError as e:
                logger.info('Trying to inititialize connection with broker (last error: {})'.format(e))
                self.doWait(5000)  # Wait a bit and retry
            except rest.RESTError as e: # Invalid key?
                logger.error('Error validating with broker. (Invalid token?): {}'.format(e))

        self.configureMachine()

        return True

    def checkIpsChanged(self):
        if not self._cfg.own_token or not self._cfg.config or not self._cfg.config.unique_id:
            # Not enouth data do check
            return

        def locateMac(interfaces: typing.Iterable[types.InterfaceInfoType]) -> typing.Optional[types.InterfaceInfoType]:
            try:
                return next(x for x in interfaces if x.mac.lower() == self._cfg.config.unique_id.lower())
            except StopIteration:
                return None

        try:
            oldIp = locateMac(self._interfaces)
            newIp = locateMac(platform.operations.getNetworkInfo())
            if not newIp:
                raise Exception('No ip currently available for {}'.format(self._cfg.config.unique_id))
            if oldIp != newIp:
                self._api.notifyIpChange(self._cfg.own_token, newIp)
                logger.info('Ip changed from {} to {}. Notified to UDS'.format(oldIp, newIp))
        except Exception as e:
            # No ip changed, log exception for info
            logger.warn('Checking ips faield: {}'.format(e))

    # ***************************************************
    # Methods that ARE overriden by linux & windows Actor
    # ***************************************************
    def rename(self, name: str, user: typing.Optional[str] = None, oldPassword: typing.Optional[str] = None, newPassword: typing.Optional[str] = None):
        '''
        Invoked when broker requests a rename action
        MUST BE OVERRIDEN
        '''
        raise NotImplementedError('Method renamed has not been implemented!')

    def joinDomain(self, name: str, domain: str, ou: str, account: str, password: str):
        '''
        Invoked when broker requests a "domain" action
        MUST BE OVERRIDEN
        '''
        raise NotImplementedError('Method renamed has not been implemented!')

    # ****************************************
    # Methods that CAN BE overriden by actors
    # ****************************************
    def notifyLocal(self):
        self.setReady()

    def doWait(self, miliseconds):
        '''
        Invoked to wait a bit
        CAN be OVERRIDEN
        '''
        time.sleep(float(miliseconds) / 1000)

    def notifyStop(self):
        '''
        Overriden to log stop
        '''
        logger.info('Service is being stopped')

    def preConnect(self, user: str, protocol: str):
        '''
        Invoked when received a PRE Connection request via REST
        '''
        logger.debug('Pre-connect does nothing')
        return 'ok'

    def onLogout(self, user: str):
        logger.debug('On logout invoked for {}'.format(user))
