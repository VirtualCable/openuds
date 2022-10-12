# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''

# Note. most methods are not implemented, as they are not needed for this platform (macos)
# that only supports unmanaged machines

import socket
import os
import re
import subprocess  # nosec
import typing

import psutil

from udsactor import types, tools

MACVER_RE = re.compile(
    r"<key>ProductVersion</key>\s*<string>(.*)</string>", re.MULTILINE
)
MACVER_FILE = '/System/Library/CoreServices/SystemVersion.plist'


def checkPermissions() -> bool:
    return os.getuid() == 0


def getComputerName() -> str:
    '''
    Returns computer name, with no domain
    '''
    return socket.gethostname().split('.')[0]


def getNetworkInfo() -> typing.Iterator[types.InterfaceInfoType]:
    ifdata: typing.List['psutil._common.snicaddr']
    for ifname, ifdata in psutil.net_if_addrs().items():
        name, ip, mac = '', '', ''
        # Get IP address, interface name and MAC address whenever possible
        for row in ifdata:
            if row.family == socket.AF_INET:
                ip = row.address
                name = ifname
            elif row.family == socket.AF_LINK:
                mac = row.address

            # if all data is available, stop iterating
            if ip and name and mac:
                if (
                    mac != '00:00:00:00:00:00'
                    and mac
                    and ip
                    and ip.startswith('169.254') is False
                ):  # Skips local interfaces & interfaces with no dhcp IPs
                    yield types.InterfaceInfoType(name=name, ip=ip, mac=mac)
                    break


def getDomainName() -> str:
    return ''


def getMacOs() -> str:
    try:
        with open(MACVER_FILE, 'r') as f:
            data = f.read()
        m = MACVER_RE.search(data)
        if m:
            return m.group(1)
    except Exception:  # nosec: B110: ignore exception because we are not interested in it
        pass

    return 'unknown'


def getVersion() -> str:
    return 'MacOS ' + getMacOs()


def reboot(flags: int = 0) -> None:
    '''
    Simple reboot using os command
    '''
    subprocess.call(['/sbin/shutdown', '-r', 'now'])  # nosec: Command line is fixed


def loggoff() -> None:
    '''
    Right now restarts the machine...
    '''
    subprocess.run(
        "/bin/launchctl bootout gui/$(id -u $USER)", shell=True
    )  # nosec: Command line is fixed
    # Ignores output, as it may fail if user is not logged in


def renameComputer(newName: str) -> bool:
    '''
    Changes the computer name
    Returns True if reboot needed
    Note: For macOS, no configuration is supported, only "unmanaged" actor
    '''
    return False


def joinDomain(
    domain: str, ou: str, account: str, password: str, executeInOneStep: bool = False
):
    pass


def changeUserPassword(user: str, oldPassword: str, newPassword: str) -> None:
    pass


def initIdleDuration(atLeastSeconds: int) -> None:
    pass


# se we cache for 20 seconds the result, that is enough for our needs
# and we avoid calling a system command every time we need it
@tools.cache(20)
def getIdleDuration() -> float:
    # Execute:
    try:
        return (
            int(
                next(
                    filter(
                        lambda x: b"HIDIdleTime" in x,
                        subprocess.check_output(
                            ["/usr/sbin/ioreg", "-c", "IOHIDSystem"]
                        ).split(b"\n"),
                    )
                ).split(b"=")[1]
            )
            / 1000000000
        )  # nosec: Command line is fixed
    except Exception:  # nosec: B110: ignore exception because we are not interested in it
        return 0


def getCurrentUser() -> str:
    '''
    Returns current logged in user
    '''
    return os.getlogin()


def getSessionType() -> str:
    '''
    Returns the session type. Currently, only "macos" (console) is supported
    '''
    return 'macos'


def forceTimeSync() -> None:
    return
