# _*_ coding: iso-8859-1 _*_

from __future__ import unicode_literals

import servicemanager
import win32com.client
import win32com.server.policy
import pythoncom

# based on python SENS example from http://timgolden.me.uk/python/win32_how_do_i/track-session-events.html

## from Sens.h
SENSGUID_PUBLISHER = "{5fee1bd6-5b9b-11d1-8dd2-00aa004abd5e}"
SENSGUID_EVENTCLASS_LOGON = "{d5978630-5b9f-11d1-8dd2-00aa004abd5e}"

## from EventSys.h
PROGID_EventSystem = "EventSystem.EventSystem"
PROGID_EventSubscription = "EventSystem.EventSubscription"

IID_ISensLogon = "{d597bab3-5b9f-11d1-8dd2-00aa004abd5e}"

class SensLogon(win32com.server.policy.DesignatedWrapPolicy):
    _com_interfaces_=[IID_ISensLogon]
    _public_methods_=[
        'Logon',
        'Logoff',
        'StartShell',
        'DisplayLock',
        'DisplayUnlock',
        'StartScreenSaver',
        'StopScreenSaver'
        ]

    def __init__(self, api):
        self._wrap_(self)
        self.api = api

    def Logon(self, *args):
        logevent('Logon : %s'%[args])

    def Logoff(self, *args):
        logevent('Logoff : %s'%[args])
        self.executer.logoff(*args)

    def StartShell(self, *args):
        logevent('StartShell : %s'%[args])

    def DisplayLock(self, *args):
        logevent('DisplayLock : %s'%[args])

    def DisplayUnlock(self, *args):
        logevent('DisplayUnlock : %s'%[args])

    def StartScreenSaver(self, *args):
        logevent('StartScreenSaver : %s'%[args])

    def StopScreenSaver(self, *args):
        logevent('StopScreenSaver : %s'%[args])


def logevent(msg, evtid=0xF000):
    """log into windows event manager
    """
    servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            evtid, #  generic message
            (msg, '')
            )

#def register():
    ## call the CoInitialize to allow the registration to run in an other
    ## thread
    #pythoncom.CoInitialize()

    #logevent('Registring ISensLogon')

    #sl=SensLogon()
    #subscription_interface=pythoncom.WrapObject(sl)

    #event_system=win32com.client.Dispatch(PROGID_EventSystem)

    #event_subscription=win32com.client.Dispatch(PROGID_EventSubscription)
    #event_subscription.EventClassID=SENSGUID_EVENTCLASS_LOGON
    #event_subscription.PublisherID=SENSGUID_PUBLISHER
    #event_subscription.SubscriptionName='Python subscription'
    #event_subscription.SubscriberInterface=subscription_interface

    #event_system.Store(PROGID_EventSubscription, event_subscription)

    ##pythoncom.PumpMessages()
    ##logevent('ISensLogon stopped')
