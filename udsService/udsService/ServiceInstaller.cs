using System;
using System.Runtime.InteropServices;
using log4net;

namespace uds.Services
{
    class ServiceInstaller
    {
        private static ILog logger = LogManager.GetLogger(typeof(ServiceInstaller));

        #region DLLImport
        [DllImport("advapi32.dll")]
        public static extern IntPtr OpenSCManager(string lpMachineName, string lpSCDB, int scParameter);
        [DllImport("Advapi32.dll")]
        public static extern IntPtr CreateService(IntPtr SC_HANDLE, string lpSvcName, string lpDisplayName,
        int dwDesiredAccess, int dwServiceType, int dwStartType, int dwErrorControl, string lpPathName,
        string lpLoadOrderGroup, int lpdwTagId, string lpDependencies, string lpServiceStartName, string lpPassword);
        [DllImport("advapi32.dll")]
        public static extern void CloseServiceHandle(IntPtr SCHANDLE);
        [DllImport("advapi32.dll")]
        public static extern int StartService(IntPtr SVHANDLE, int dwNumServiceArgs, string lpServiceArgVectors);
        [DllImport("advapi32.dll", SetLastError = true)]
        public static extern IntPtr OpenService(IntPtr SCHANDLE, string lpSvcName, int dwNumServiceArgs);
        [DllImport("advapi32.dll")]
        public static extern int DeleteService(IntPtr SVHANDLE);
        [DllImport("kernel32.dll")]
        public static extern int GetLastError();
        #endregion DLLImport

        /// <summary>
        /// This method installs and runs the service in the service control manager.
        /// </summary>
        /// <param name="svcPath">The complete path of the service.</param>
        /// <param name="svcName">Name of the service.</param>
        /// <param name="svcDispName">Display name of the service.</param>
        /// <returns>True if the process went thro successfully. False if there was anyerror.</returns>
        public static bool InstallService(string svcPath, string svcName, string svcDispName, string description, string dependencies, bool startNow)
        {
            logger.Info("Installing service \"" + svcName + "\" at \"" + svcPath + "\"");

            int SC_MANAGER_CREATE_SERVICE = 0x0002;
            int SERVICE_WIN32_OWN_PROCESS = 0x00000010;
            //int SERVICE_DEMAND_START = 0x00000003;
            int SERVICE_ERROR_NORMAL = 0x00000001;
            int STANDARD_RIGHTS_REQUIRED = 0xF0000;
            int SERVICE_QUERY_CONFIG = 0x0001;
            int SERVICE_CHANGE_CONFIG = 0x0002;
            int SERVICE_QUERY_STATUS = 0x0004;
            int SERVICE_ENUMERATE_DEPENDENTS = 0x0008;
            int SERVICE_START = 0x0010;
            int SERVICE_STOP = 0x0020;
            int SERVICE_PAUSE_CONTINUE = 0x0040;
            int SERVICE_INTERROGATE = 0x0080;
            int SERVICE_USER_DEFINED_CONTROL = 0x0100;
            int SERVICE_ALL_ACCESS = (STANDARD_RIGHTS_REQUIRED | SERVICE_QUERY_CONFIG | SERVICE_CHANGE_CONFIG | SERVICE_QUERY_STATUS |
                SERVICE_ENUMERATE_DEPENDENTS | SERVICE_START | SERVICE_STOP | SERVICE_PAUSE_CONTINUE | SERVICE_INTERROGATE | SERVICE_USER_DEFINED_CONTROL);
            int SERVICE_AUTO_START = 0x00000002;

            try
            {
                IntPtr sc_handle = OpenSCManager(null, null, SC_MANAGER_CREATE_SERVICE);
                if (sc_handle.ToInt32() != 0)
                {
                    IntPtr sv_handle = CreateService(sc_handle, svcName, svcDispName, SERVICE_ALL_ACCESS, SERVICE_WIN32_OWN_PROCESS, SERVICE_AUTO_START, SERVICE_ERROR_NORMAL, svcPath, null, 0, dependencies, null, null);
                    if (sv_handle.ToInt32() == 0)
                    {
                        logger.Error("Service can't be installed!!");
                        CloseServiceHandle(sc_handle);
                        return false;
                    }
                    else
                    {
                        logger.Info("Service installed");
                        if (startNow)
                        {
                            //now trying to start the service
                            int i = StartService(sv_handle, 0, null);
                            // If the value i is zero, then there was an error starting the service.
                            // note: error may arise if the service is already running or some other problem.
                            if (i == 0)
                            {
                                logger.Error("Can't start service!!!");
                                //Console.WriteLine("Couldnt start service");
                                return false;
                            }
                            //Console.WriteLine("Success");
                        }
                        CloseServiceHandle(sc_handle);

                        Microsoft.Win32.RegistryKey system, currentControlSet, services, service;
                        system = Microsoft.Win32.Registry.LocalMachine.OpenSubKey("System");
                        //Open CurrentControlSet

                        currentControlSet = system.OpenSubKey("CurrentControlSet");
                        services = currentControlSet.OpenSubKey("Services");
                        service = services.OpenSubKey(svcName, true);
                        service.SetValue("Description", description);
                        return true;
                    }
                }
                else
                {
                    logger.Error("SCM not opened successfully");
                    return false;
                }
            }
            catch (Exception e)
            {
                throw e;
            }
        }

        public static void StopService(string svcName, int timeoutMilliseconds = 10000)
        {
            logger.Debug("Stoping service " + svcName + " with timeout " + timeoutMilliseconds);
            System.ServiceProcess.ServiceController service = new System.ServiceProcess.ServiceController(svcName);
            try
            {
                TimeSpan timeout = TimeSpan.FromMilliseconds(timeoutMilliseconds);

                service.Stop();
                service.WaitForStatus(System.ServiceProcess.ServiceControllerStatus.Stopped, timeout);
                logger.Debug("Service correctly stopped");
            }
            catch(Exception e)
            {
                // ...
                logger.Debug("Service could not been stoped", e);
            }
        }


        public static bool UnInstallService(string svcName)
        {
            logger.Info("Uninstalling service " + svcName);
            StopService(svcName);
            // First, stop service
            int GENERIC_WRITE = 0x40000000;
            IntPtr sc_hndl = OpenSCManager(null, null, GENERIC_WRITE);
            if (sc_hndl.ToInt32() != 0)
            {
                int DELETE = 0x10000;
                IntPtr svc_hndl = OpenService(sc_hndl, svcName, DELETE);
                //Console.WriteLine(svc_hndl.ToInt32());
                if (svc_hndl.ToInt32() != 0)
                {
                    int i = DeleteService(svc_hndl);
                    if (i != 0)
                    {
                        logger.Info("Service correctly removed");
                        CloseServiceHandle(sc_hndl);
                        return true;
                    }
                    else
                    {
                        logger.Error("Can't remove service: " + i.ToString());
                        CloseServiceHandle(sc_hndl);
                        return false;
                    }
                }
                else
                    return false;
            }
            else
            {
                logger.Error("SCM not opened successfully!!");
                return false;
            }
        }
    }
}