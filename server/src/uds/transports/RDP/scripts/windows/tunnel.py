# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args

from PyQt4 import QtCore, QtGui
import win32crypt  # @UnresolvedImport
import os
import subprocess
from uds.forward import forward  # @UnresolvedImport

from uds import tools  # @UnresolvedImport

import six

forwardThread, port = forward('{tunHost}', '{tunPort}', '{tunUser}', '{tunPass}', '{server}', '{port}')

theFile = '''{file}'''.format(
    password=win32crypt.CryptProtectData(six.binary_type('{password}'.encode('UTF-16LE')), None, None, None, None, 0x01).encode('hex'),
    address='127.0.0.1:{{}}'.format(port)
)

filename = tools.saveTempFile(theFile)
executable = os.path.join(os.path.join(os.environ['WINDIR'], 'system32'), 'mstsc.exe')


subprocess.call([executable, filename])
tools.addFileToUnlink(filename)

# QtGui.QMessageBox.critical(parent, 'Notice', filename + ", " + executable, QtGui.QMessageBox.Ok)
