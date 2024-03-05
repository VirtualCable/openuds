# This is a template
# Saved as .py for easier editing
# from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable

import os
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

# Care, expanduser is encoding using "mcbs", so treat it as bytes on python 2.7
home = expanduser('~').replace('\\', '\\\\') + '#1;'
keyFile = tools.save_temp_file(sp['key'])  # type: ignore
theFile = sp['xf'].format(export=home, keyFile=keyFile.replace('\\', '/'), ip='127.0.0.1', port=fs.server_address[1])  # type: ignore
filename = tools.save_temp_file(theFile)

x2goPath = os.environ['PROGRAMFILES(X86)'] + '\\x2goclient'
executable = tools.find_application('x2goclient.exe', [x2goPath])
if executable is None:
    raise Exception(
        '''<p>You must have installed latest X2GO Client in default program file folder in order to connect to this UDS service.</p>
<p>You can download it for windows from <a href="http://wiki.x2go.org/doku.php">X2Go Site</a>.</p>'''
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
