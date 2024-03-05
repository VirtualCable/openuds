# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import os
import glob
import subprocess

from uds import tools  # type: ignore
from uds.tunnel import forward  # type: ignore

# Lets find remote viewer
# There is a bug that when installed, the remote viewer (at least 64 bits version) does not store correctly its path, so lets find it "a las bravas"
extraPaths = ()
for env in ('PROGRAMFILES', 'PROGRAMW6432'):
    if env in os.environ:
        extraPaths += tuple(p + '\\bin' for p in glob.glob(os.environ[env] + '\\VirtViewer*'))  # type: ignore

executable = tools.find_application('remote-viewer.exe', extraPaths)

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
theFile = sp['as_file_ns']  # type: ignore
fs = None
if sp['ticket']:  # type: ignore
    # Open tunnel
    fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

    # Check that tunnel works..
    if fs.check() is False:
        raise Exception(
            '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
        )

fss = None
if sp['ticket_secure']:  # type: ignore
    theFile = sp['as_file']
    # Open tunnel
    fss = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket_secure'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

    # Check that tunnel works..
    if fss.check() is False:
        raise Exception(
            '<p>Could not connect to tunnel server 2.</p><p>Please, check your network settings.</p>'
        )

theFile = theFile.format(
    secure_port='-1' if not fss else fss.server_address[1],
    port='-1' if not fs else fs.server_address[1],
)

filename = tools.save_temp_file(theFile)

subprocess.Popen([executable, filename])
