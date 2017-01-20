# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
import subprocess
from uds.forward import forward  # @UnresolvedImport
import os

from uds import tools  # @UnresolvedImport


cmd = '/Applications/OpenNX/OpenNX.app/Contents/MacOS/OpenNXapp'
if os.path.isfile(cmd) is False:
    raise Exception('''<p>You need to have installed Open NX Client in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system from <a href="http://www.opennx.net/">here</a>.</p>
''')

forwardThread, port = forward('{m.tunHost}', '{m.tunPort}', '{m.tunUser}', '{m.tunPass}', '{m.ip}', {m.port})  # @UndefinedVariable
if forwardThread.status == 2:
    raise Exception('Unable to open tunnel')


theFile = '''{r.as_file_for_format}'''.format(
    address='127.0.0.1',
    port=port
)

filename = tools.saveTempFile(theFile)

cmd = cmd.replace('%1', filename)
tools.addTaskToWait(subprocess.Popen([cmd, '--session={{}}'.format(filename), '--autologin', '--killerrors']))
tools.addFileToUnlink(filename)
