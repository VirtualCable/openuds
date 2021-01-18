# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
try:
    import winreg as wreg
except ImportError:  # Python 2.7 fallback
    import _winreg as wreg  # type: ignore
import subprocess

from uds import tools  # type: ignore

try:
    k = wreg.OpenKey(wreg.HKEY_CURRENT_USER, 'Software\\Classes\\NXClient.session\\shell\\open\\command')  # @UndefinedVariable
    cmd = wreg.QueryValue(k, '')  # type: ignore
    wreg.CloseKey(k)
except Exception:
    raise Exception('''<p>You need to have installed NX Client version 3.5 in order to connect to this UDS service.</p>
<p>Please, install appropriate package for your system.</p>
''')

filename = tools.saveTempFile(sp['as_file'])  # type: ignore
cmd = cmd.replace('%1', filename)
tools.addTaskToWait(subprocess.Popen(cmd))
tools.addFileToUnlink(filename)
