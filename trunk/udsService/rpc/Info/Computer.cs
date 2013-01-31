using System;
using System.Collections.Generic;
using System.Text;
using System.Net.NetworkInformation;
using log4net;
using System.Security.Principal;

namespace uds.Info
{
    public class Computer
    {
        private static ILog logger = LogManager.GetLogger(typeof(Computer));

        public struct InterfaceInfo
        {
            public string ip;
            public string mac;

            public InterfaceInfo(string _ip, string _mac)
            {
                ip = _ip; mac = _mac;
            }
        }

        public static List<InterfaceInfo> GetInterfacesInfo()
        {
            if (NetworkInterface.GetIsNetworkAvailable() == false)
                return null;

            List<InterfaceInfo> res = new List<InterfaceInfo>();

            foreach (NetworkInterface nic in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (nic.OperationalStatus == OperationalStatus.Up)
                {
                    byte[] addr = nic.GetPhysicalAddress().GetAddressBytes();
                    if (addr.Length != 6)
                        continue;
                    IPInterfaceProperties props = nic.GetIPProperties();
                    List<string> ips = new List<string>();
                    foreach (IPAddressInformation ip in props.UnicastAddresses)
                    {
                        if (ip.Address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
                            ips.Add(ip.Address.ToString());
                    }
                    string tmp = nic.GetPhysicalAddress().ToString();
                    string nc = tmp.Substring(0, 2) + ":" + tmp.Substring(2,2) + ":" + tmp.Substring(4,2) + ":" + tmp.Substring(6,2) + ":" + 
                        tmp.Substring(8,2) + ":" + tmp.Substring(10,2);
                    res.Add(new InterfaceInfo(string.Join(",", ips.ToArray()), nc));
                }
            }
            return res;
        }

        public static DomainInfo GetDomainInfo()
        {
            return new DomainInfo();
        }

        public static OsInfo GetOsInfo()
        {
            return new OsInfo();
        }

        public static bool IsUserAdministrator()
        {
            //bool value to hold our return value
            bool isAdmin;
            try
            {
                //get the currently logged in user
                WindowsIdentity user = WindowsIdentity.GetCurrent();
                WindowsPrincipal principal = new WindowsPrincipal(user);
                isAdmin = principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
            catch (UnauthorizedAccessException)
            {
                isAdmin = false;
            }
            catch (Exception)
            {
                isAdmin = false;
            }
            return isAdmin;
        }

    }
}

