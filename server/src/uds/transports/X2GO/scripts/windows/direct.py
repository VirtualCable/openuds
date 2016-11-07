# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
from PyQt4 import QtCore, QtGui
import os
import subprocess

from uds import tools  # @UnresolvedImport

import six

keyFile = tools.saveTempFile('''{m.key}''')
theFile = '''{m.xf}'''.format(export='c:\\', keyFile=keyFile.replace('\\', '/'), ip='{m.ip}', port='22')
filename = tools.saveTempFile(theFile)

x2goPath = os.environ['PROGRAMFILES(X86)'] + '\\x2goclient'
executable = tools.findApp('x2goclient.exe', [x2goPath])
if executable is None:
    raise Exception('''<p>You must have installed latest X2GO Client in order to connect to this UDS service.</p>
<p>You can download it for windows from <a href="http://wiki.x2go.org/doku.php">X2Go Site</a>.</p>''')

# C:\Program Files (x86)\\x2goclient>x2goclient.exe --session-conf=c:/temp/sessions --session=UDS/test-session --close-disconnect --hide --no-menu

subprocess.Popen([executable, '--session-conf={{}}'.format(filename), '--session=UDS/connect', '--close-disconnect', '--hide', '--no-menu', '--add-to-known-hosts'])
# tools.addFileToUnlink(filename)
# tools.addFileToUnlink(keyFile)

# QtGui.QMessageBox.critical(parent, 'Notice', executable + ' -- ' + keyFile + ', ' + filename, QtGui.QMessageBox.Ok)  # @UndefinedVariable
