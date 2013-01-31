using System;
using System.Collections.Generic;
using System.Text;
using log4net;

namespace uds.Info
{
    public class OsInfo
    {
        private static ILog logger = LogManager.GetLogger(typeof(OsInfo));

        public enum WindowsVersion {
            Unknown,
            Win95,
            Win98,
            Win98SE,
            WinME,
            WinNT351,
            WinNT40,
            Win2000,
            WinXP,
            WinVista,
            Win7
        };

        WindowsVersion _version;
        string _servicePack;
        int _architecture;

        public OsInfo()
        {
            //Get Operating system information.
            OperatingSystem os = Environment.OSVersion;
            //Get version information about the os.
            Version vs = os.Version;

            _version = WindowsVersion.Unknown;
            _servicePack = os.ServicePack;
            _architecture = 0;

            if (os.Platform == PlatformID.Win32Windows)
            {
                //This is a pre-NT version of Windows
                switch (vs.Minor)
                {
                    case 0:
                        _version = WindowsVersion.Win95;
                        break;
                    case 10:
                        if (vs.Revision.ToString() == "2222A")
                            _version = WindowsVersion.Win98SE;
                        else
                            _version = WindowsVersion.Win98;
                        break;
                    case 90:
                        _version = WindowsVersion.WinME;
                        break;
                    default:
                        break;
                }
            }
            else if (os.Platform == PlatformID.Win32NT)
            {
                switch (vs.Major)
                {
                    case 3:
                        _version = WindowsVersion.WinNT351; 
                        break;
                    case 4:
                        _version = WindowsVersion.WinNT40;
                        break;
                    case 5:
                        if (vs.Minor == 0)
                            _version = WindowsVersion.Win2000;
                        else
                            _version = WindowsVersion.WinXP;
                        break;
                    case 6:
                        if (vs.Minor == 0)
                            _version = WindowsVersion.WinVista;
                        else
                            _version = WindowsVersion.Win7;
                        break;
                    default:
                        break;
                }
            }
            //Make sure we actually got something in our OS check
            //We don't want to just return " Service Pack 2" or " 32-bit"
            //That information is useless without the OS version.
            if (_version != WindowsVersion.Unknown)
            {
                //Append the OS architecture.  i.e. "Windows XP Service Pack 3 32-bit"
                _architecture = getOSArchitecture();
            }
        }

        private static int getOSArchitecture()
        {
            string pa = Environment.GetEnvironmentVariable("PROCESSOR_ARCHITECTURE");
            Console.WriteLine("Arch: " + pa);
            return ((String.IsNullOrEmpty(pa) || String.Compare(pa, 0, "x86", 0, 3, true) == 0) ? 32 : 64);
        }

        public WindowsVersion Version
        {
            get { return _version; }
        }

    }
}
