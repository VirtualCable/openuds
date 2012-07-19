using System;
using System.Collections.Generic;
using System.Text;
using System.Runtime.InteropServices;
using log4net;

namespace uds.Info
{
    public class DomainInfo
    {
        private static ILog logger = LogManager.GetLogger(typeof(DomainInfo));

        // Win32 Result Code Constant
        const int ErrorSuccess = 0;

        // NetGetJoinInformation() Enumeration
        public enum NetJoinStatus
        {
            NetSetupUnknownStatus = 0,
            NetSetupUnjoined,
            NetSetupWorkgroupName,
            NetSetupDomainName
        }

        [DllImport("Netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern int NetGetJoinInformation(string server, out IntPtr domain, out NetJoinStatus status);

        [DllImport("Netapi32.dll")]
        static extern int NetApiBufferFree(IntPtr Buffer);

        // Info obtained
        private string _computerName;
        private string _domainName;
        private NetJoinStatus _status;


        public DomainInfo()
        {
            _domainName = "";
            _computerName = System.Environment.MachineName;
            _status = NetJoinStatus.NetSetupUnknownStatus;

            IntPtr pDomain = IntPtr.Zero;
            try
            {
                int result = 0;
                result = NetGetJoinInformation(null, out pDomain, out _status);
                if (result == ErrorSuccess )
                {

                    if( _status == NetJoinStatus.NetSetupDomainName )
                        _domainName = Marshal.PtrToStringAuto(pDomain);
                }
            }
            finally
            {
                if (pDomain != IntPtr.Zero) NetApiBufferFree(pDomain);
            }

            logger.Debug("Name: " + _computerName + ", Domain: " + _domainName + ", status" + _status.ToString());
        }

        public string ComputerName
        {
            get { return _computerName; }
        }

        public string DomainName
        {
            get { return _domainName; }
        }

        public NetJoinStatus Status
        {
            get { return _status; }
        }

    }
}
