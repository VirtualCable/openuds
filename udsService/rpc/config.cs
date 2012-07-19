using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using log4net;

namespace uds
{
    public class config
    {
        private static ILog logger = LogManager.GetLogger(typeof(config));

        public static string broker = "";
        public static bool ssl = true;
        public static int timeOut = 10;

        // Constants
        private const string KEY_SOFTWARE = "Software";
        private const string KEY_VCABLE = "Virtual Cable S.L.";
        private const string KEY_UDSACTOR = "UDS Actor";
        private const string VALUE_BROKER = "server";
        private const string VALUE_SSL = "secured";
        private const string VALUE_TIMEOUT = "timeout";

        public static void LoadConfig()
        {
            Microsoft.Win32.RegistryKey software = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(KEY_SOFTWARE);
            Microsoft.Win32.RegistryKey vcable = software.OpenSubKey(KEY_VCABLE);
            // Default values if registry don't exists
            if( vcable == null )
                return;
            Microsoft.Win32.RegistryKey udssactor = vcable.OpenSubKey(KEY_UDSACTOR);
            // Default values if registry don't exists
            if (udssactor == null)
                return;
            broker = (string)udssactor.GetValue(VALUE_BROKER, "");
            string tmp = (string)udssactor.GetValue(VALUE_SSL, "1");
            ssl = (tmp == "1") ? true : false;
            tmp = (string)udssactor.GetValue(VALUE_TIMEOUT, "10");
            try {  timeOut = Int32.Parse(tmp); }
            catch (Exception) { timeOut = 10;  }
            
        }

        public static void SaveConfig()
        {
            Microsoft.Win32.RegistryKey software = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(KEY_SOFTWARE, true);
            Microsoft.Win32.RegistryKey vcable = software.OpenSubKey(KEY_VCABLE, true);
            if (vcable == null)
            {
                // Tries to create subkey
                vcable = software.CreateSubKey(KEY_VCABLE);
                if (vcable == null)
                    throw new InvalidOperationException("Can't access registry!!! " + KEY_VCABLE);
            }
            Microsoft.Win32.RegistryKey udssactor = vcable.OpenSubKey(KEY_UDSACTOR, true);
            if (udssactor == null)
            {
                // Tries to create subkey
                udssactor = vcable.CreateSubKey(KEY_UDSACTOR);
                if (udssactor == null)
                    throw new InvalidOperationException("Can't access registry!!! " + KEY_UDSACTOR);
            }

            udssactor.SetValue(VALUE_BROKER, broker);
            udssactor.SetValue(VALUE_SSL, ssl ? "1" : "0");
            udssactor.SetValue(VALUE_TIMEOUT, timeOut.ToString());

        }


    }
}
