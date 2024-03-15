# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import subprocess

from uds import tools  # type: ignore

executable = tools.findApp('remote-viewer')

if executable is None:
    raise Exception(
        '''<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>
    Please, install appropriate package for your Linux system. (probably named something like <b>remote-viewer</b>)
</p>
'''
    )

theFile = sp['as_file']  # type: ignore

filename = tools.saveTempFile(theFile)

subprocess.Popen([executable, filename])
