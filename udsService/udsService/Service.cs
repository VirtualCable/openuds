using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Diagnostics;
using System.ServiceProcess;
using System.Threading;
using log4net;

namespace uds.Services 
{
    public class Service : System.ServiceProcess.ServiceBase
    {
        private static ILog logger = LogManager.GetLogger(typeof(Service));
        const int secsDelay = 5;

        private Thread _thread;
        private ManualResetEvent _stopEvent;
        private TimeSpan _delay;
        private bool _reboot;

        private static void SensLogon_Logon(string userName)
        {
            logger.Info("User " + userName + " has logged in");
            rpc.Logon(userName);
        }


        private static void SensLogon_Logout(string userName)
        {
            logger.Info("User " + userName + " has logged out");
            rpc.Logoff(userName);
        }

        public Service()
        {
            ServiceName = "UDS Actor";
            _thread = null;
            _stopEvent = null;
            _delay = new TimeSpan(0, 0, 0, secsDelay, 0);
            _reboot = false;
        }

        protected override void OnStart(string[] args)
        {
            logger.Debug("Initiated OnStart of service");
            ThreadStart start = new ThreadStart(this.ParallelThread);
            _thread = new Thread(start);
            _stopEvent = new ManualResetEvent(false);
            (_thread).Start();

            // Prepare SENS events
            Sens.SensLogon.Logon += SensLogon_Logon;
            Sens.SensLogon.Logoff += SensLogon_Logout;

            logger.Debug("Invoking base OnStart");
            // Invoke base OnStart
            base.OnStart(args);
        }

        protected override void OnStop()
        {
            logger.Debug("Initiated service shutdown");
            // Signal thread if already running
            _stopEvent.Set();
            // Prepare SENS events
            Sens.SensLogon.Logon -= SensLogon_Logon;
            Sens.SensLogon.Logoff -= SensLogon_Logout;

            _thread.Join((2 + secsDelay) * 1000);

            base.OnStop();
        }

        private void ParallelThread()
        {
            logger.Debug("Initiated Service main");

            // We have to wait till we have ip
            List<Info.Computer.InterfaceInfo> interfaces = null;
            while (interfaces == null)
            {
                logger.Debug("Trying to get network info..");
                try
                {
                    interfaces = Info.Computer.GetInterfacesInfo();
                }
                catch (Exception e)
                {
                    logger.Debug("Exception!!!",e);
                }
                if (interfaces == null)
                {
                    bool exit = _stopEvent.WaitOne(_delay);
                    if (exit)
                    {
                        logger.Debug("Exit requested waiting for interfaces");
                        return;
                    }
                }
            }
            // We have now interfaces info, intialize the connection and try to connect
            // In fact, we do not use the interfaces received except for logging, initialize gets their own data from there
            logger.Debug("Interfaces: " + string.Join(",", interfaces.ConvertAll<String>(i => i.mac + "=" + i.ip).ToArray()));
            rpc.Initialize(config.broker, config.ssl);
            string action = null;
            while (action == null)
            {
                logger.Debug("Trying to contact server to get action");
                rpc.ResetId(); // So we get interfaces info every time we try to contact broker
                action = rpc.GetInfo();  // Get action to execute
                if (action == null)
                {
                    bool exit = _stopEvent.WaitOne(_delay);
                    if (exit)
                    {
                        logger.Debug("Exit requested waiting for broker info");
                        return;
                    }
                }
            }

            if (action == "")
            {
                logger.Debug("Unmanaged machine, exiting...");
                // Reset rpc so next calls are simply ignored...
                rpc.ResetManager();
                return;
            }

            // Important note:
            // Remove ":" as separator, due to the posibility that ":"  can be used as part of a password
            // Old ":" is now '\r'
            // In order to keep compatibility, getInfo will invoke rcp "information", so old actors "versions"
            // will keep invoking "info" and return the old ":" separator way

            // Message is in the form "action\rparams", where we can identify:
            // rename\rcomputername  --- > Just rename
            // rename\rcomputername\tuser\toldPass\tnewPass --> Rename with user password changing
            // domain:computername\tdomain\tou\tuserToAuth\tpassToAuth --> Rename and add machine to domain
            string[] data = action.Split('\r');
            if (data.Length != 2)
            {
                logger.Error("Unrecognized instruction: \"" + action + "\"");
                rpc.ResetManager(); // Invalidates manager, cause we don't recognized it
                return;
            }

            string[] parms = data[1].Split('\t');

            switch (data[0])
            {
                case "rename":
                    if (parms.Length == 1 )
                        // Do not have to change user password
                        Rename(parms[0], null, null, null);
                    else if (parms.Length == 4)
                        // Rename, and also change user password
                        Rename(parms[0], parms[1], parms[2], parms[2]);
                    else
                    {
                        logger.Error("Unrecognized parameters: " + data[1]);
                        rpc.ResetManager();
                        return;
                    }

                    break;
                case "domain":
                    {
                        if (parms.Length != 5)
                        {
                            logger.Error("Unrecognized parameters: " + data[1]);
                            rpc.ResetManager(); // Invalidates manager, cause we don't recognized it
                            return;
                        }
                        JoinDomain(parms[0], parms[1], parms[2], parms[3], parms[4]);
                    }
                    break;
                default:
                    logger.Error("Unrecognized action: \"" + data[0] + "\"");
                    rpc.ResetManager(); // Invalidates manager, cause we don't recognized it
                    return;
            }
            // Reboot process or no process at all, exit
            if (_reboot || rpc.Manager == null)
            {
                logger.Debug("Returning, reboot = '" + _reboot.ToString() + "' + rcp.Manager = '" + rpc.Manager.ToString() + "'");
                return;
            }
            logger.Debug("Main loop waiting for ip change");
            // Now, every secs delay, get if the interfaces ips changes and notify service
            Dictionary<string, string> knownIps = new Dictionary<string, string>();
            try
            {
                foreach (Info.Computer.InterfaceInfo i in Info.Computer.GetInterfacesInfo())
                    knownIps.Add(i.mac, i.ip);
            }
            catch (Exception e)
            {
                logger.Error("Could not accesss ip adresses!!", e);
                return;
            }

            while (true)
            {
                try
                {
                    foreach (Info.Computer.InterfaceInfo i in Info.Computer.GetInterfacesInfo())
                    {

                        /*logger.Debug(knownIps.ContainsKey(i.mac));
                        logger.Debug(i.mac + ", " + i.ip);*/

                        if (knownIps.ContainsKey(i.mac) && knownIps[i.mac] != i.ip)
                        {
                            if (rpc.NotifyIPChange() == true) // if Could not send ip addresses, try again in a while, else save it
                                knownIps[i.mac] = i.ip;
                            else
                                logger.Info("Could not notify ip, will retry later");
                            break;
                        }
                    }
                }
                catch (Exception e)
                {
                    logger.Error("Error getting interfaces", e);
                }
                bool exit = _stopEvent.WaitOne(_delay);
                if (exit)
                {
                    logger.Debug("Exit requested on main loop");
                    return;
                }
            }
        }

