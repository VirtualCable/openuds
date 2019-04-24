# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import subprocess
import win32crypt  # @UnresolvedImport
try:
    import winreg as wreg
except ImportError:  # Python 2.7 fallback
    import _winreg as wreg  # @UnresolvedImport, pylint: disable=import-error

from uds.log import logger  # @UnresolvedImport
from uds import tools  # @UnresolvedImport

import six

try:
    thePass = six.binary_type(sp['password'].encode('UTF-16LE'))  # @UndefinedVariable
    password = win32crypt.CryptProtectData(thePass, None, None, None, None, 0x01).encode('hex')
except Exception:
    logger.info('Cannot encrypt for user, trying for machine')
    password = win32crypt.CryptProtectData(thePass, None, None, None, None, 0x05).encode('hex')

try:
    key = wreg.OpenKey(wreg.HKEY_CURRENT_USER, 'Software\Microsoft\Terminal Server Client\LocalDevices', 0, wreg.KEY_SET_VALUE)  # @UndefinedVariable
    wreg.SetValueEx(key, sp['ip'], 0, wreg.REG_DWORD, 255)  # @UndefinedVariable
    wreg.CloseKey(key)  # @UndefinedVariable
except Exception as e:
    logger.warn('Exception fixing redirection dialog: %s', e)

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
theFile = sp['as_file'].format(# @UndefinedVariable
    password=password
)
filename = tools.saveTempFile(theFile)
executable = tools.findApp('mstsc.exe')
subprocess.Popen([executable, filename])
tools.addFileToUnlink(filename)

