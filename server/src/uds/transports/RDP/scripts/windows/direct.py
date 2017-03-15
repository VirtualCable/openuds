from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import win32crypt  # @UnresolvedImport
import os
import subprocess

from uds import tools  # @UnresolvedImport

import six

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
theFile = sp['as_file'].format(password=win32crypt.CryptProtectData(six.binary_type(sp['password'].encode('UTF-16LE')), None, None, None, None, 0x01).encode('hex'))  # @UndefinedVariable

filename = tools.saveTempFile(theFile)
executable = tools.findApp('mstsc.exe')
subprocess.Popen([executable, filename])
tools.addFileToUnlink(filename)
