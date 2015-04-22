# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
from PyQt4 import QtCore, QtGui  # @UnusedImport
import _winreg
import subprocess

from uds import tools  # @UnresolvedImport


try:
    k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, 'Software\\Classes\\NXClient.session\\shell\\open\\command')  # @UndefinedVariable
    cmd = _winreg.QueryValue(k, '')  # @UndefinedVariable
except Exception:
    raise Exception('''<p>You need to have installed NX Client version 3.5 in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
''')

filename = tools.saveTempFile('''{r.as_file}''')
cmd = cmd.replace('%1', filename)
tools.addTaskToWait(subprocess.Popen(cmd))
tools.addFileToUnlink(filename)
