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
# pylint: disable=unused-wildcard-import, wildcard-import

import win32serviceutil  # @UnresolvedImport, pylint: disable=import-error
import win32service  # @UnresolvedImport, pylint: disable=import-error
import win32event  # @UnresolvedImport, pylint: disable=import-error
import win32com.client  # @UnresolvedImport,  @UnusedImport, pylint: disable=import-error
import pythoncom  # @UnresolvedImport, pylint: disable=import-error
import servicemanager  # @UnresolvedImport, pylint: disable=import-error

import socket
import random

from udsactor import store
from udsactor import REST
from udsactor import operations
from udsactor import httpserver
from udsactor import ipc

from udsactor.windows.SENS import *  # @UnusedWildImport
from udsactor.log import logger

IPC_PORT = 39188

cfg = None


def initCfg():
    global cfg
    cfg = store.readConfig()

    if logger.logger.isWindows():
        # Logs will also go to windows event log for services
        logger.logger.serviceLogger = True

    if cfg is not None:
        logger.setLevel(cfg.get('logLevel', 20000))
    else:
        logger.setLevel(20000)


class UDSActorSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = "UDSActor"
    _svc_display_name_ = "UDS Actor Service"
    _svc_description_ = "UDS Actor for machines managed by UDS Broker"
    # 'System Event Notification' is the SENS service
    _svc_deps_ = ['EventLog', 'SENS']

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 1, 0, None)
        self.isAlive = True
        socket.setdefaulttimeout(20)
        self.api = None
        self.ipc = None
        self.httpServer = None
        self.rebootRequested = False
        self.knownIps = []

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.isAlive = False
        win32event.SetEvent(self.hWaitStop)

    SvcShutdown = SvcStop

    def notifyStop(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STOPPED,
                              (self._svc_name_, ''))

    def reboot(self):
        self.rebootRequested = True

    def setReady(self):
        self.api.setReady([(v.mac, v.ip) for v in operations.getNetworkInfo()])

    def rename(self, name, user=None, oldPassword=None, newPassword=None):
        '''
        Renames the computer, and optionally sets a password for an user
        before this
        '''
        hostName = operations.getComputerName()

        if hostName.lower() == name.lower():
            logger.info('Computer name is now {}'.format(hostName))
            self.setReady()
            return

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

        operations.renameComputer(name)
        # Reboot just after renaming
        logger.info('Rebooting computer got activate new name {}'.format(name))
        self.reboot()

    def oneStepJoin(self, name, domain, ou, account, password):
        '''
        Ejecutes the join domain in exactly one step
        '''
        currName = operations.getComputerName()
        # If name is desired, simply execute multiStepJoin, because computer
        # name will not change
        if currName.lower() == name.lower():
            self.multiStepJoin(name, domain, ou, account, password)
        else:
            operations.renameComputer(name)
            logger.debug('Computer renamed to {} without reboot'.format(name))
            operations.joinDomain(
                domain, ou, account, password, executeInOneStep=True)
            logger.debug(
                'Requested join domain {} without errors'.format(domain))
            self.reboot()

    def multiStepJoin(self, name, domain, ou, account, password):
        currName = operations.getComputerName()
        if currName.lower() == name.lower():
            currDomain = operations.getDomainName()
            if currDomain is not None and currDomain.lower() == domain.lower():
                logger.info(
                    'Machine {} is part of domain {}'.format(name, domain))
                self.setReady()
            else:
                operations.joinDomain(
                    domain, ou, account, password, executeInOneStep=False)
        else:
            operations.renameComputer(name)
            logger.info(
                'Rebooting computer got activate new name {}'.format(name))
            self.reboot()

    def joinDomain(self, name, domain, ou, account, password):
        ver = operations.getWindowsVersion()
        ver = ver[0] * 10 + ver[1]
        logger.info('Starting joining domain {} with name {} (detected operating version: {})'.format(
            domain, name, ver))
        # Accepts one step joinDomain, also remember XP is no more supported by
        # microsoft, but this also must works with it because will do a "multi
        # step" join
        if ver >= 60:
            self.oneStepJoin(name, domain, ou, account, password)
        else:
            self.multiStepJoin(name, domain, ou, account, password)

    def interactWithBroker(self):
        '''
        Returns True to continue to main loop, false to stop & exit service
        '''
        # If no configuration is found, stop service
        if cfg is None:
            logger.debug('No configuration found, stopping service')
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
                logger.debug('Exception caugh: {}, retrying'.format(e.message.decode('windows-1250', 'ignore')))
                # Any other error is expectable and recoverable, so let's wait a bit and retry again
                # but, if too many errors, will log it (one every minute, for
                # example)
                counter += 1
                if counter % 60 == 0:  # Every 5 minutes, raise a log
                    logger.info('Trying to inititialize connection with broker (last error: {})'.format(e.message.decode('windows-1250', 'ignore')))
                # Wait a bit before next check
                win32event.WaitForSingleObject(self.hWaitStop, 5000)

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
                elif data[0] == 'domain':
                    if len(params) != 5:
                        logger.error('Got invalid parameters for domain message: {}'.format(params))
                        return False
                    self.joinDomain(params[0], params[1], params[2], params[3], params[4])
                    break
                else:
                    logger.error('Unrecognized action sent from broker: {}'.format(data[0]))
                    return False  # Stop running service
            except REST.UserServiceNotFoundError:
                logger.error('The host has lost the sync state with broker! (host uuid changed?)')
                return False
            except Exception:
                counter += 1
                if counter % 60 == 0:
                    logger.warn('Too many retries in progress, though still trying (last error: {})'.format(e.message.decode('windows-1250', 'ignore')))
                # Any other error is expectable and recoverable, so let's wait
                # a bit and retry again
                # Wait a bit before next check
                win32event.WaitForSingleObject(self.hWaitStop, 1000)

        if self.rebootRequested:
            try:
                operations.reboot()
            except Exception as e:
                logger.error('Exception on reboot: {}'.format(e.message))
            return False  # Stops service

        return True

    def checkIpsChanged(self):
        netInfo = tuple(operations.getNetworkInfo())
        for i in netInfo:
            # If at least one ip has changed
            if i.mac in self.knownIps and self.knownIps[i.mac] != i.ip:
                logger.info('Notifying ip change to broker (mac {}, from {} to {})'.format(i.mac, self.knownIps[i.mac], i.ip))
                try:
                    # Notifies all interfaces IPs
                    self.api.notifyIpChanges(((v.mac, v.ip) for v in netInfo))
                    # Regenerates Known ips
                    self.knownIps = dict(((i.mac, i.ip) for i in netInfo))
                except Exception as e:
                    logger.warn('Got an error notifiying IPs to broker: {} (will retry in a bit)'.format(e.message.decode('windows-1250', 'ignore')))

    def SvcDoRun(self):
        '''
        Main service loop
        '''
        initCfg()

        logger.debug('running SvcDoRun')
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))

        # call the CoInitialize to allow the registration to run in an other
        # thread
        logger.debug('Initializing com...')
        pythoncom.CoInitialize()

        # ********************************************************
        # * Ask brokers what to do before proceding to main loop *
        # ********************************************************
        if self.interactWithBroker() is False:
            logger.debug('Interact with broker returned false, stopping service after a while')
            self.notifyStop()
            win32event.WaitForSingleObject(self.hWaitStop, 5000)
            return

        if self.isAlive is False:
            logger.debug('The service is not alive after broker interaction, stopping it')
            self.notifyStop()
            return

        if self.rebootRequested is True:
            logger.debug('Reboot has been requested, stopping service')
            self.notifyStop()
            return

        # ******************************************
        # * Initialize listener IPC & REST threads *
        # ******************************************
        logger.debug('Starting IPC listener at {}'.format(IPC_PORT))
        self.ipc = ipc.ServerIPC(IPC_PORT)
        self.ipc.start()

        if self.api.mac in self.knownIps:
            address = (self.knownIps[self.api.mac], random.randrange(32000, 64000))
            logger.debug('Starting REST listener at {}'.format(address))
            self.httpServer = httpserver.HTTPServerThread(address, self.ipc)
            self.httpServer.start()
            # And notify it to broker
            self.api.notifyComm(self.httpServer.getServerUrl())

        # ********************************
        # * Registers SENS subscriptions *
        # ********************************
        logevent('Registring ISensLogon')
        subscription_guid = '{41099152-498E-11E4-8FD3-10FEED05884B}'
        sl = SensLogon(self.api)
        subscription_interface = pythoncom.WrapObject(sl)

        event_system = win32com.client.Dispatch(PROGID_EventSystem)

        event_subscription = win32com.client.Dispatch(PROGID_EventSubscription)
        event_subscription.EventClassID = SENSGUID_EVENTCLASS_LOGON
        event_subscription.PublisherID = SENSGUID_PUBLISHER
        event_subscription.SubscriptionName = 'UDS Actor subscription'
        event_subscription.SubscriptionID = subscription_guid
        event_subscription.SubscriberInterface = subscription_interface

        event_system.Store(PROGID_EventSubscription, event_subscription)

        logger.debug('Registered SENS, running main loop')

        # *********************
        # * Main Service loop *
        # *********************
        # Counter used to check ip changes only once every 10 seconds, for
        # example
        counter = 0
        while self.isAlive:
            counter += 1
            # Process SENS messages, This will be a bit asyncronous (1 second
            # delay)
            pythoncom.PumpWaitingMessages()
            # if counter % 10 == 0:
            #    self.checkIpsChanged()
            # In milliseconds, will break
            win32event.WaitForSingleObject(self.hWaitStop, 1000)

        logger.debug('Exited main loop, deregistering SENS')

        # *******************************************
        # * Remove SENS subscription before exiting *
        # *******************************************
        event_system.Remove(
            PROGID_EventSubscription, "SubscriptionID == " + subscription_guid)

        # Remove IPC threads
        if self.ipc is not None:
            try:
                self.ipc.stop()
            except:
                logger.error('Couln\'t stop ipc server')
        if self.httpServer is not None:
            try:
                self.httpServer.stop()
            except:
                logger.error('Couln\'t stop REST server')

        if self.api is not None:
            try:
                self.api.notifyComm(None)
            except:
                logger.error('Couln\'t remove comms url from broker')

        self.notifyStop()


if __name__ == '__main__':
    initCfg()
    win32serviceutil.HandleCommandLine(UDSActorSvc)
