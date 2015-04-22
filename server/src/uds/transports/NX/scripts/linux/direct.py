# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
from PyQt4 import QtCore, QtGui  # @UnusedImport
import subprocess

from uds import tools  # @UnresolvedImport


try:
    cmd = tools.findApp('nxclient', ['/usr/NX/bin/'])
    if cmd is None:
        raise Exception()

except Exception:
    raise Exception('''<p>You need to have installed NX Client version 3.5 in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
''')

filename = tools.saveTempFile('''{r.as_file}''')
tools.addTaskToWait(subprocess.Popen([cmd, '--session', filename]))
tools.addFileToUnlink(filename)
