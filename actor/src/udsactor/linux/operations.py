# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
# pylint: disable=invalid-name
import configparser
import platform
import socket
import fcntl
import os
import ctypes
import ctypes.util
import subprocess
import struct
import array
import typing

from .. import types

from .renamer import rename


def _getMacAddr(ifname: str) -> typing.Optional[str]:
    '''
    Returns the mac address of an interface
    Mac is returned as unicode utf-8 encoded
    '''
    ifnameBytes = ifname.encode('utf-8')  # If unicode, convert to bytes
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = bytearray(fcntl.ioctl(s.fileno(), 0x8927, struct.pack(str('256s'), ifnameBytes[:15])))
        return str(''.join(['%02x:' % char for char in info[18:24]])[:-1]).upper()
    except Exception:
        return None


def _getIpAddr(ifname: str) -> typing.Optional[str]:
    '''
    Returns the ip address of an interface
    Ip is returned as unicode utf-8 encoded
    '''
    ifnameBytes = ifname.encode('utf-8')  # If unicode, convert to bytes (or str in python 2.7)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return str(socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack(str('256s'), ifnameBytes[:15])
        )[20:24]))
    except Exception:
        return None


def _getInterfaces() -> typing.List[str]:
    '''
    Returns a list of interfaces names coded in utf-8
    '''
    max_possible = 128  # arbitrary. raise if needed.
    space = max_possible * 16
    if platform.architecture()[0] == '32bit':
        offset, length = 32, 32
    elif platform.architecture()[0] == '64bit':
        offset, length = 16, 40
    else:
        raise OSError('Unknown arquitecture {0}'.format(platform.architecture()[0]))

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array(str('B'), b'\0' * space)
    outbytes = struct.unpack(str('iL'), fcntl.ioctl(
        s.fileno(),
        0x8912,  # SIOCGIFCONF
        struct.pack(str('iL'), space, names.buffer_info()[0])
    ))[0]
    namestr = names.tostring()
    # return namestr, outbytes
    return [namestr[i:i + offset].split(b'\0', 1)[0].decode('utf-8') for i in range(0, outbytes, length)]


def _getIpAndMac(ifname: str) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    ip, mac = _getIpAddr(ifname), _getMacAddr(ifname)
    return (ip, mac)


def checkPermissions() -> bool:
    return os.getuid() == 0

def getComputerName() -> str:
    '''
    Returns computer name, with no domain
    '''
    return socket.gethostname().split('.')[0]

def getNetworkInfo() -> typing.Iterable[types.InterfaceInfoType]:
    for ifname in _getInterfaces():
        ip, mac = _getIpAndMac(ifname)
        if mac != '00:00:00:00:00:00' and mac and ip and ip.startswith('169.254') is False:  # Skips local interfaces & interfaces with no dhcp IPs
            yield types.InterfaceInfoType(name=ifname, mac=mac, ip=ip)

def getDomainName() -> str:
    return ''

def getLinuxOs() -> str:
    try:
        with open('/etc/os-release', 'r') as f:
            data = f.read()
        cfg = configparser.ConfigParser()
        cfg.read_string('[os]\n' + data)
        return cfg['os'].get('id', 'unknown')
    except Exception:
        return 'unknown'

def reboot(flags: int = 0):
    '''
    Simple reboot using os command
    '''
    subprocess.call(['/sbin/shutdown', 'now', '-r'])


def loggoff() -> None:
    '''
    Right now restarts the machine...
    '''
    subprocess.call(['/usr/bin/pkill', '-u', os.environ['USER']])
    # subprocess.call(['/sbin/shutdown', 'now', '-r'])
    # subprocess.call(['/usr/bin/systemctl', 'reboot', '-i'])


def renameComputer(newName: str) -> None:
    rename(newName)


def joinDomain(domain: str, ou: str, account: str, password: str, executeInOneStep: bool = False):
    pass


def changeUserPassword(user: str, oldPassword: str, newPassword: str) -> None:
    '''
    Simple password change for user using command line
    '''
    os.system('echo "{1}\n{1}" | /usr/bin/passwd {0} 2> /dev/null'.format(user, newPassword))


class XScreenSaverInfo(ctypes.Structure):  # pylint: disable=too-few-public-methods
    _fields_ = [('window', ctypes.c_long),
                ('state', ctypes.c_int),
                ('kind', ctypes.c_int),
                ('til_or_since', ctypes.c_ulong),
                ('idle', ctypes.c_ulong),
                ('eventMask', ctypes.c_ulong)]

# Initialize xlib & xss
try:
    xlibPath = ctypes.util.find_library('X11')
    xssPath = ctypes.util.find_library('Xss')
    xlib = xss = None
    if not xlibPath or not xssPath:
        raise Exception()
    xlib = ctypes.cdll.LoadLibrary(xlibPath)
    xss = ctypes.cdll.LoadLibrary(xssPath)

    # Fix result type to XScreenSaverInfo Structure
    xss.XScreenSaverQueryExtension.restype = ctypes.c_int
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)  # Result in a XScreenSaverInfo structure
    display = xlib.XOpenDisplay(None)
    xssInfo = xss.XScreenSaverAllocInfo()
except Exception:  # Libraries not accesible, not found or whatever..
    xlib = xss = display = xssInfo = None


def initIdleDuration(atLeastSeconds: int) -> None:
    subprocess.call(['/usr/bin/xset', 's', '{}'.format(atLeastSeconds + 30)])
    # And now reset it
    subprocess.call(['/usr/bin/xset', 's', 'reset'])


def getIdleDuration() -> float:
    '''
    Returns idle duration, in seconds
    '''
    if xlib is None or xss is None:
        return 0  # Libraries not available

    event_base = ctypes.c_int()
    error_base = ctypes.c_int()

    available = xss.XScreenSaverQueryExtension(display, ctypes.byref(event_base), ctypes.byref(error_base))

    if available != 1:
        return 0  # No screen saver is available, no way of getting idle

    xss.XScreenSaverQueryInfo(display, xlib.XDefaultRootWindow(display), xssInfo)

    # Centos seems to set state to 1?? (weird, but it's happening don't know why... will try this way)
    if xssInfo.contents.state != 0 and 'centos' not in getLinuxOs().lower().strip():
        return 3600 * 100 * 1000  # If screen saver is active, return a high enough value

    return xssInfo.contents.idle / 1000.0


def getCurrentUser() -> str:
    '''
    Returns current logged in user
    '''
    return os.environ['USER']
