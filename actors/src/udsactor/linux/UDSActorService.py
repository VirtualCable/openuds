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

from udsactor import store
from udsactor import REST
from udsactor import operations
from udsactor import httpserver
from udsactor import ipc

from udsactor.log import logger

from .daemon import Daemon
from . import renamer

import socket
import time


IPC_PORT = 39188

cfg = None


class UDSActorSvc(Daemon):
    def __init__(self, args):
        Daemon.__init__(self, '/var/run/udsa.pid')
        self.isAlive = True
        socket.setdefaulttimeout(20)
        self.api = None
        self.ipc = None
        self.httpServer = None
        self.rebootRequested = False
        self.knownIps = []

    def setReady(self):
        self.api.setReady([(v.mac, v.ip) for v in operations.getNetworkInfo()])

    def rename(self, name, user=None, oldPassword=None, newPassword=None):
        '''
        Renames the computer, and optionally sets a password for an user
        before this
        '''

        # Check for password change request for an user
        if user is not None:
            logger.info('Setting password for user {}'.format(user))
            try:
                operations.changeUserPassword(user, oldPassword, newPassword)
            except Exception as e:
                # We stop here without even renaming computer, because the
                # process has failed
                raise Exception(
                    'Could not change password for user {} (maybe invalid current password is configured at broker): {} '.format(user, unicode(e)))

        renamer.rename(name)
        self.setReady()

    def interactWithBroker(self):
        '''
        Returns True to continue to main loop, false to stop & exit service
        '''
        # If no configuration is found, stop service
        if cfg is None:
            logger.fatal('No configuration found, stopping service')
            return False

        self.api = REST.Api(cfg['host'], cfg['masterKey'], cfg['ssl'], scrambledResponses=True)

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
                    logger.debug('No network interfaces found, retrying in a while...')
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
                return False
            except Exception as e:
                logger.debug('Exception caught: {}, retrying'.format(e.message.decode('windows-1250', 'ignore')))
                # Any other error is expectable and recoverable, so let's wait a bit and retry again
                # but, if too many errors, will log it (one every minute, for
                # example)
                counter += 1
                if counter % 60 == 0:  # Every 5 minutes, raise a log
                    logger.info('Trying to inititialize connection with broker (last error: {})'.format(e.message.decode('windows-1250', 'ignore')))
                # Wait a bit before next check
                time.sleep(1)

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
                            self.rename(params[0])
                        # Rename with change password for an user
                        elif len(params) == 4:
                            self.rename(params[0], params[1], params[2], params[3])
                        else:
                            logger.error('Got invalid parameter for rename operation: {}'.format(params))
                            return False
                        break
                    except Exception as e:
                        logger.error('Error at computer renaming stage: {}'.format(e.message))
                        return False
                else:
                    logger.error('Unrecognized action sent from broker: {}'.format(data[0]))
                    return False  # Stop running service
            except REST.UserServiceNotFoundError:
                logger.error('The host has lost the sync state with broker! (host uuid changed?)')
                return False
            except Exception:
                counter += 1
                if counter % 60 == 0:
                    logger.warn('Too many retries in progress, though still trying (last error: {})'.format(e))
                # Any other error is expectable and recoverable, so let's wait
                # a bit and retry again
                # Wait a bit before next check
                time.sleep(1)

        if self.rebootRequested:
            try:
                operations.reboot()
            except Exception as e:
                logger.error('Exception on reboot: {}'.format(e.message))
            return False  # Stops service

        return True

    def run(self):
        pass
