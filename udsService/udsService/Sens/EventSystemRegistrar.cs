using System.Diagnostics;
using System.Runtime.InteropServices;
using EventSystemLib;
using System;
using SensEvents;
using log4net;

namespace uds.Services.Sens
{
    //In the ManagesSENS namespace
    [ComImport, Guid("4E14FBA2-2E22-11D1-9964-00C04FBBB345")]
    class EventSystem { }
    [ComImport, Guid("7542E960-79C7-11D1-88F9-0080C7D771BF")]
    class EventSubcription { }
    [ComImport, Guid("AB944620-79C6-11d1-88F9-0080C7D771BF")]
    class EventPublisher { }
    [ComImport, Guid("cdbec9c0-7a68-11d1-88f9-0080c7d771bf")]
    class EventClass { }

    class EventSystemRegistrar
    {
        private static ILog logger = LogManager.GetLogger(typeof(EventSystemRegistrar));

        private const string PROGID_EventSubscription = "EventSystem.EventSubscription";
        static EventSystemRegistrar() { }

        private static IEventSystem es = null;
        private static IEventSystem EventSystem
        {
            get
            {
                if (es == null)
                    es = new EventSystem() as IEventSystem;
                return es;
            }
        }

        public static void SubscribeToEvents(string description, string subscriptionName, string
         subscriptionID, object subscribingObject, Type subscribingType)
        {
            // activate subscriber
            try
            {
                //create and populate a subscription object
                IEventSubscription sub = new EventSubcription() as IEventSubscription;
                sub.Description = description;
                sub.SubscriptionName = subscriptionName;
                sub.SubscriptionID = subscriptionID;
                //Get the GUID from the ISensLogon interface
                sub.InterfaceID = GetInterfaceGuid(subscribingType);
                sub.SubscriberInterface = subscribingObject;
                //Store the actual Event.
                EventSystem.Store(PROGID_EventSubscription, sub);
            }
            catch (Exception ex)
            {
                logger.Error("Exception cauthg subscribing to SENS events: ", ex);
            }
        }

        private static string GetInterfaceGuid(Type theType)
        {
            object[] attributes = theType.GetCustomAttributes(typeof(GuidAttribute), true);
            if (attributes.Length > 0)
            {
                return "{" + ((GuidAttribute)attributes[0]).Value + "}";
            }
            else
            {
                logger.Error("GuidedAttribute not present on the type");
                throw new ArgumentException("GuidAttribute not present on the Type.", "theType");
            }
        }

        public static void UnsubscribeToEvents(string subscriptionID)
        {
            try
            {
                string strCriteria = "SubscriptionID == " + subscriptionID;
                int errorIndex = 0;
                EventSystem.Remove("EventSystem.EventSubscription", strCriteria, out errorIndex);
            }
            catch (Exception ex)
            {
                logger.Error("Exception cauthg unsubscribing to SENS events: ", ex);
            }
        }
    }

    public delegate void SensLogonEventHandler(string userName);
    public class SensLogon
    {
        private static ILog logger = LogManager.GetLogger(typeof(SensLogon));

        private static SensLogonInterop eventCatcher;
        static SensLogon() { }

        private class SensLogonInterop : ISensLogon, IDisposable
        {
            private static ILog logger = LogManager.GetLogger(typeof(SensLogonInterop));

            private const string SubscriptionViewerName = "ManagedSENS.SensLogonInterop";
            // generate a subscriptionID 
            private static string SubscriptionViewerID = "{" + typeof(SensLogonInterop).GUID.ToString().ToUpper() + "}"; 
            private const string SubscriptionViewerDesc = "ManagedSENS Event Subscriber";

            private bool registered;

            public SensLogonInterop()
            {
                registered = false;
                EventSystemRegistrar.SubscribeToEvents(SubscriptionViewerDesc, SubscriptionViewerName,
                 SubscriptionViewerID, this, typeof(ISensLogon));
                registered = true;
                logger.Debug("Sens registered");
            }

            ~SensLogonInterop()
            {
                this.Dispose(false);
            }

            public void Dispose()
            {
                this.Dispose(true);
            }

            protected void Dispose(bool isExplicit)
            {
                this.Deactivate();
            }

            private void Deactivate()
            {
                if (registered)
                {
                    EventSystemRegistrar.UnsubscribeToEvents(SubscriptionViewerID);
                    registered = false;
                    logger.Debug("Sens unregistered");
                }
            }

            public void DisplayLock(string bstrUserName)
            {
                logger.Debug("SENS Displaylock invoked for user " + bstrUserName);
                SensLogon.OnDisplayLock(bstrUserName);
            }
            public void DisplayUnlock(string bstrUserName)
            {
                logger.Debug("SENS DisplayUnloock invoked for user " + bstrUserName);
                SensLogon.OnDisplayUnlock(bstrUserName);
            }

            public void Logoff(string bstrUserName)
            {
                logger.Debug("SENS Logoff invoked for user " + bstrUserName);
                SensLogon.OnLogoff(bstrUserName);
            }

            public void Logon(string bstrUserName)
            {
                logger.Debug("SENS Logon invoked for user " + bstrUserName);
                SensLogon.OnLogon(bstrUserName);
            }

            public void StartScreenSaver(string bstrUserName)
            {
                logger.Debug("SENS StartScreenSaver invoked for user " + bstrUserName);
                SensLogon.OnStartScreenSaver(bstrUserName);
            }

