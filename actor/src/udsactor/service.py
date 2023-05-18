# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2023 Virtual Cable S.L.
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
@author: Alexander Burmatov,  thatman at altlinux dot org
'''
# pylint: disable=invalid-name

import socket
import time
import secrets
import subprocess
import typing

from udsactor import platform
from udsactor import rest
from udsactor import types
from udsactor import tools

from udsactor.log import logger, DEBUG, INFO, ERROR, FATAL
from udsactor.http import clients_pool, server, cert

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
    _initialized: bool = False
    _cfg: types.ActorConfigurationType
    _api: rest.UDSServerApi
    _interfaces: typing.List[types.InterfaceInfoType]
    _secret: str
    _certificate: types.CertificateInfoType
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
        self._certificate = (
            cert.defaultCertificate
        )  # For being used on "unmanaged" hosts only, and prior to first login
        self._http = None

        # Initialzies loglevel and serviceLogger
        # 0 = DEBUG, 1 = INFO, 2 = ERROR, 3 = FATAL in combobox
        # BUT!!!:
        # 0 = OTHER, 10000 = DEBUG, 20000 = WARN, 30000 = INFO, 40000 = ERROR, 50000 = FATAL
        # So this comes:
        logger.setLevel([DEBUG, INFO, ERROR, FATAL][self._cfg.log_level])
        # If windows, enable service logger FOR SERVICE only
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
        return (
            self._cfg.actorType != types.UNMANAGED
        )  # Only "unmanaged" hosts are unmanaged, the rest are "managed"

    def serviceInterfaceInfo(
        self, interfaces: typing.Optional[typing.List[types.InterfaceInfoType]] = None
    ) -> typing.Optional[types.InterfaceInfoType]:
        """
        returns the inteface with unique_id mac or first interface or None if no interfaces...
        """
        interfaces = (
            interfaces or self._interfaces
        )  # Emty interfaces is like "no ip change" because cannot be notified
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

    def canCleanSensibleData(self) -> bool:
        return True

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
                        self._certificate = self._api.ready(
                            self._cfg.own_token,
                            self._secret,
                            srvInterface.ip,
                            rest.LISTEN_PORT,
                        )
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
            if self.canCleanSensibleData():
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
                return False  # If the command fails, continue with the rest of the operations...

        # Retry configuration while not stop service, config in case of error 10 times, reboot vm
        counter = 10
        while self._isAlive:
            counter -= 1
            try:
                if self._cfg.config and self._cfg.config.os:
                    osData = self._cfg.config.os
                    custom: typing.Mapping[str, typing.Any] = osData.custom or {}
                    # Needs UDS Server >= 4.0 to work
                    if osData.action == 'rename':
                        self.rename(
                            osData.name,
                            custom.get('username'),
                            custom.get('password'),
                            custom.get('new_password'),
                        )
                    elif osData.action == 'rename_ad':
                        self.joinDomain(osData.name, custom)

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
        # Notify UDS about my callback
        self.getInterfaces()  # Ensure we have interfaces
        if self._cfg.master_token:
            try:
                self._certificate = self._api.notifyUnmanagedCallback(
                    self._cfg.master_token,
                    self._secret,
                    self._interfaces,
                    rest.LISTEN_PORT,
                )
            except Exception as e:
                logger.error('Couuld not notify unmanaged callback: %s', e)

        return True

    def getInterfaces(self) -> None:
        if self._interfaces:
            return

        while self._isAlive:
            self._interfaces = tools.validNetworkCards(
                self._cfg.restrict_net, platform.operations.getNetworkInfo()
            )
            if self._interfaces:
                break
            self.doWait(5000)

    def initialize(self) -> bool:
        if self._initialized or not self._cfg.host or not self._isAlive:  # Not configured or not running
            return False

        self._initialized = True

        # Force time sync, just in case...
        if self.isManaged():
            platform.operations.forceTimeSync()

        # Wait for Broker to be ready
        # Ensure we have intefaces...
        self.getInterfaces()

        while self._isAlive:
            try:
                # If master token is present, initialize and get configuration data
                if self._cfg.master_token:
                    initResult: types.InitializationResultType = self._api.initialize(
                        self._cfg.master_token, self._interfaces, self._cfg.actorType
                    )
                    if not initResult.own_token:  # Not managed
                        logger.debug(
                            'This host is not managed by UDS Broker (ids: {})'.format(self._interfaces)
                        )
                        return False

                    # Only removes master token for managed machines (will need it on next client execution)
                    # For unmanaged, if alias is present, replace master token with it
                    master_token = (
                        None if self.isManaged() else (initResult.alias_token or self._cfg.master_token)
                    )
                    # Replace master token with alias token if present
                    self._cfg = self._cfg._replace(
                        master_token=master_token,
                        own_token=initResult.own_token,
                        config=types.ActorDataConfigurationType(
                            unique_id=initResult.unique_id, os=initResult.os
                        ),
                    )

                # On first successfull initialization request, master token will dissapear for managed hosts
                # so it will be no more available (not needed anyway). For unmanaged, the master token will
                # be replaced with an alias token.
                platform.store.writeConfig(self._cfg)

                # Setup logger now
                if self._cfg.own_token:
                    logger.setRemoteLogger(self._api, self._cfg.own_token)

                break  # Initial configuration done..
            except rest.RESTConnectionError as e:
                logger.info('Trying to inititialize connection with broker (last error: {})'.format(e))
                self.doWait(5000)  # Wait a bit and retry
            except rest.RESTError as e:  # Invalid key?
                logger.error('Error validating with broker. (Invalid token?): {}'.format(e))
                return False
            except Exception:
                logger.exception()
                self.doWait(5000)  # Wait a bit and retry...

        return self.configureMachine()

    def uninitialize(self):
        self._initialized = False
        self._cfg = self._cfg._replace(own_token=None)  # Ensures assigned token is cleared

    def finish(self) -> None:
        if self._http:
            self._http.stop()

        # If logged in, notify UDS of logout (daemon stoped = no control = logout)
        # For every connected client...
        if self._cfg.own_token:
            for client in clients_pool.UDSActorClientPool().clients:
                if client.session_id:
                    try:
                        self._api.logout(
                            self._cfg.actorType,
                            self._cfg.own_token,
                            '',
                            client.session_id or 'stop',  # If no session id, pass "stop"
                            '',
                            self._interfaces,
                            self._secret,
                        )
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
            currentInterfaces = tools.validNetworkCards(
                self._cfg.restrict_net, platform.operations.getNetworkInfo()
            )
            old = self.serviceInterfaceInfo()
            new = self.serviceInterfaceInfo(currentInterfaces)
            if not new or not old:
                raise Exception('No ip currently available for {}'.format(self._cfg.config.unique_id))
            if old.ip != new.ip:
                self._certificate = self._api.notifyIpChange(
                    self._cfg.own_token, self._secret, new.ip, rest.LISTEN_PORT
                )
                # Now store new addresses & interfaces...
                self._interfaces = currentInterfaces
                logger.info('Ip changed from {} to {}. Notified to UDS'.format(old.ip, new.ip))
                # Stop the running HTTP Thread and start a new one, with new generated cert
                self.startHttpServer()
        except Exception as e:
            # No ip changed, log exception for info
            logger.warn('Checking ips failed: {}'.format(e))

    def loop(self):
        # Main common loop
        try:
            # Checks if ips has changed
            self.checkIpsChanged()

            # Now check if every registered client is already there (if logged in OFC)
            for lost_client in clients_pool.UDSActorClientPool().lost_clients():
                logger.info('Lost client: {}'.format(lost_client))
                self.logout('client_unavailable', '', lost_client.session_id or '')  # '' means "all clients"
        except Exception as e:
            logger.error('Exception on main service loop: %s', e)

    # ******************************************************
    # Methods that can be overriden by linux & windows Actor
    # ******************************************************
    def rename(
        self,
        name: str,
        userName: typing.Optional[str] = None,
        oldPassword: typing.Optional[str] = None,
        newPassword: typing.Optional[str] = None,
    ) -> None:
        '''
        Invoked when broker requests a rename action
        '''
        hostName = platform.operations.getComputerName()

        # Check for password change request for an user
        if userName and newPassword:
            logger.info('Setting password for configured user')
            try:
                platform.operations.changeUserPassword(userName, oldPassword or '', newPassword)
            except Exception as e:
                # Logs error, but continue renaming computer
                logger.error('Could not change password for user {}: {}'.format(userName, e))

        if hostName.lower() == name.lower():
            logger.info('Computer name is already {}'.format(hostName))
            return

        if platform.operations.renameComputer(name):
            self.reboot()

    def joinDomain(self, name: str, custom: typing.Mapping[str, typing.Any]) -> None:
        '''
        Invoked when broker requests a "domain" action
        default does nothing
        '''
        logger.debug('Base join invoked: %s on %s, %s', name, custom)

    # Client notifications
    def login(self, username: str, sessionType: typing.Optional[str] = None) -> types.LoginResultInfoType:
        result = types.LoginResultInfoType(ip='', hostname='', dead_line=None, max_idle=None, session_id=None)
        master_token = None
        secret = None
        # If unmanaged, do initialization now, because we don't know before this
        # Also, even if not initialized, get a "login" notification token
        if not self.isManaged():
            self._initialized = (
                self.initialize()
            )  # Maybe it's a local login by an unmanaged host.... On real login, will execute initilize again
            # Unamanaged, need the master token
            master_token = self._cfg.master_token
            secret = self._secret

        # Own token will not be set if UDS did not assigned the initialized VM to an user
        # In that case, take master token (if machine is Unamanaged version)
        token = self._cfg.own_token or master_token
        if token:
            result = self._api.login(
                self._cfg.actorType,
                token,
                username,
                sessionType or '',
                self._interfaces,
                secret,
            )

        if (
            result.session_id
        ):  # If logged in, process it. client_pool will take account of login response to client and session
            script = platform.store.invokeScriptOnLogin()
            if script:
                logger.info('Executing script on login: {}'.format(script))
                script += f'{username} {sessionType or "unknown"} {self._cfg.actorType}'
                self.execute(script, 'Logon')

        return result

    def logout(
        self,
        username: str,
        session_type: typing.Optional[str],
        session_id: typing.Optional[str],
    ) -> None:
        master_token = self._cfg.master_token

        # Own token will not be set if UDS did not assigned the initialized VM to an user
        # In that case, take master token (if machine is Unamanaged version)
        token = self._cfg.own_token or master_token
        if token:
            # If logout is not processed (that is, not ok result), the logout has not been processed
            if (
                self._api.logout(
                    self._cfg.actorType,
                    token,
                    username,
                    session_id or '',
                    session_type or '',
                    self._interfaces,
                    self._secret,
                )
                != 'ok'  # Can return also "notified", that means the logout has not been processed by UDS
            ):
                logger.info('Logout from %s ignored as required by uds broker', username)
                return

        self.onLogout(username, session_id or '')

        if not self.isManaged():
            self.uninitialize()

    # ******************************************************
    # Methods that CAN BE overriden by specific OS Actor
    # ******************************************************
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

    def preConnect(self, userName: str, protocol: str, ip: str, hostname: str, udsUserName: str) -> str:
        '''
        Invoked when received a PRE Connection request via REST
        Base preconnect executes the preconnect command
        '''
        if self._cfg.pre_command:
            self.execute(
                self._cfg.pre_command
                + ' {} {} {} {} {}'.format(
                    userName.replace('"', '%22'),
                    protocol,
                    ip,
                    hostname,
                    udsUserName.replace('"', '%22'),
                ),
                'preConnect',
            )

        return 'ok'

    def onLogout(self, userName: str, session_id: str) -> None:
        logger.debug('On logout invoked for {}'.format(userName))
