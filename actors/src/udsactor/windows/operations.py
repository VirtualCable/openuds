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

import win32com.client  # @UnresolvedImport, pylint: disable=import-error
import win32net  # @UnresolvedImport, pylint: disable=import-error
import win32security  # @UnresolvedImport, pylint: disable=import-error
import win32api  # @UnresolvedImport, pylint: disable=import-error
import win32con  # @UnresolvedImport, pylint: disable=import-error
import ctypes
from ctypes.wintypes import DWORD, LPCWSTR
import os

from udsactor import utils
from udsactor.log import logger


def getErrorMessage(res=0):
    # sys_fs_enc = sys.getfilesystemencoding() or 'mbcs'
    msg = win32api.FormatMessage(res)
    return msg.decode('windows-1250', 'ignore')


def getComputerName():
    return win32api.GetComputerNameEx(win32con.ComputerNamePhysicalDnsHostname)


def getNetworkInfo():
    obj = win32com.client.Dispatch("WbemScripting.SWbemLocator")
    wmobj = obj.ConnectServer("localhost", "root\cimv2")
    adapters = wmobj.ExecQuery("Select * from Win32_NetworkAdapterConfiguration where IpEnabled=True")
    try:
        for obj in adapters:
            for ip in obj.IPAddress:
                if ':' in ip:  # Is IPV6, skip this
                    continue
                if ip is None or ip == '' or ip.startswith('169.254') or ip.startswith('0.'):  # If single link ip, or no ip
                    continue
                # logger.debug('Net config found: {}=({}, {})'.format(obj.Caption, obj.MACAddress, ip))
                yield utils.Bunch(name=obj.Caption, mac=obj.MACAddress, ip=ip)
    except Exception:
        return


def getDomainName():
    '''
    Will return the domain name if we belong a domain, else None
    (if part of a network group, will also return None)
    '''
    # Status:
    # 0 = Unknown
    # 1 = Unjoined
    # 2 = Workgroup
    # 3 = Domain
    domain, status = win32net.NetGetJoinInformation()
    if status != 3:
        domain = None

    return domain


def getWindowsVersion():
    return win32api.GetVersionEx()

EWX_LOGOFF = 0x00000000
EWX_SHUTDOWN = 0x00000001
EWX_REBOOT = 0x00000002
EWX_FORCE = 0x00000004
EWX_POWEROFF = 0x00000008
EWX_FORCEIFHUNG = 0x00000010


def reboot(flags=EWX_FORCEIFHUNG | EWX_REBOOT):
    hproc = win32api.GetCurrentProcess()
    htok = win32security.OpenProcessToken(hproc, win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY)
    privs = ((win32security.LookupPrivilegeValue(None, win32security.SE_SHUTDOWN_NAME), win32security.SE_PRIVILEGE_ENABLED),)
    win32security.AdjustTokenPrivileges(htok, 0, privs)
    win32api.ExitWindowsEx(flags, 0)


def loggoff():
    win32api.ExitWindowsEx(EWX_LOGOFF)


def renameComputer(newName):
    # Needs admin privileges to work
    if ctypes.windll.kernel32.SetComputerNameExW(DWORD(win32con.ComputerNamePhysicalDnsHostname), LPCWSTR(newName)) == 0:  # @UndefinedVariable
        # win32api.FormatMessage -> returns error string
        # win32api.GetLastError -> returns error code
        # (just put this comment here to remember to log this when logger is available)
        error = getErrorMessage()
        computerName = win32api.GetComputerNameEx(win32con.ComputerNamePhysicalDnsHostname)
        raise Exception('Error renaming computer from {} to {}: {}'.format(computerName, newName, error))

NETSETUP_JOIN_DOMAIN = 0x00000001
NETSETUP_ACCT_CREATE = 0x00000002
NETSETUP_ACCT_DELETE = 0x00000004
NETSETUP_WIN9X_UPGRADE = 0x00000010
NETSETUP_DOMAIN_JOIN_IF_JOINED = 0x00000020
NETSETUP_JOIN_UNSECURE = 0x00000040
NETSETUP_MACHINE_PWD_PASSED = 0x00000080
NETSETUP_JOIN_WITH_NEW_NAME = 0x00000400
NETSETUP_DEFER_SPN_SET = 0x1000000


def joinDomain(domain, ou, account, password, executeInOneStep=False):
    '''
    Joins machine to a windows domain
    :param domain: Domain to join to
    :param ou: Ou that will hold machine
    :param account: Account used to join domain
    :param password: Password of account used to join domain
    :param executeInOneStep: If true, means that this machine has been renamed and wants to add NETSETUP_JOIN_WITH_NEW_NAME to request so we can do rename/join in one step.
    '''
    # If account do not have domain, include it
    if '@' not in account and '\\' not in account:
        if '.' in domain:
            account = account + '@' + domain
        else:
            account = domain + '\\' + account

    # Do log
    flags = NETSETUP_ACCT_CREATE | NETSETUP_DOMAIN_JOIN_IF_JOINED | NETSETUP_JOIN_DOMAIN

    if executeInOneStep:
        flags |= NETSETUP_JOIN_WITH_NEW_NAME

    flags = DWORD(flags)

    domain = LPCWSTR(domain)

    # Must be in format "ou=.., ..., dc=...,"
    ou = LPCWSTR(ou) if ou is not None and ou != '' else None
    account = LPCWSTR(account)
    password = LPCWSTR(password)

    res = ctypes.windll.netapi32.NetJoinDomain(None, domain, ou, account, password, flags)
    # Machine found in another ou, use it and warn this on log
    if res == 2224:
        flags = DWORD(NETSETUP_DOMAIN_JOIN_IF_JOINED | NETSETUP_JOIN_DOMAIN)
        res = ctypes.windll.netapi32.NetJoinDomain(None, domain, None, account, password, flags)
    if res != 0:
        # Log the error
        error = getErrorMessage(res)
        if res == 1355:
            error = "DC Is not reachable"
        logger.error('Error joining domain: {}, {}'.format(error, res))
        raise Exception('Error joining domain {}, with credentials {}/*****{}: {}, {}'.format(domain, account, ', under OU {}'.format(ou) if ou is not None else '', res, error))


def changeUserPassword(user, oldPassword, newPassword):
    computerName = LPCWSTR(getComputerName())
    user = LPCWSTR(user)
    oldPassword = LPCWSTR(oldPassword)
    newPassword = LPCWSTR(newPassword)

    res = ctypes.windll.netapi32.NetUserChangePassword(computerName, user, oldPassword, newPassword)

    if res != 0:
        # Log the error, and raise exception to parent
        error = getErrorMessage()
        raise Exception('Error changing password for user {}: {}'.format(user.value, error))


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint),
    ]


def initIdleDuration(atLeastSeconds):
    '''
    In windows, there is no need to set screensaver
    '''
    pass


def getIdleDuration():
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo))
    millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime  # @UndefinedVariable
    return millis / 1000.0


def getCurrentUser():
    '''
    Returns current logged in username
    '''
    return os.environ['USERNAME']
