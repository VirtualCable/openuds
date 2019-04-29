# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import _winreg
import subprocess
from uds.forward import forward  # @UnresolvedImport

from uds import tools  # @UnresolvedImport


try:
    k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, 'Software\\Classes\\NXClient.session\\shell\\open\\command')  # @UndefinedVariable
    cmd = _winreg.QueryValue(k, '')  # @UndefinedVariable
except Exception:
    raise Exception('''<p>You need to have installed NX Client version 3.5 in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
''')

forwardThread, port = forward(sp['tunHost'], sp['tunPort'], sp['tunUser'], sp['tunPass'], sp['ip'], sp['port'])  # @UndefinedVariable
if forwardThread.status == 2:
    raise Exception('Unable to open tunnel')


theFile = sp['as_file_for_format'].format(  # @UndefinedVariable
    address='127.0.0.1',
    port=port
)

filename = tools.saveTempFile(theFile)

cmd = cmd.replace('%1', filename)
tools.addTaskToWait(subprocess.Popen(cmd))
tools.addFileToUnlink(filename)
