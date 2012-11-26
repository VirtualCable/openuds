using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using log4net;
using System.Runtime.InteropServices;

namespace uds
{
    public class Operation
    {
        private static ILog logger = LogManager.GetLogger(typeof(Operation));

        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        internal struct TokPriv1Luid
        {
            public int Count;
            public long Luid;
            public int Attr;
        }

        [DllImport("kernel32.dll", ExactSpelling = true)]
        internal static extern IntPtr GetCurrentProcess();

        [DllImport("advapi32.dll", ExactSpelling = true, SetLastError = true)]
        internal static extern bool OpenProcessToken(IntPtr h, int acc, ref IntPtr phtok);

        [DllImport("advapi32.dll", SetLastError = true)]
        internal static extern bool LookupPrivilegeValue(string host, string name, ref long pluid);

        [DllImport("advapi32.dll", ExactSpelling = true, SetLastError = true)]
        internal static extern bool AdjustTokenPrivileges(IntPtr htok, bool disall,  ref TokPriv1Luid newst, 
            int len, IntPtr prev, IntPtr relen);

        [DllImport("user32.dll", ExactSpelling = true, SetLastError = true)]
        internal static extern bool ExitWindowsEx(int flg, int rea);

        [DllImport("netapi32.dll", CharSet = CharSet.Unicode, CallingConvention = CallingConvention.StdCall,
            SetLastError = true)]
        static extern uint NetUserChangePassword(
        [MarshalAs(UnmanagedType.LPWStr)] string domainname,
        [MarshalAs(UnmanagedType.LPWStr)] string username,
        [MarshalAs(UnmanagedType.LPWStr)] string oldpassword,
        [MarshalAs(UnmanagedType.LPWStr)] string newpassword
        );


        [Flags]
        public enum JoinOptions
        {
            NETSETUP_JOIN_DOMAIN = 0x00000001,
            NETSETUP_ACCT_CREATE = 0x00000002,
            NETSETUP_ACCT_DELETE = 0x00000004,
            NETSETUP_WIN9X_UPGRADE = 0x00000010,
            NETSETUP_DOMAIN_JOIN_IF_JOINED = 0x00000020,
            NETSETUP_JOIN_UNSECURE = 0x00000040,
            NETSETUP_MACHINE_PWD_PASSED = 0x00000080,
            NETSETUP_JOIN_WITH_NEW_NAME = 0x00000400,
            NETSETUP_DEFER_SPN_SET = 0x10000000
        }

        [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
        static extern uint NetJoinDomain(string lpServer, string lpDomain, string lpAccountOU, string lpAccount, string lpPassword, JoinOptions NameType);

        enum COMPUTER_NAME_FORMAT
        {
            ComputerNameNetBIOS,
            ComputerNameDnsHostname,
            ComputerNameDnsDomain,
            ComputerNameDnsFullyQualified,
            ComputerNamePhysicalNetBIOS,
            ComputerNamePhysicalDnsHostname,
            ComputerNamePhysicalDnsDomain,
            ComputerNamePhysicalDnsFullyQualified,
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Auto)]
        static extern bool SetComputerNameEx(COMPUTER_NAME_FORMAT NameType, string lpBuffer);

        internal const int SE_PRIVILEGE_ENABLED = 0x00000002;
        internal const int TOKEN_QUERY = 0x00000008;
        internal const int TOKEN_ADJUST_PRIVILEGES = 0x00000020;
        internal const string SE_SHUTDOWN_NAME = "SeShutdownPrivilege";
        internal const string SE_SECURITY_NAME = "SeSecurityPrivilege";
        internal const string SE_TCB_NAME = "SeTcbPrivilege";

        public const int EWX_LOGOFF = 0x00000000;
        public const int EWX_SHUTDOWN = 0x00000001;
        public const int EWX_REBOOT = 0x00000002;
        public const int EWX_FORCE = 0x00000004;
        public const int EWX_POWEROFF = 0x00000008;
        public const int EWX_FORCEIFHUNG = 0x00000010;

        public static bool Reboot(int flg = EWX_FORCEIFHUNG|EWX_REBOOT)
        {
            logger.Debug("Rebooting computer");
            bool ok;
            TokPriv1Luid tp;
            IntPtr hproc = GetCurrentProcess();
            IntPtr htok = IntPtr.Zero;
            ok = OpenProcessToken(hproc, TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ref htok);
            tp.Count = 1;
            tp.Luid = 0;
            tp.Attr = SE_PRIVILEGE_ENABLED;
            ok = LookupPrivilegeValue(null, SE_SHUTDOWN_NAME, ref tp.Luid);
            ok = AdjustTokenPrivileges(htok, false, ref tp, 0, IntPtr.Zero, IntPtr.Zero);
            ok = ExitWindowsEx(flg, 0);
            logger.Debug("Result: " + ok.ToString());
            return ok;
        }

        public static bool RenameComputer(string newName)
        {
            logger.Debug("Renaming computer to \"" + newName + "\"");
            try
            {
                return SetComputerNameEx(COMPUTER_NAME_FORMAT.ComputerNamePhysicalDnsHostname, newName);
            }
            catch (Exception)
            {
                return false;
            }
        }

        public static bool JoinDomain(string domain, string ou, string account, string password, bool oneStep = false)
        {
            if (account.Contains('@') == false && account.Contains('\\') == false)
            {
                if (domain.Contains('.'))
                    account = account + "@" + domain;
                else
                    account = domain + "\\" + account;
            }
            logger.Debug("Joining domain: \"" + domain + "\", \"" + ou + "\", \"" + account + "\", \"" + password + "\"" + ", oneStep = " + oneStep.ToString());
            // Flag NETSETUP_JOIN_WITH_NEW_NAME not supported on win xp/2000
            JoinOptions flags = JoinOptions.NETSETUP_ACCT_CREATE | JoinOptions.NETSETUP_DOMAIN_JOIN_IF_JOINED | JoinOptions.NETSETUP_JOIN_DOMAIN;

            if (oneStep)
                flags |= JoinOptions.NETSETUP_JOIN_WITH_NEW_NAME;

            if (ou == "")
                ou = null;
            try
            {
                uint res = NetJoinDomain(null, domain, ou, account, password, flags);
                logger.Debug("Result of join: " + res);
                return res == 0;
            }
            catch (Exception e)
            {
                logger.Error("Exception at join domain", e);
                return false;
            }

        }

        public static bool ChangeUserPassword(string user, string oldPass, string newPass)
        {
            try {

                logger.Debug("Setting new password for user " + user + " to " + newPass);

                Info.DomainInfo info = Info.Computer.GetDomainInfo();

                uint res = NetUserChangePassword(info.ComputerName, user, oldPass, newPass);
                logger.Debug("Result of changeUserPassword: " + res);

                if( res != 0 )
                    logger.Error("Could not change password for user \"" + user + "\" (using password \"" + newPass + "\") at \"" + info.ComputerName + "\", result: " + res);

                return res == 0;
            }
            catch  (Exception e)
            {
                logger.Error("Exception at change user password", e);
                return false;
            }
        }
   }
}
