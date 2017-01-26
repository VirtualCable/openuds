# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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
from __future__ import unicode_literals

import socket
import platform
import fcntl
import os
import ctypes  # @UnusedImport
import ctypes.util
import subprocess
import struct
import array
import six
from udsactor import utils
from .renamer import rename


def _getMacAddr(ifname):
    '''
    Returns the mac address of an interface
    Mac is returned as unicode utf-8 encoded
    '''
    if isinstance(ifname, list):
        return dict([(name, _getMacAddr(name)) for name in ifname])
    if isinstance(ifname, six.text_type):
        ifname = ifname.encode('utf-8')  # If unicode, convert to bytes (or str in python 2.7)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = bytearray(fcntl.ioctl(s.fileno(), 0x8927, struct.pack(str('256s'), ifname[:15])))
        return six.text_type(''.join(['%02x:' % char for char in info[18:24]])[:-1]).upper()
    except Exception:
        return None


def _getIpAddr(ifname):
    '''
    Returns the ip address of an interface
    Ip is returned as unicode utf-8 encoded
    '''
    if isinstance(ifname, list):
        return dict([(name, _getIpAddr(name)) for name in ifname])
    if isinstance(ifname, six.text_type):
        ifname = ifname.encode('utf-8')  # If unicode, convert to bytes (or str in python 2.7)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return six.text_type(socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack(str('256s'), ifname[:15])
        )[20:24]))
    except Exception:
        return None


def _getInterfaces():
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


def _getIpAndMac(ifname):
    ip, mac = _getIpAddr(ifname), _getMacAddr(ifname)
    return (ip, mac)


def getComputerName():
    '''
    Returns computer name, with no domain
    '''
    return socket.gethostname().split('.')[0]


def getNetworkInfo():
    for ifname in _getInterfaces():
        ip, mac = _getIpAndMac(ifname)
        if mac != '00:00:00:00:00:00' and ip.startswith('169.254') is False:  # Skips local interfaces & interfaces with no dhcp IPs
            yield utils.Bunch(name=ifname, mac=mac, ip=ip)


def getDomainName():
    return ''


def getLinuxVersion():
    lv = platform.linux_distribution()
    return lv[0] + ', ' + lv[1]


def reboot(flags=0):
    '''
    Simple reboot using os command
    '''
    # Workaround for dummy thread
    if six.PY3 is False:
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42

    subprocess.call(['/sbin/shutdown', 'now', '-r'])


def loggoff():
    '''
    Right now restarts the machine...
    '''
    # Workaround for dummy thread
    if six.PY3 is False:
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42

    subprocess.call(['/usr/bin/pkill', '-u', os.environ['USER']])
    # subprocess.call(['/sbin/shutdown', 'now', '-r'])
    # subprocess.call(['/usr/bin/systemctl', 'reboot', '-i'])


def renameComputer(newName):
    rename(newName)


def joinDomain(domain, ou, account, password, executeInOneStep=False):
    pass


def changeUserPassword(user, oldPassword, newPassword):
    '''
    Simple password change for user using command line
    '''
    os.system('echo "{1}\n{1}" | /usr/bin/passwd {0} 2> /dev/null'.format(user, newPassword))


class XScreenSaverInfo(ctypes.Structure):
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
    xlib = ctypes.cdll.LoadLibrary(xlibPath)
    xss = ctypes.cdll.LoadLibrary(xssPath)

    # Fix result type to XScreenSaverInfo Structure
    xss.XScreenSaverQueryExtension.restype = ctypes.c_int
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)  # Result in a XScreenSaverInfo structure
    display = xlib.XOpenDisplay(None)
    info = xss.XScreenSaverAllocInfo()
except Exception:  # Libraries not accesible, not found or whatever..
    xlib = xss = display = info = None


def initIdleDuration(atLeastSeconds):
    '''
    On linux we set the screensaver to at least required seconds, or we never will get "idle"
    '''
    # Workaround for dummy thread
    if six.PY3 is False:
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42

    subprocess.call(['/usr/bin/xset', 's', '{}'.format(atLeastSeconds + 30)])
    # And now reset it
    subprocess.call(['/usr/bin/xset', 's', 'reset'])


def getIdleDuration():
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

    xss.XScreenSaverQueryInfo(display, xlib.XDefaultRootWindow(display), info)

    # Centos seems to set state to 1?? (weird, but it's happening don't know why... will try this way)
    if info.contents.state != 0 and 'centos' not in platform.linux_distribution()[0].lower().strip():
        return 3600 * 100 * 1000  # If screen saver is active, return a high enough value

    return info.contents.idle / 1000.0


def getCurrentUser():
    '''
    Returns current logged in user
    '''
    return os.environ['USER']
