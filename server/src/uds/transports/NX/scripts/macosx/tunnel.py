# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
import subprocess
from uds.tunnel import forward  # type: ignore
import os

from uds import tools  # type: ignore


cmd = '/Applications/OpenNX/OpenNX.app/Contents/MacOS/OpenNXapp'
if os.path.isfile(cmd) is False:
    raise Exception('''<p>You need to have installed Open NX Client in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system from <a href="http://www.opennx.net/">here</a>.</p>
''')

# Open tunnel
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])

# Check that tunnel works..
if fs.check() is False:
    raise Exception('<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>')

theFile = sp['as_file_for_format'].format(
    address='127.0.0.1',
    port=fs.server_address[1]
)

filename = tools.saveTempFile(theFile)

tools.addTaskToWait(subprocess.Popen([cmd, '--session={}'.format(filename), '--autologin', '--killerrors']))
tools.addFileToUnlink(filename)
