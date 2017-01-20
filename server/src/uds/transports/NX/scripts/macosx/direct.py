# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
import subprocess
import os

from uds import tools  # @UnresolvedImport


cmd = '/Applications/OpenNX/OpenNX.app/Contents/MacOS/OpenNXapp'
if os.path.isfile(cmd) is False:
    raise Exception('''<p>You need to have installed Open NX Client in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system from <a href="http://www.opennx.net/">here</a>.</p>
''')


filename = tools.saveTempFile('''{r.as_file}''')
tools.addTaskToWait(subprocess.Popen([cmd, '--session={{}}'.format(filename), '--autologin', '--killerrors']))
tools.addFileToUnlink(filename)
