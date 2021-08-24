# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module
import os
import subprocess

from uds import tools  # type: ignore

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


theFile = sp['as_file']  # type: ignore

filename = tools.saveTempFile(theFile)

subprocess.Popen([remoteViewer, filename])
