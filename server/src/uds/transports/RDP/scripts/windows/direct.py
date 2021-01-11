# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import subprocess
import win32crypt  # type: ignore
import codecs

try:
    import winreg as wreg
except ImportError:  # Python 2.7 fallback
    import _winreg as wreg  # type: ignore

from uds.log import logger  # type: ignore
from uds import tools  # type: ignore

import six

try:
    thePass = six.binary_type(sp['password'].encode('UTF-16LE'))  # type: ignore
    password = codecs.encode(win32crypt.CryptProtectData(thePass, None, None, None, None, 0x01), 'hex').decode()
except Exception:
    # logger.info('Cannot encrypt for user, trying for machine')
    password = codecs.encode(win32crypt.CryptProtectData(thePass, None, None, None, None, 0x05), 'hex').decode()

try:
    key = wreg.OpenKey(wreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\Terminal Server Client\\LocalDevices', 0, wreg.KEY_SET_VALUE)  # @UndefinedVariable
    wreg.SetValueEx(key, sp['ip'], 0, wreg.REG_DWORD, 255)  # @UndefinedVariable
    wreg.CloseKey(key)  # @UndefinedVariable
except Exception as e:
    # logger.warn('Exception fixing redirection dialog: %s', e)
    pass  # Key does not exists, ok...

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
theFile = sp['as_file'].format(# @UndefinedVariable
    password=password
)
filename = tools.saveTempFile(theFile)
executable = tools.findApp('mstsc.exe')

if executable is None:
    raise Exception('Unable to find mstsc.exe. Check that path points to your SYSTEM32 folder')

subprocess.Popen([executable, filename])
tools.addFileToUnlink(filename)

