# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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
from __future__ import unicode_literals

from udsactor.log import logger

from . import operations
from . import store
from . import REST
from . import ipc
from . import httpserver
from .scriptThread import ScriptExecutorThread
from .utils import exceptionToMessage

import socket
import time
import random
import os
import subprocess
import shlex
import stat

IPC_PORT = 39188

cfg = None


def initCfg():
    global cfg  # pylint: disable=global-statement
    cfg = store.readConfig()

    if logger.logger.isWindows():
        # Logs will also go to windows event log for services
        logger.logger.serviceLogger = True

    if cfg is not None:
        logger.setLevel(cfg.get('logLevel', 20000))
    else:
        logger.setLevel(20000)
        cfg = {}

    # If ANY var is missing, reset cfg
    for v in ('host', 'ssl', 'masterKey'):
        if v not in cfg:
            cfg = None
            break

    return cfg


class CommonService(object):
    def __init__(self):
        self.isAlive = True
        self.api = None
        self.ipc = None
        self.httpServer = None
        self.rebootRequested = False
        self.knownIps = []
        socket.setdefaulttimeout(20)

    def reboot(self):
        self.rebootRequested = True

    def execute(self, cmdLine, section):
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
            else:
                logger.error('{} file exists but it it is not executable (needs execution permission by admin/root)'.format(section))
        else:
            logger.error('{} file not found & not executed'.format(section))

        return False

    def setReady(self):
        self.api.setReady([(v.mac, v.ip) for v in operations.getNetworkInfo()])

    def interactWithBroker(self):
        '''
        Returns True to continue to main loop, false to stop & exit service
        '''
        # If no configuration is found, stop service
        if cfg is None:
            logger.fatal('No configuration found, stopping service')
            return False

        self.api = REST.Api(cfg['host'], cfg['masterKey'], cfg['ssl'])

        # Wait for Broker to be ready
        counter = 0
        while self.isAlive:
            try:
                # getNetworkInfo is a generator function
                netInfo = tuple(operations.getNetworkInfo())
                self.knownIps = dict(((i.mac, i.ip) for i in netInfo))
                ids = ','.join([i.mac for i in netInfo])
                if ids == '':
                    # Wait for any network interface to be ready
                    logger.debug('No valid network interfaces found, retrying in a while...')
                    raise Exception()
                logger.debug('Ids: {}'.format(ids))
                self.api.init(ids)
                # Set remote logger to notify log info to broker
                logger.setRemoteLogger(self.api)

                break
            except REST.InvalidKeyError:
                logger.fatal('Can\'t sync with broker: Invalid broker Master Key')
                return False
            except REST.UnmanagedHostError:
                # Maybe interface that is registered with broker is not enabled already?
                # Right now, we thing that the interface connected to broker is
                # the interface that broker will know, let's see how this works
                logger.fatal('This host is not managed by UDS Broker (ids: {})'.format(ids))
                return False  # On unmanaged hosts, there is no reason right now to continue running
            except Exception as e:
                logger.debug('Exception on network info: retrying')
                # Any other error is expectable and recoverable, so let's wait a bit and retry again
                # but, if too many errors, will log it (one every minute, for
                # example)
                counter += 1
                if counter % 60 == 0:  # Every 5 minutes, raise a log
                    logger.info('Trying to inititialize connection with broker (last error: {})'.format(exceptionToMessage(e)))
                # Wait a bit before next check
                self.doWait(5000)

        # Now try to run the "runonce" element
        runOnce = store.runApplication()
        if runOnce is not None:
            logger.info('Executing runOnce app: {}'.format(runOnce))
            if self.execute(runOnce, 'RunOnce') is True:
                # operations.reboot()
                return False

        # Broker connection is initialized, now get information about what to
        # do
        counter = 0
        while self.isAlive:
            try:
                logger.debug('Requesting information of what to do now')
                info = self.api.information()
                data = info.split('\r')
                if len(data) != 2:
                    logger.error('The format of the information message is not correct (got {})'.format(info))
                    raise Exception
                params = data[1].split('\t')
                if data[0] == 'rename':
                    try:
                        if len(params) == 1:  # Simple rename
                            logger.debug('Renaming computer to {}'.format(params[0]))
                            self.rename(params[0])
                        # Rename with change password for an user
                        elif len(params) == 4:
                            logger.debug('Renaming computer to {}'.format(params))
                            self.rename(params[0], params[1], params[2], params[3])
                        else:
                            logger.error('Got invalid parameter for rename operation: {}'.format(params))
                            return False
                        break
                    except Exception as e:
                        logger.error('Error at computer renaming stage: {}'.format(e.message))
                        return None  # Will retry complete broker connection if this point is reached
                elif data[0] == 'domain':
                    if len(params) != 5:
                        logger.error('Got invalid parameters for domain message: {}'.format(params))
                        return False  # Stop running service
                    self.joinDomain(params[0], params[1], params[2], params[3], params[4])
                    break
                else:
                    logger.error('Unrecognized action sent from broker: {}'.format(data[0]))
                    return False  # Stop running service
            except REST.UserServiceNotFoundError:
                logger.error('The host has lost the sync state with broker! (host uuid changed?)')
                return False
            except Exception as err:
                if counter % 60 == 0:
                    logger.warn('Too many retries in progress, though still trying (last error: {})'.format(exceptionToMessage(err)))
                counter += 1
                # Any other error is expectable and recoverable, so let's wait
                # a bit and retry again
                # Wait a bit before next check
                self.doWait(5000)

        if self.rebootRequested:
            try:
                operations.reboot()
            except Exception as e:
                logger.error('Exception on reboot: {}'.format(e.message))
            return False  # Stops service

        return True

    def checkIpsChanged(self):
        if self.api is None or self.api.uuid is None:
            return  # Not connected
        netInfo = tuple(operations.getNetworkInfo())
        for i in netInfo:
            # If at least one ip has changed
            if i.mac in self.knownIps and self.knownIps[i.mac] != i.ip:
                logger.info('Notifying ip change to broker (mac {}, from {} to {})'.format(i.mac, self.knownIps[i.mac], i.ip))
                try:
                    # Notifies all interfaces IPs
                    self.api.notifyIpChanges(((v.mac, v.ip) for v in netInfo))

                    # Regenerates Known ips
                    self.knownIps = dict(((v.mac, v.ip) for v in netInfo))

                    # And notify new listening address to broker
                    address = (self.knownIps[self.api.mac], self.httpServer.getPort())
                    # And new listening address
                    self.httpServer.restart(address)
                    # sends notification
                    self.api.notifyComm(self.httpServer.getServerUrl())

                except Exception as e:
                    logger.warn('Got an error notifiying IPs to broker: {} (will retry in a bit)'.format(e.message.decode('windows-1250', 'ignore')))

    def clientMessageProcessor(self, msg, data):
        logger.debug('Got message {}'.format(msg))
        if self.api is None:
            logger.info('Rest api not ready')
            return

        if msg == ipc.REQ_LOGIN:
            res = self.api.login(data).split('\t')
            # third parameter, if exists, sets maxSession duration to this.
            # First & second parameters are ip & hostname of connection source
            if len(res) >= 3:
                self.api.maxSession = int(res[2])  # Third parameter is max session duration
                msg = ipc.REQ_INFORMATION  # Senf information, requested or not, to client on login notification
        if msg == ipc.REQ_LOGOUT:
            self.api.logout(data)
            self.onLogout(data)
        if msg == ipc.REQ_INFORMATION:
            info = {}
            if self.api.idle is not None:
                info['idle'] = self.api.idle
            if self.api.maxSession is not None:
                info['maxSession'] = self.api.maxSession
            self.ipc.sendInformationMessage(info)

    def initIPC(self):
        # ******************************************
        # * Initialize listener IPC & REST threads *
        # ******************************************
        logger.debug('Starting IPC listener at {}'.format(IPC_PORT))
        self.ipc = ipc.ServerIPC(IPC_PORT, clientMessageProcessor=self.clientMessageProcessor)
        self.ipc.start()

        if self.api.mac in self.knownIps:
            address = (self.knownIps[self.api.mac], random.randrange(43900, 44000))
            logger.info('Starting REST listener at {}'.format(address))
            self.httpServer = httpserver.HTTPServerThread(address, self)
            self.httpServer.start()
            # And notify it to broker
            self.api.notifyComm(self.httpServer.getServerUrl())

    def endIPC(self):
        # Remove IPC threads
        if self.ipc is not None:
            try:
                self.ipc.stop()
            except Exception:
                logger.error('Couln\'t stop ipc server')
        if self.httpServer is not None:
            try:
                self.httpServer.stop()
            except Exception:
                logger.error('Couln\'t stop REST server')

    def endAPI(self):
        if self.api is not None:
            try:
                self.api.notifyComm(None)
            except Exception:
                logger.error('Couln\'t remove comms url from broker')

        self.notifyStop()

    # ***************************************************
    # Methods that ARE overriden by linux & windows Actor
    # ***************************************************
    def rename(self, name, user=None, oldPassword=None, newPassword=None):
        '''
        Invoked when broker requests a rename action
        MUST BE OVERRIDEN
        '''
        raise NotImplementedError('Method renamed has not been implemented!')

    def joinDomain(self, name, domain, ou, account, password):
        '''
        Invoked when broker requests a "domain" action
        MUST BE OVERRIDEN
        '''
        raise NotImplementedError('Method renamed has not been implemented!')

    # ****************************************
    # Methods that CAN BE overriden by actors
    # ****************************************
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

    def preConnect(self, user, protocol):
        '''
        Invoked when received a PRE Connection request via REST
        '''
        logger.debug('Pre-connect does nothing')
        return 'ok'

    def onLogout(self, user):
        logger.debug('On logout invoked for {}'.format(user))
