# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import os
import glob
import subprocess

from uds import tools  # type: ignore

# Lets find remote viewer
# There is a bug that when installed, the remote viewer (at least 64 bits version) does not store correctly its path, so lets find it "a las bravas"
extraPaths = ()
for env in ('PROGRAMFILES', 'PROGRAMW6432'):
    if env in os.environ:
        extraPaths += tuple(p + '\\bin' for p in glob.glob(os.environ[env] + '\\VirtViewer*'))  # type: ignore

executable = tools.findApp('remote-viewer.exe', extraPaths)

if executable is None:
    raise Exception(
        '''<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>
    Please, install appropriate package for your system.
</p>
<p>
    <a href="http://virt-manager.org/download/">Open download page</a>
</p>
'''
    )

theFile = sp['as_file']  # type: ignore

filename = tools.saveTempFile(theFile)

subprocess.Popen([executable, filename])
