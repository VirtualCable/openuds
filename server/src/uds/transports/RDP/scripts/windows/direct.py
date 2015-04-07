# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
from PyQt4 import QtCore, QtGui
import win32crypt  # @UnresolvedImport
import os
import subprocess

from uds import tools  # @UnresolvedImport

import six

theFile = '''{file}'''.format(password=win32crypt.CryptProtectData(six.binary_type('{password}'.encode('UTF-16LE')), None, None, None, None, 0x01).encode('hex'))

filename = tools.saveTempFile(theFile)
executable = os.path.join(os.path.join(os.environ['WINDIR'], 'system32'), 'mstsc.exe')
subprocess.call([executable, filename])
# tools.addFileToUnlink(filename)

# QtGui.QMessageBox.critical(parent, 'Notice', filename + ", " + executable, QtGui.QMessageBox.Ok)