        private void Rename(string name, string user, string oldPass, string newPass)
        {
            logger.Info("Requested renaming of computer to \"" + name + "\"");
            // name and newName can be different case, but still same
            Info.DomainInfo info = Info.Computer.GetDomainInfo();

            if ( string.Equals(info.ComputerName, name, StringComparison.CurrentCultureIgnoreCase))
            {
                logger.Debug("Computer do not needs to be renamed");
                rpc.SetReady();
                return;
            }

            // Set user password if provided
            if (user != null)
            {
                if (Operation.ChangeUserPassword(user, oldPass, newPass) == false)
                {
                    logger.Error("Could not change password to " + newPass + " for user " + user);
                    rpc.ResetManager();
                    return;
                }
            }

            if (Operation.RenameComputer(name) == false)
            {
                logger.Error("Could not rename machine to \"" + name + "\"");
                rpc.ResetManager();
                return;
            }

            Reboot();
        }


        private void OneStepJoin(string name, string domain, string ou, string account, string pass)
        {
            logger.Info("Requested one step join of computer to \"" + domain + "\" with name \"" + name + "\" under ou \"" + ou + "\"" );
            // name and newName can be different case, but still same
            Info.DomainInfo info = Info.Computer.GetDomainInfo();
            if (string.Equals(info.ComputerName, name, StringComparison.CurrentCultureIgnoreCase))
            {
                // We should be already in the domain, if not, will try second step of "multiStepJoin"
                if(info.Status == Info.DomainInfo.NetJoinStatus.NetSetupDomainName ) // Already in domain
                {
                    logger.Debug("Machine already in the domain");
                    rpc.SetReady();
                    return;
                }
                // Call multiStep, cause name is good but domain don't
                MultiStepJoin(name, domain, ou, account, pass);
                return;
            }
            // Needs to rename + join
            if (Operation.RenameComputer(name) == false)
            {
                logger.Error("Could not rename machine to \"" + name + "\"");
                rpc.ResetManager();
                return;
            }
            // Now try to join domain
            if (Operation.JoinDomain(domain, ou, account, pass, true) == false)
            {
                logger.Error("Could not join domain \"" + domain + "\", ou \"" + ou + "\"");
                rpc.ResetManager();
                return;
            }
            // Fine, now reboot
            Reboot();
        }

        private void MultiStepJoin(string name, string domain, string ou, string account, string pass)
        {
            logger.Info("Requested two step join of computer to \"" + domain + "\" with name \"" + name + "\" under ou \"" + ou + "\"");
            Info.DomainInfo info = Info.Computer.GetDomainInfo();
            if (string.Equals(info.ComputerName, name, StringComparison.CurrentCultureIgnoreCase))
            {
                // Name already, now see if already in domain
                if (info.Status == Info.DomainInfo.NetJoinStatus.NetSetupDomainName) // Already in domain
                {
                    logger.Debug("Machine already in the domain");
                    rpc.SetReady();
                    return;
                }
                // Now try to join domain
                if (Operation.JoinDomain(domain, ou, account, pass, true) == false)
                {
                    logger.Error("Could not join domain \"" + domain + "\", ou \"" + ou + "\"");
                    rpc.ResetManager();
                    return;
                }
            }
            else
            {
                // Try to rename machine
                if (Operation.RenameComputer(name) == false)
                {
                    logger.Error("Could not rename machine to \"" + name + "\"");
                    rpc.ResetManager();
                    return;
                }
            }
            // Fine, now reboot
            Reboot();
        }

        private void JoinDomain(string name, string domain, string ou, string account, string pass)
        {
            // Test to see if it is windows 7
            logger.Info("Joining domain " + domain + ", under ou " + ou);
            Info.OsInfo winVer = new Info.OsInfo();
            if (winVer.Version == Info.OsInfo.WindowsVersion.Win7)
            {
                // Will do it in one step
                OneStepJoin(name, domain, ou, account, pass);
            }
            else
            {
                MultiStepJoin(name, domain, ou, account, pass);
            }
        }

        private void Reboot()
        {
            if (Operation.Reboot() == false)
            {
                logger.Error("Could not reboot machine");
                rpc.ResetManager();
            }
            else
                _reboot = true;

        }
    }
}
