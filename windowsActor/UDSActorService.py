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

import win32serviceutil
import win32service
import win32api
import win32event

import pythoncom
import win32com.client

import servicemanager
from SENS import *
from store import readConfig
import socket

from management import *

cfg = None

class AppServerSvc (win32serviceutil.ServiceFramework):
    _svc_name_ = "UDSActor"
    _svc_display_name_ = "UDS Actor Service"
    _svc_description_ = "UDS Actor for machines managed by UDS Broker"
    _svc_deps_ = ['EventLog','SENS'] # 'System Event Notification' is the SENS service

    def __init__(self,args):
        win32serviceutil.ServiceFramework.__init__(self,args)
        self.hWaitStop = win32event.CreateEvent(None,0,0,None)
        self.isAlive = True
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.isAlive = False
        win32event.SetEvent(self.hWaitStop)

    SvcShutdown = SvcStop

    def interactWithBroker(self):
        '''
        Returns True to continue to main loop, false to stop & exit service
        '''
        return True

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_,''))

        if cfg is None:
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return

        # ********************************************************
        # * Ask brokers what to do before proceding to main loop *
        # ********************************************************
        if self.interactWithBroker() is False:
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return

        # ********************************
        # * Registers SENS subscriptions *
        # ********************************

        # call the CoInitialize to allow the registration to run in an other
        # thread
        pythoncom.CoInitialize()

        logevent('Registring ISensLogon')
        subscription_guid = '{41099152-498E-11E4-8FD3-10FEED05884B}'
        sl = SensLogon()
        subscription_interface=pythoncom.WrapObject(sl)

        event_system=win32com.client.Dispatch(PROGID_EventSystem)

        event_subscription=win32com.client.Dispatch(PROGID_EventSubscription)
        event_subscription.EventClassID=SENSGUID_EVENTCLASS_LOGON
        event_subscription.PublisherID=SENSGUID_PUBLISHER
        event_subscription.SubscriptionName='UDS Actor subscription'
        event_subscription.SubscriptionID = subscription_guid
        event_subscription.SubscriberInterface=subscription_interface

        event_system.Store(PROGID_EventSubscription, event_subscription)

        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, 0xF000, ('Running Service Main Loop', ''))

        # *********************
        # * Main Service loop *
        # *********************
        while self.isAlive:
            pythoncom.PumpWaitingMessages() # Process SENS messages, This will be a bit asyncronous (1 second delay)
            win32event.WaitForSingleObject(self.hWaitStop, 1000)  # In milliseconds, will break

        # *******************************************
        # * Remove SENS subscription before exiting *
        # *******************************************
        event_system.Remove(PROGID_EventSubscription, "SubscriptionID == "  + subscription_guid)

        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STOPPED,
                              (self._svc_name_,''))

        try:
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        except Exception:
            pass


if __name__ == '__main__':
    # cfg = readConfig()
    win32serviceutil.HandleCommandLine(AppServerSvc)
