# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable

import subprocess
from uds.tunnel import forward  # type: ignore
from os.path import expanduser

from uds import tools  # type: ignore

# Open tunnel
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

# Check that tunnel works..
if fs.check() is False:
    raise Exception(
        '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
    )

home = expanduser('~') + ':1;/media:1;'
keyFile = tools.saveTempFile(sp['key'])  # type: ignore
theFile = sp['xf'].format(export=home, keyFile=keyFile.replace('\\', '/'), ip='127.0.0.1', port=fs.server_address[1])  # type: ignore
filename = tools.saveTempFile(theFile)

# HOME=[temporal folder, where we create a .x2goclient folder and a sessions inside] pyhoca-cli -P UDS/test-session

executable = tools.findApp('x2goclient')
if executable is None:
    raise Exception(
        '''<p>You must have installed latest X2GO Client in order to connect to this UDS service.</p>
<p>Please, install the required packages for your platform</p>'''
    )

subprocess.Popen(
    [
        executable,
        '--session-conf={}'.format(filename),
        '--session=UDS/connect',
        '--close-disconnect',
        '--hide',
        '--no-menu',
        '--add-to-known-hosts',
    ]
)
