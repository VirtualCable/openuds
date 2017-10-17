# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import win32crypt  # @UnresolvedImport
import subprocess

from uds import tools  # @UnresolvedImport

import six

thePass = six.binary_type('{m.password}'.encode('UTF-16LE'))
try:
    password = win32crypt.CryptProtectData(thePass, None, None, None, None, 0x01).encode('hex')
except Exception:
    # Cannot encrypt for user, trying for machine
    password = win32crypt.CryptProtectData(thePass, None, None, None, None, 0x05).encode('hex')

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
theFile = '''{m.r.as_file}'''.format(password=password)

filename = tools.saveTempFile(theFile)
executable = tools.findApp('mstsc.exe')
subprocess.Popen([executable, filename])
tools.addFileToUnlink(filename)
