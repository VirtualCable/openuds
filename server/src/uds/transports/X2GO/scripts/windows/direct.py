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

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
keyFile = tools.saveTempFile('''{m.key}''')
theFile = '''{m.xf}'''.format(exports='c:\\', keyFile=keyFile.replace('\\', '/'), ip='{m.ip}')
filename = tools.saveTempFile(theFile)

x2goPath = os.environ['PROGRAMFILES(X86)'] + '\\x2goclient'
executable = tools.findApp('x2goclient.exe', [x2goPath])

# executable = tools.findApp('mstsc.exe')
# subprocess.Popen([executable, filename])
# tools.addFileToUnlink(filename)

QtGui.QMessageBox.critical(parent, 'Notice', executable + ' -- ' + keyFile + ', ' + filename, QtGui.QMessageBox.Ok)  # @UndefinedVariable
