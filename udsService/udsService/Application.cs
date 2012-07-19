using System;
using System.Collections.Generic;
using log4net;
using System.ServiceProcess;
using System.Diagnostics;
using System.Linq;

namespace uds.Services
{
    class Application
    {
        private static ILog logger = LogManager.GetLogger(typeof(Application));

        private const string serviceName = "UDSService";
        private const string serviceDisplayName = "UDS Actor";
        private const string serviceDescription = "UDS coordination actor";
        private const string serviceDependencies = "SENS\0COMSysApp";
        private const bool serviceStartOnInstall = false;


        /*private static void SensLogon_DisplayLock(string userName)
        {
            Console.WriteLine("Screen Locked: " + userName);
        }
        private static void SensLogon_DisplayUnlock(string userName)
        {
            Console.WriteLine("Screen Unlocked: " + userName);
        }*/

        private static void InstallService()
        {
            if (ServiceInstaller.InstallService(System.Reflection.Assembly.GetEntryAssembly().Location, serviceName, serviceDisplayName, serviceDescription, serviceDependencies, serviceStartOnInstall) == false)
            {
                 Console.WriteLine("Can't install service!!!");
            }
        }

        private static void UninstallService()
        {
            if (ServiceInstaller.UnInstallService("UDSService") == false)
            {
                Console.WriteLine("Can't uninstall service!!!");
            }
        }

        static void Main(string[] args)
        {
            log4net.Config.XmlConfigurator.Configure(new System.IO.FileInfo(AppDomain.CurrentDomain.BaseDirectory + "logging.cfg"));
            config.LoadConfig(); // Loads configuration...
            // unlocks rpc
            rpc.Unlock(string.Join("", new string[] { "m", "a", "m", "0" }));
            if (args.Length == 1)
            {
                switch (args[0])
                {
                    case "-I":
                    case "-i":
                    case "/i":
                        InstallService();
                        return;
                    case "-U":
                    case "-u":
                    case "/u":
                        UninstallService();
                        return;
                    case "-C":
                    case "-c":
                    case "/c":
                        gui.gui.ShowConfig();
                        return;
                    case "-R":
                    case "-r":
                    case "/r":
                        //Operation.Reboot();
                        return;
                    case "-h":
                    case "-H":
                    default:
                        Console.WriteLine("Usage: udsService.exe [-i|-u|-h|-c]");
                        return;
                }
            }

            ServiceBase.Run(new Service());
        }
    }
}
