# -*- coding: utf-8 -*-

from __future__ import unicode_literals


from win32com.shell import shell
import _winreg


path = 'Software\\UDS Enterprise'

def checkPermissions():
    return shell.IsUserAnAdmin()

def readConfig():
    try:
        key = wreg.OpenKey(_wreg.HKEY_LOCAL_MACHINE, path, 0, _wreg.KEY_ALL_ACCESS)

    except:
        pass
