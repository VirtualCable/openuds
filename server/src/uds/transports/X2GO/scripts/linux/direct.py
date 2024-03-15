# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import subprocess
from os.path import expanduser

from uds import tools  # type: ignore

home = expanduser('~') + ':1;/media:1;'
keyFile = tools.saveTempFile(sp['key'])  # type: ignore
theFile = sp['xf'].format(export=home, keyFile=keyFile.replace('\\', '/'), ip=sp['ip'], port=sp['port'])  # type: ignore
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
# tools.addFileToUnlink(filename)
# tools.addFileToUnlink(keyFile)
