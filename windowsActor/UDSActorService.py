import win32serviceutil
import win32service
import win32api
import win32event

import pythoncom
import win32com.client

import servicemanager
from SENS import *
import socket


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
            win32event.WaitForSingleObject(self.hWaitStop, 1000)  # In milliseconds

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
    win32serviceutil.HandleCommandLine(AppServerSvc)
