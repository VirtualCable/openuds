# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable

import os
import subprocess
from uds.forward import forward  # @UnresolvedImport
from os.path import expanduser

from uds import tools  # @UnresolvedImport

import six

forwardThread, port = forward('{m.tunHost}', '{m.tunPort}', '{m.tunUser}', '{m.tunPass}', '{m.ip}', 22)

if forwardThread.status == 2:
    raise Exception('Unable to open tunnel')

tools.addTaskToWait(forwardThread)

home = expanduser('~') + ':1;'
keyFile = tools.saveTempFile('''{m.key}''')
theFile = '''{m.xf}'''.format(export=home, keyFile=keyFile.replace('\\', '/'), ip='127.0.0.1', port=port)
filename = tools.saveTempFile(theFile)

# HOME=[temporal folder, where we create a .x2goclient folder and a sessions inside] pyhoca-cli -P UDS/test-session

executable = tools.findApp('x2goclient')
if executable is None:
    raise Exception('''<p>You must have installed latest X2GO Client in order to connect to this UDS service.</p>
<p>Please, install the required packages for your platform</p>''')

subprocess.Popen([executable, '--session-conf={{}}'.format(filename), '--session=UDS/connect', '--close-disconnect', '--hide', '--no-menu', '--add-to-known-hosts'])

