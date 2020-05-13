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
import secrets
import subprocess
import typing

from . import platform
from . import rest
from . import types

from .log import logger, DEBUG, INFO, ERROR, FATAL
from .http import clients_pool, server, cert

# def setup() -> None:
#     cfg = platform.store.readConfig()

#     if logger.logger.windows:
#         # Logs will also go to windows event log for services
#         logger.logger.serviceLogger = True

#     if cfg.x:
#         logger.setLevel(cfg.get('logLevel', 20000))
#     else:
#         logger.setLevel(20000)

class CommonService:  # pylint: disable=too-many-instance-attributes
    _isAlive: bool = True
    _rebootRequested: bool = False
    _loggedIn = False

    _cfg: types.ActorConfigurationType
    _api: rest.UDSServerApi
    _interfaces: typing.List[types.InterfaceInfoType]
    _secret: str
    _certificate: types.CertificateInfoType
    _clientsPool: clients_pool.UDSActorClientPool
    _http: typing.Optional[server.HTTPServerThread]

    @staticmethod
    def execute(cmdLine: str, section: str) -> bool:
        try:
            logger.debug('Executing command on {}: {}'.format(section, cmdLine))
            res = subprocess.check_call(cmdLine, shell=True)
        except Exception as e:
            logger.error('Got exception executing: {} - {} - {}'.format(section, cmdLine, e))
            return False
        logger.debug('Result of executing cmd for {} was {}'.format(section, res))
        return True

    def __init__(self) -> None:
        self._cfg = platform.store.readConfig()
        self._interfaces = []
        self._api = rest.UDSServerApi(self._cfg.host, self._cfg.validateCertificate)
        self._secret = secrets.token_urlsafe(33)
        self._clientsPool = clients_pool.UDSActorClientPool()
        self._certificate = cert.defaultCertificate  # For being used on "unmanaged" hosts only
        self._http = None

        # Initialzies loglevel and serviceLogger
        # 0 = DEBUG, 1 = INFO, 2 = ERROR, 3 = FATAL in combobox
        # BUT!!!:
        # 0 = OTHER, 10000 = DEBUG, 20000 = WARN, 30000 = INFO, 40000 = ERROR, 50000 = FATAL
        # So this comes:
        logger.setLevel([DEBUG, INFO, ERROR, FATAL][self._cfg.log_level])
        # If windows, enable service logger
        logger.enableServiceLogger()

        socket.setdefaulttimeout(20)

    def startHttpServer(self):
        # Starts the http thread
        if self._http:
            try:
                self._http.stop()
            except Exception:
                pass

        self._http = server.HTTPServerThread(self)
        self._http.start()

    def isManaged(self) -> bool:
        return self._cfg.actorType != types.UNMANAGED  # Only "unmanaged" hosts are unmanaged, the rest are "managed"

    def serviceInterfaceInfo(self, interfaces: typing.Optional[typing.List[types.InterfaceInfoType]] = None) -> typing.Optional[types.InterfaceInfoType]:
        """
        returns the inteface with unique_id mac or first interface or None if no interfaces...
        """
        interfaces = interfaces or self._interfaces  # Emty interfaces is like "no ip change" because cannot be notified
        if self._cfg.config and interfaces:
            try:
                return next(x for x in interfaces if x.mac.lower() == self._cfg.config.unique_id)
            except StopIteration:
                return interfaces[0]

        return None

    def reboot(self) -> None:
        # Reboot just after renaming
        logger.info('Rebooting...')
        self._rebootRequested = True

    def setReady(self) -> None:
        if not self._isAlive or not self.isManaged():
            return
        # Unamanged actor types does not set ready never (has no osmanagers, no needing for this)

        # First, if postconfig is available, execute it and disable it
        if self._cfg.post_command:
            self.execute(self._cfg.post_command, 'postConfig')
            self._cfg = self._cfg._replace(post_command=None)
            platform.store.writeConfig(self._cfg)

        if self._cfg.own_token and self._interfaces:
            srvInterface = self.serviceInterfaceInfo()
            if srvInterface:
                # Rery while RESTConnectionError (that is, cannot connect)
                counter = 60
                logged = False
                while self._isAlive:
                    counter -= 1
                    try:
                        self._certificate = self._api.ready(self._cfg.own_token, self._secret, srvInterface.ip, rest.LISTEN_PORT)
                    except rest.RESTConnectionError as e:
                        if not logged:  # Only log connection problems ONCE
                            logged = True
                            logger.error('Error connecting with UDS Broker')
                        self.doWait(5000)
                        continue
                    except Exception as e:
                        logger.error('Unhandled exception while setting ready: %s', e)
                        if counter > 0:
                            self.doWait(10000)  # A long wait on other error...
                            continue
                        platform.operations.reboot()  # On too many errors, simply reboot
                    # Success or any error that is not recoverable (retunerd by UDS). if Error, service will be cleaned in a while.
                    break
            else:
                logger.error('Could not locate IP address!!!. (Not registered with UDS)')

        # Do not continue if not alive...
        if not self._isAlive:
            return

        # Cleans sensible data
        if self._cfg.config:
            self._cfg = self._cfg._replace(config=self._cfg.config._replace(os=None), data=None)
            platform.store.writeConfig(self._cfg)

        logger.info('Service ready')

    def configureMachine(self) -> bool:
        if not self._isAlive:
            return False

        if not self.isManaged():
            return True

        # First, if runonce is present, honor it and remove it from config
        # Return values is "True" for keep service (or daemon) running, False if Stop it.
        if self._cfg.runonce_command:
            runOnce = self._cfg.runonce_command
            self._cfg = self._cfg._replace(runonce_command=None)
            platform.store.writeConfig(self._cfg)
            if self.execute(runOnce, "runOnce"):
            # If runonce is present, will not do anythin more
            # So we have to ensure that, when runonce command is finished, reboots the machine.
            # That is, the COMMAND itself has to restart the machine!
                return False   # If the command fails, continue with the rest of the operations...

        # Retry configuration while not stop service, config in case of error 10 times, reboot vm
        counter = 10
        while self._isAlive:
            counter -= 1
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
                        return False  # Stops service if reboot was requested ofc
                break
            except Exception as e:
                logger.error('Got exception operating machine: {}'.format(e))
                if counter > 0:
                    self.doWait(5000)
                else:
                    platform.operations.reboot()
                    return False

        return True

    def initializeUnmanaged(self) -> bool:
        return True

    def initialize(self) -> bool:
        if not self._cfg.host or not self._isAlive:  # Not configured or not running
            return False

        # Force time sync, just in case...
        if self.isManaged():
            platform.operations.forceTimeSync()

        # Wait for Broker to be ready
        while self._isAlive:
            if not self._interfaces:
                self._interfaces = list(platform.operations.getNetworkInfo())
                if not self._interfaces:  # Wait a bit for interfaces to get initialized... (has valid IPs)
                    self.doWait(5000)
                    continue

            try:
                # If master token is present, initialize and get configuration data
                if self._cfg.master_token:
                    initResult: types.InitializationResultType = self._api.initialize(self._cfg.master_token, self._interfaces, self._cfg.actorType)
                    if not initResult.own_token:  # Not managed
                        logger.debug('This host is not managed by UDS Broker (ids: {})'.format(self._interfaces))
                        return False

                    # Only removes token for managed machines
                    master_token = None if self.isManaged() else self._cfg.master_token
                    self._cfg = self._cfg._replace(
                        master_token=master_token,
                        own_token=initResult.own_token,
                        config=types.ActorDataConfigurationType(
                            unique_id=initResult.unique_id,
                            os=initResult.os
                        )
                    )

                # On first successfull initialization request, master token will dissapear for managed hosts so it will be no more available (not needed anyway)
                if self.isManaged():
                    platform.store.writeConfig(self._cfg)

                # Setup logger now
                if self._cfg.own_token:
                    logger.setRemoteLogger(self._api, self._cfg.own_token)

                break  # Initial configuration done..
            except rest.RESTConnectionError as e:
                logger.info('Trying to inititialize connection with broker (last error: {})'.format(e))
                self.doWait(5000)  # Wait a bit and retry
            except rest.RESTError as e: # Invalid key?
                logger.error('Error validating with broker. (Invalid token?): {}'.format(e))
                return False

        return self.configureMachine()

    def finish(self) -> None:
        if self._http:
            self._http.stop()

        # If logged in, notify UDS of logout (daemon stoped = no control = logout)
        if self._loggedIn and self._cfg.own_token:
            self._loggedIn = False
            try:
                self._api.logout(self._cfg.own_token, '')
            except Exception as e:
                logger.error('Error notifying final logout to UDS: %s', e)

        self.notifyStop()

    def checkIpsChanged(self) -> None:
        if not self.isManaged():
            return  # Unamanaged hosts does not changes ips. (The full initialize-login-logout process is done in a row, so at login the IP is correct)

        try:
            if not self._cfg.own_token or not self._cfg.config or not self._cfg.config.unique_id:
                # Not enouth data do check
                return
            currentInterfaces = list(platform.operations.getNetworkInfo())
            old = self.serviceInterfaceInfo()
            new = self.serviceInterfaceInfo(currentInterfaces)
            if not new or not old:
                raise Exception('No ip currently available for {}'.format(self._cfg.config.unique_id))
            if old.ip != new.ip:
                self._certificate = self._api.notifyIpChange(self._cfg.own_token, self._secret, new.ip, rest.LISTEN_PORT)
                # Now store new addresses & interfaces...
                self._interfaces = currentInterfaces
                logger.info('Ip changed from {} to {}. Notified to UDS'.format(old.ip, new.ip))
                # Stop the running HTTP Thread and start a new one, with new generated cert
                self.startHttpServer()
        except Exception as e:
            # No ip changed, log exception for info
            logger.warn('Checking ips failed: {}'.format(e))

    def rename(
            self,
            name: str,
            userName: typing.Optional[str] = None,
            oldPassword: typing.Optional[str] = None,
            newPassword: typing.Optional[str] = None
        ) -> None:
        '''
        Invoked when broker requests a rename action
        default does nothing
        '''
        hostName = platform.operations.getComputerName()

        if hostName.lower() == name.lower():
            logger.info('Computer name is already {}'.format(hostName))
            return

        # Check for password change request for an user
        if userName and newPassword:
            logger.info('Setting password for configured user')
            try:
                platform.operations.changeUserPassword(userName, oldPassword or '', newPassword)
            except Exception as e:
                raise Exception('Could not change password for user {} (maybe invalid current password is configured at broker): {} '.format(userName, str(e)))

        if platform.operations.renameComputer(name):
            self.reboot()

    def loop(self):
        # Main common loop
        try:
            # Checks if ips has changed
            self.checkIpsChanged()

            # Now check if every registered client is already there (if logged in OFC)
            if self._loggedIn and not self._clientsPool.ping():
                self.logout('client_unavailable')
        except Exception as e:
            logger.error('Exception on main service loop: %s', e)

    # ******************************************************
    # Methods that can be overriden by linux & windows Actor
    # ******************************************************
    def joinDomain(  # pylint: disable=unused-argument, too-many-arguments
            self,
            name: str,
            domain: str,
            ou: str,
            account: str,
            password: str
        ) -> None:
        '''
        Invoked when broker requests a "domain" action
        default does nothing
        '''
        logger.debug('Base join invoked: {} on {}, {}'.format(name, domain, ou))

    # Client notifications
    def login(self, username: str) -> types.LoginResultInfoType:
        result = types.LoginResultInfoType(ip='', hostname='', dead_line=None, max_idle=None)
        self._loggedIn = True
        if not self.isManaged():
            self.initialize()

        if self._cfg.own_token:
            result = self._api.login(self._cfg.own_token, username)

        return result

    def logout(self, username: str) -> None:
        self._loggedIn = False
        if self._cfg.own_token:
            self._api.logout(self._cfg.own_token, username)

        self.onLogout(username)

        self._cfg = self._cfg._replace(own_token=None)  # Ensures assigned token is cleared

    # ****************************************
    # Methods that CAN BE overriden by actors
    # ****************************************
    def doWait(self, miliseconds: int) -> None:
        '''
        Invoked to wait a bit
        CAN be OVERRIDEN
        '''
        seconds = miliseconds / 1000.0
        # So it can be broken by "stop"
        while self._isAlive and seconds > 1:
            time.sleep(1)
            seconds -= 1
        time.sleep(seconds)

    def notifyStop(self) -> None:
        '''
        Overriden to log stop (on windows, notify to service manager)
        '''
        logger.info('Service stopped')

    def preConnect(self, userName: str, protocol: str, ip: str, hostname: str) -> str:  # pylint: disable=unused-argument
        '''
        Invoked when received a PRE Connection request via REST
        Base preconnect executes the preconnect command
        '''
        if self._cfg.pre_command:
            self.execute(self._cfg.pre_command + ' {} {} {} {}'.format(userName.replace('"', '%22'), protocol, ip, hostname), 'preConnect')

        return 'ok'

    def onLogout(self, userName: str) -> None:
        logger.debug('On logout invoked for {}'.format(userName))
