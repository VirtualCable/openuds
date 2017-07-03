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
import win32security  # @UnresolvedImport, pylint: disable=import-error
import win32net  # @UnresolvedImport, pylint: disable=import-error
import win32event  # @UnresolvedImport, pylint: disable=import-error
import win32com.client  # @UnresolvedImport,  @UnusedImport, pylint: disable=import-error
import pythoncom  # @UnresolvedImport, pylint: disable=import-error
import servicemanager  # @UnresolvedImport, pylint: disable=import-error
import subprocess
import os

from udsactor import operations
from udsactor import store
from udsactor.service import CommonService
from udsactor.service import initCfg

from udsactor.log import logger

from .SENS import SensLogon
from .SENS import logevent
from .SENS import SENSGUID_EVENTCLASS_LOGON
from .SENS import SENSGUID_PUBLISHER
from .SENS import PROGID_EventSubscription
from .SENS import PROGID_EventSystem

POST_CMD = 'c:\\windows\\post-uds.bat'


class UDSActorSvc(win32serviceutil.ServiceFramework, CommonService):
    '''
    This class represents a Windows Service for managing actor interactions
    with UDS Broker and Machine
    '''
    _svc_name_ = "UDSActor"
    _svc_display_name_ = "UDS Actor Service"
    _svc_description_ = "UDS Actor for machines managed by UDS Broker"
    # 'System Event Notification' is the SENS service
    _svc_deps_ = ['EventLog', 'SENS']

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        CommonService.__init__(self)
        self.hWaitStop = win32event.CreateEvent(None, 1, 0, None)
        self._user = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.isAlive = False
        win32event.SetEvent(self.hWaitStop)

    SvcShutdown = SvcStop

    def notifyStop(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STOPPED,
                              (self._svc_name_, ''))

    def doWait(self, miliseconds):
        win32event.WaitForSingleObject(self.hWaitStop, miliseconds)

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
        logger.info('Rebooting computer to activate new name {}'.format(name))
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
            if currDomain is not None:
                # logger.debug('Name: "{}" vs "{}", Domain: "{}" vs "{}"'.format(currName.lower(), name.lower(), currDomain.lower(), domain.lower()))
                logger.info(
                    'Machine {} is part of domain {}'.format(name, domain))
                self.setReady()
            else:
                operations.joinDomain(
                    domain, ou, account, password, executeInOneStep=False)
                self.reboot()
        else:
            operations.renameComputer(name)
            logger.info(
                'Rebooting computer got activate new name {}'.format(name))
            self.reboot()

    def joinDomain(self, name, domain, ou, account, password):
        ver = operations.getWindowsVersion()
        ver = ver[0] * 10 + ver[1]
        logger.debug('Starting joining domain {} with name {} (detected operating version: {})'.format(
            domain, name, ver))
        # If file c:\compat.bin exists, joind domain in two steps instead one

        # Accepts one step joinDomain, also remember XP is no more supported by
        # microsoft, but this also must works with it because will do a "multi
        # step" join
        if ver >= 60 and store.useOldJoinSystem() is False:
            self.oneStepJoin(name, domain, ou, account, password)
        else:
            logger.info('Using multiple step join because configuration requests to do so')
            self.multiStepJoin(name, domain, ou, account, password)

    def preConnect(self, user, protocol):
        logger.debug('Pre connect invoked')
        if protocol != 'rdp':  # If connection is not using rdp, skip adding user
            return 'ok'
        # Well known SSID for Remote Desktop Users
        REMOTE_USERS_SID = 'S-1-5-32-555'

        p = win32security.GetBinarySid(REMOTE_USERS_SID)
        groupName = win32security.LookupAccountSid(None, p)[0]

        useraAlreadyInGroup = False
        resumeHandle = 0
        while True:
            users, _, resumeHandle = win32net.NetLocalGroupGetMembers(None, groupName, 1, resumeHandle, 32768)
            if user in [u['name'] for u in users]:
                useraAlreadyInGroup = True
                break
            if resumeHandle == 0:
                break

        if useraAlreadyInGroup is False:
            logger.debug('User not in group, adding it')
            self._user = user
            try:
                userSSID = win32security.LookupAccountName(None, user)[0]
                win32net.NetLocalGroupAddMembers(None, groupName, 0, [{'sid': userSSID}])
            except Exception as e:
                logger.error('Exception adding user to Remote Desktop Users: {}'.format(e))
        else:
            self._user = None
            logger.debug('User {} already in group'.format(user))

        return 'ok'

    def onLogout(self, user):
        logger.debug('Windows onLogout invoked: {}, {}'.format(user, self._user))
        try:
            REMOTE_USERS_SID = 'S-1-5-32-555'
            p = win32security.GetBinarySid(REMOTE_USERS_SID)
            groupName = win32security.LookupAccountSid(None, p)[0]
        except Exception:
            logger.error('Exception getting Windows Group')
            return

        if self._user is not None:
            try:
                win32net.NetLocalGroupDelMembers(None, groupName, [self._user])
            except Exception as e:
                logger.error('Exception removing user from Remote Desktop Users: {}'.format(e))

    def SvcDoRun(self):
        '''
        Main service loop
        '''
        try:
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
            while True:
                brokerConnected = self.interactWithBroker()
                if brokerConnected is False:
                    logger.debug('Interact with broker returned false, stopping service after a while')
                    self.notifyStop()
                    win32event.WaitForSingleObject(self.hWaitStop, 5000)
                    return
                elif brokerConnected is True:
                    break

                # If brokerConnected returns None, repeat the cycle
                self.doWait(16000)  # Wait for a looong while

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

            self.initIPC()
        except Exception:  # Any init exception wil be caught, service must be then restarted
            logger.exception()
            logger.debug('Exiting service with failure status')
            os._exit(-1)  # pylint: disable=protected-access

        # ********************************
        # * Registers SENS subscriptions *
        # ********************************
        logevent('Registering ISensLogon')
        subscription_guid = '{41099152-498E-11E4-8FD3-10FEED05884B}'
        sl = SensLogon(self)
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

        # Execute script in c:\\windows\\post-uds.bat after interacting with broker, if no reboot is requested ofc
        # This will be executed only when machine gets "ready"
        try:
            if os.path.isfile(POST_CMD):
                subprocess.call([POST_CMD, ])
            else:
                logger.info('POST file not found & not executed')
        except Exception as e:
            # Ignore output of execution command
            logger.error('Executing post command give')

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
            if counter >= 15:  # Once every 15 seconds
                counter = 0
                try:
                    self.checkIpsChanged()
                except Exception as e:
                    logger.error('Error checking ip change: {}'.format(e))
            # In milliseconds, will break
            win32event.WaitForSingleObject(self.hWaitStop, 1000)

        logger.debug('Exited main loop, deregistering SENS')

        # *******************************************
        # * Remove SENS subscription before exiting *
        # *******************************************
        event_system.Remove(
            PROGID_EventSubscription, "SubscriptionID == " + subscription_guid)

        self.endIPC()  # Ends IPC servers
        self.endAPI()  # And deinitializes REST api if needed

        self.notifyStop()


if __name__ == '__main__':
    initCfg()
    win32serviceutil.HandleCommandLine(UDSActorSvc)