            public void StartShell(string bstrUserName)
            {
                logger.Debug("SENS StartShell invoked for user " + bstrUserName);
                SensLogon.OnStartShell(bstrUserName);
            }

            public void StopScreenSaver(string bstrUserName)
            {
                logger.Debug("SENS StopScreenSaver invoked for user " + bstrUserName);
                SensLogon.OnStopScreenSaver(bstrUserName);
            }
        }

        private static int registerCount = 0;
        private static bool IsRegistered
        {
            get
            {
                return (registerCount > 0);
            }
        }

        private static SensLogonEventHandler RegisterEvent(SensLogonEventHandler original,
         SensLogonEventHandler newDel)
        {
            bool shouldRegister = (original == null);
            original = original + newDel;
            if (shouldRegister)
            {
                if (registerCount <= 0)
                {
                    if (SensLogon.eventCatcher == null)
                        SensLogon.eventCatcher = new SensLogonInterop();
                    registerCount = 1;
                }
                else
                {
                    //Just count them.
                    registerCount++;
                }
            }
            return original;
        }

        private static SensLogonEventHandler UnregisterEvent(SensLogonEventHandler original,
         SensLogonEventHandler oldDel)
        {
            original = original - oldDel;
            if (original == null)
            {
                registerCount--;
                if (registerCount == 0)
                {
                    //unregister for those events.
                    SensLogon.eventCatcher.Dispose();
                    SensLogon.eventCatcher = null;
                }
            }
            return original;
        }

        private static void exec(string name, SensLogonEventHandler ev, string bStrUsername)
        {
            if (ev != null)
            {
                try
                {
                    logger.Debug("Executing " + name + " for user " + bStrUsername );
                    ev(bStrUsername);
                }
                catch (Exception ex)
                {
                    logger.Error("Exception cauthg executing sens event " + name, ex);
                }
            }
        }

        protected static void OnDisplayLock(string bstrUserName)
        {
            exec("DisplayLock", SensLogon.displayLock, bstrUserName);
        }
        protected static void OnDisplayUnlock(string bstrUserName)
        {
            exec("DisplayUnlock", SensLogon.displayUnlock, bstrUserName);
        }
        protected static void OnLogoff(string bstrUserName)
        {
            exec("Logoff", SensLogon.logoff, bstrUserName);
        }
        protected static void OnLogon(string bstrUserName)
        {
            exec("Logon", SensLogon.logon, bstrUserName);
        }
        protected static void OnStartScreenSaver(string bstrUserName)
        {
            exec("StartScreenSaver", SensLogon.startScreenSaver, bstrUserName);
        }
        protected static void OnStartShell(string bstrUserName)
        {
            exec("Startshell", SensLogon.startShell, bstrUserName);
        }
        protected static void OnStopScreenSaver(string bstrUserName)
        {
            exec("StopScreenSaver", SensLogon.stopScreenSaver, bstrUserName);
        }


        private static SensLogonEventHandler displayLock = null;
        private static SensLogonEventHandler displayUnlock = null;
        private static SensLogonEventHandler logoff = null;
        private static SensLogonEventHandler logon = null;
        private static SensLogonEventHandler startScreenSaver = null;
        private static SensLogonEventHandler startShell = null;
        private static SensLogonEventHandler stopScreenSaver = null;


        public static event SensLogonEventHandler DisplayLock
        {
            add  { SensLogon.displayLock = SensLogon.RegisterEvent(SensLogon.displayLock, value); }
            remove  { SensLogon.displayLock = SensLogon.UnregisterEvent(SensLogon.displayLock, value); }
        }

        public static event SensLogonEventHandler DisplayUnlock
        {
            add { SensLogon.displayUnlock = SensLogon.RegisterEvent(SensLogon.displayUnlock, value); }
            remove { SensLogon.displayUnlock = SensLogon.UnregisterEvent(SensLogon.displayUnlock, value); }
        }

        public static event SensLogonEventHandler Logoff
        {
            add { SensLogon.logoff = SensLogon.RegisterEvent(SensLogon.logoff, value); }
            remove { SensLogon.logoff = SensLogon.UnregisterEvent(SensLogon.logoff, value); }
        }

        public static event SensLogonEventHandler Logon
        {
            add { SensLogon.logon = SensLogon.RegisterEvent(SensLogon.logon, value); }
            remove { SensLogon.logon = SensLogon.UnregisterEvent(SensLogon.logon, value); }
        }

        public static event SensLogonEventHandler StartScreenSaver
        {
            add { SensLogon.startScreenSaver = SensLogon.RegisterEvent(SensLogon.startScreenSaver, value); }
            remove { SensLogon.startScreenSaver = SensLogon.UnregisterEvent(SensLogon.startScreenSaver, value); }
        }

        public static event SensLogonEventHandler StartShell
        {
            add { SensLogon.startShell = SensLogon.RegisterEvent(SensLogon.startShell, value); }
            remove { SensLogon.startShell = SensLogon.UnregisterEvent(SensLogon.startShell, value); }
        }

        public static event SensLogonEventHandler StopScreenSaver
        {
            add { SensLogon.stopScreenSaver = SensLogon.RegisterEvent(SensLogon.stopScreenSaver, value); }
            remove { SensLogon.stopScreenSaver = SensLogon.UnregisterEvent(SensLogon.stopScreenSaver, value); }
        }


    }

}

