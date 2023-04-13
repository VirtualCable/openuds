# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import os
import subprocess

from uds import tools  # type:  ignore
from uds.tunnel import forward  # type: ignore

remoteViewer = '/Applications/RemoteViewer.app/Contents/MacOS/RemoteViewer'

if not os.path.isfile(remoteViewer):
    raise Exception(
        '''<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>
    Please, install appropriate package for your system.
</p>
<p>
    <a href="http://people.freedesktop.org/~teuf/spice-gtk-osx/dmg/0.5.7/RemoteViewer-0.5.7-1.dmg">Open download page</a>
</p>
<p>
    Please, note that in order to UDS Connector to work correctly, you must copy the Remote Viewer app to your Applications Folder.<br/>
    Also remember, that in order to allow this app to run on your system, you must open it one time once it is copied to your App folder
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
    # Open tunnel
    theFile = sp['as_file']
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

filename = tools.saveTempFile(theFile)
subprocess.Popen([remoteViewer, filename])
