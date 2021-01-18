# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import subprocess
from uds.tunnel import forward  # type: ignore

from uds import tools  # type: ignore

try:
    cmd = tools.findApp('nxclient', ['/usr/NX/bin/'])
    if cmd is None:
        raise Exception()
except Exception:
    raise Exception('''<p>You need to have installed NX Client version 3.5 in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
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

cmd = cmd.replace('%1', filename)
tools.addTaskToWait(subprocess.Popen([cmd, '--session', filename]))
tools.addFileToUnlink(filename)
