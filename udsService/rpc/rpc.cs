using System;
using System.Collections.Generic;
using System.Text;
using System.Text.RegularExpressions;
using CookComputing.XmlRpc;
using log4net;

namespace uds
{
    public class rpc
    {
        private static ILog logger = LogManager.GetLogger(typeof(rpc));

        private static rpc _manager = null;
        private static bool _unlocked = false;
        private string _id = null;
        private IUDS service = null;

        private const string LOGON_MSG = "logon";
        private const string LOGOFF_MSG = "logoff";
        private const string INFO_MSG = "information";
        private const string READY_MSG = "ready";
        private const string IP_MSG = "ip";
        private const string LOG_MSG = "log";

        private rpc(string url)
        {
            System.Net.ServicePointManager.ServerCertificateValidationCallback = delegate { return true; };
            logger.Debug("Initializing rpc at \"" + url + "\" with timeout of " + config.timeOut.ToString());
            _id = null;
            service = XmlRpcProxyGen.Create<IUDS>();
            service.Timeout = config.timeOut * 1000;
            service.Url = url;
        }

        public static void Initialize(string broker, bool useSSl)
        {
            if (!_unlocked)
                throw new Exception("access denied");
            _manager = null; // Release previous manager
            string protocol = useSSl ? "https" : "http";
            _manager = new rpc(protocol + "://" + broker + "/xmlrpc");
        }

        public static void Unlock(string pass)
        {
            if( pass == string.Join("", new string[] {"m","a","m","0" } ) )
                _unlocked = true;
        }

        public static rpc Manager 
        {
            get { return _manager; }
        }

        private static string Unscramble(string str)
        {
            if( str == "" || str == null )
                return str;

            StringBuilder sb = new StringBuilder();
            int val = 0x32;
            for (int i = 0; i < str.Length; i += 2)
            {
                int c = Int32.Parse(str.Substring(i, 2), System.Globalization.NumberStyles.HexNumber) ^ val;
                val = (val + c) & 0xFF;
                sb.Insert(0, Convert.ToString(Convert.ToChar(c)));
            }
            return sb.ToString();
        }

        public bool Test()
        {
            try
            {
                logger.Debug("Invoking service test");
                service.Test();
            }
            catch (Exception e)
            {
                logger.Debug("Exception", e);
                return false;
            }
            return true;
        }

        public string Message(string message, string data)
        {
            if (_id == null)
            {
                logger.Debug("The id is null, recreating id");
                List<Info.Computer.InterfaceInfo> interfaces = Info.Computer.GetInterfacesInfo();
                _id = string.Join(",", interfaces.ConvertAll<String>(i => i.mac).ToArray());
                logger.Debug("The id is now " + _id);
            }
            logger.Debug("Sending message to broker: " + _id + ", " + message + ", " + data);
            string ret = Unscramble(service.Message(_id, message, data));
            logger.Debug("Returned value: " + ret);
            return ret;
        }

        public static string[] Logon(string username)
        {
            if (rpc.Manager != null)
            {
                logger.Info("Invoking remote logon of user " + username);
                try
                {
                    return rpc.Manager.Message(LOGON_MSG, username).Split('\t');
                }
                catch (Exception)
                {
                    logger.Fatal("Could cont contact broker at " + rpc.Manager.service.Url);
                    return new string[0];
                }
            }
            logger.Debug("Remote logon not invoked. RPC Disabled");
            return new string[0];
        }

        public static void Logoff(string username)
        {
            if (rpc.Manager != null)
            {
                logger.Debug("Invoking remote logoff of user " + username);
                try
                {
                    rpc.Manager.Message(LOGOFF_MSG, username);
                }
                catch (Exception)
                {
                    logger.Info("Could cont contact broker at " + rpc.Manager.service.Url);
                }
            }
            else
            {
                logger.Debug("Remote logoff not invoked. RPC Disabled");
            }
        }

        public static string GetInfo()
        {
            string res = null;
            if (rpc.Manager != null)
            {
                logger.Debug("Invoking remote GetInfo");
                try
                {
                    res = rpc.Manager.Message(INFO_MSG, "");
                }
                catch (Exception)
                {
                    res = null;
                }
            }
            return res;
        }

        public static bool SetReady()
        {
            bool ok = false;
            if (rpc.Manager != null)
            {
                logger.Info("Machine is Ready");
                try
                {
                    List<Info.Computer.InterfaceInfo> interfaces = Info.Computer.GetInterfacesInfo();
                    string info = string.Join(",", interfaces.ConvertAll<String>(i => i.mac + "=" + i.ip).ToArray());
                    rpc.Manager.Message(READY_MSG, info);
                    ok = true;
                }
                catch (Exception)
                {
                }
            }
            return ok;
        }

        public static bool NotifyIPChange()
        {
            bool ok = false;
            if (rpc.Manager != null)
            {
                logger.Debug("Informing broker of ip change");
                try
                {
                    List<Info.Computer.InterfaceInfo> interfaces = Info.Computer.GetInterfacesInfo();
                    string info = string.Join(",", interfaces.ConvertAll<String>(i => i.mac + "=" + i.ip).ToArray());
                    rpc.Manager.Message(IP_MSG, info);
                    ok = true;
                }
                catch (Exception)
                {
                }
            }
            return ok;
        }

        public static void Log(string msg, string Level)
        {
            if (rpc.Manager != null)
            {
                logger.Debug("Sending message " + msg + " of level " + Level);
                rpc.Manager.Message(LOG_MSG, string.Join("\t", new string[] { msg, Level }));
            }
        }

        public static void FlushLoggers()
        {
            log4net.Repository.ILoggerRepository rep = LogManager.GetRepository();
            foreach (log4net.Appender.IAppender appender in rep.GetAppenders())
            {
                var buffered = appender as log4net.Appender.BufferingAppenderSkeleton;
                if (buffered != null)
                    buffered.Flush();
            }
        }

        public static void ResetId()
        {
            logger.Debug("Reseting ID of rpc");
            FlushLoggers();
            if (rpc.Manager != null)
                rpc.Manager._id = null;
        }

        public static void ResetManager()
        {
            logger.Debug("Disabling rpc");
            FlushLoggers();
            rpc._manager = null;
        }
    }
}
