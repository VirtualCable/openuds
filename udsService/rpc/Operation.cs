using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using log4net;
using System.Runtime.InteropServices;
using System.Threading;

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

        const uint FORMAT_MESSAGE_ALLOCATE_BUFFER = 0x00000100;
        const uint FORMAT_MESSAGE_IGNORE_INSERTS  = 0x00000200;
        const uint FORMAT_MESSAGE_FROM_SYSTEM    = 0x00001000;
        const uint FORMAT_MESSAGE_ARGUMENT_ARRAY = 0x00002000;
        const uint FORMAT_MESSAGE_FROM_HMODULE = 0x00000800;
        const uint FORMAT_MESSAGE_FROM_STRING = 0x00000400;

        [DllImport("Kernel32.dll", SetLastError = true)]
        static extern uint FormatMessage(uint dwFlags, IntPtr lpSource, uint dwMessageId, uint dwLanguageId, ref IntPtr lpBuffer,
           uint nSize, IntPtr pArguments);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern IntPtr LocalFree(IntPtr hMem);

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

        [DllImport("netapi32.dll", CharSet = CharSet.Unicode, SetLastError=true)]
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
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError=true)]
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
            if (ok)
                logger.Info("Rebooting computer");
            else
                logger.Error("Could not reboot machine. (Error " + ok.ToString() + ")");

            return ok;
        }

        private static bool waitAfterError(string op, bool useGetLastError, ManualResetEvent waitEvent, TimeSpan retryDelay)
        {
            if (useGetLastError)
                logger.Error("Error at " + op + ": " + GetLastErrorStr() + ". Retrying in " + retryDelay.Seconds.ToString() + " secs");
            else
                logger.Error("Error at " + op + ". Retrying in " + retryDelay.Seconds.ToString() + " secs");

            if (waitEvent.WaitOne(retryDelay))
                return false;

            return true;
        }

        public static bool RenameComputer(string newName)
        {
            logger.Info("Renaming computer to \"" + newName + "\"");
            try
            {
                return SetComputerNameEx(COMPUTER_NAME_FORMAT.ComputerNamePhysicalDnsHostname, newName);
            }
            catch (Exception)
            {
                return false;
            }
        }

        public static bool RenameComputer(string newName, ManualResetEvent waitEvent, TimeSpan retryDelay)
        {
            while (RenameComputer(newName) == false)
            {
                if (waitAfterError("Rename", true, waitEvent, retryDelay) == false)
                    return false;
            }
            return true;
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
            logger.Info("Joining domain: \"" + domain + "\", \"" + ou + "\", \"" + account + "\", \"" + "*****" + "\"" + ", oneStep = " + oneStep.ToString());
            // Flag NETSETUP_JOIN_WITH_NEW_NAME not supported on win xp/2000
            JoinOptions flags = JoinOptions.NETSETUP_ACCT_CREATE | JoinOptions.NETSETUP_DOMAIN_JOIN_IF_JOINED | JoinOptions.NETSETUP_JOIN_DOMAIN;

            if (oneStep)
                flags |= JoinOptions.NETSETUP_JOIN_WITH_NEW_NAME;

            if (ou == "")
                ou = null;
            try
            {
                uint res = NetJoinDomain(null, domain, ou, account, password, flags);
                if (res == 2224)
                {
                    flags = JoinOptions.NETSETUP_DOMAIN_JOIN_IF_JOINED | JoinOptions.NETSETUP_JOIN_DOMAIN;
                    logger.Info("Existing account for machine found, reusing it");
                    res = NetJoinDomain(null, domain, null, account, password, flags);
                }
                if (res != 0)
                {
                    logger.Error("Error joining domain:" + GetLastErrorStr((int)res));
                }
                else
                    logger.Info("Successfully joined domain");
                logger.Debug("Result of join: " + res);
                return res == 0;
            }
            catch (Exception e)
            {
                logger.Error("Exception at join domain", e);
                return false;
            }

        }

        public static bool JoinDomain(string domain, string ou, string account, string password, bool oneStep, ManualResetEvent waitEvent, TimeSpan retryDelay)
        {
            while (JoinDomain(domain, ou, account, password, oneStep) == false)
            {
                if (waitAfterError("Join domain", true, waitEvent, retryDelay) == false)
                    return false;
            }
            return true;
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

        private static string GetLastErrorStr(int nLastError=-1)
        {
            if(nLastError == -1)
                nLastError = Marshal.GetLastWin32Error();

            IntPtr lpMsgBuf = IntPtr.Zero;

            uint dwChars = FormatMessage(
                FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                IntPtr.Zero,
                (uint)nLastError,
                0, // Default language
                ref lpMsgBuf,
                0,
                IntPtr.Zero);
            if (dwChars == 0)
            {
                return "(unknown)";
            }

            string sRet = Marshal.PtrToStringAnsi(lpMsgBuf);

            // Free the buffer.
            lpMsgBuf = LocalFree(lpMsgBuf);
            return sRet;

        }
   }
}
