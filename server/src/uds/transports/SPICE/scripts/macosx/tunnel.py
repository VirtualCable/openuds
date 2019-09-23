# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import os
import subprocess

from uds import tools  # @UnresolvedImport
from uds.forward import forward  # @UnresolvedImport

remoteViewer = '/Applications/RemoteViewer.app/Contents/MacOS/RemoteViewer'

if not os.path.isfile(remoteViewer):
    raise Exception('''<p>You need to have installed virt-viewer to connect to this UDS service.</p>
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
''')

theFile = sp['as_file_ns']
if sp['port'] != '-1':
    forwardThread1, port = forward(sp['tunHost'], sp['tunPort'], sp['tunUser'], sp['tunPass'], sp['ip'], sp['port'])


    if forwardThread1.status == 2:
        raise Exception('Unable to open tunnel')
else:
    port = -1

if sp['secure_port'] != '-1':
    theFile = sp['as_file']
    if port != -1:
        forwardThread2, secure_port = forwardThread1.clone(sp['ip'], sp['secure_port'])
    else:
        forwardThread2, secure_port = forward(sp['tunHost'], sp['tunPort'], sp['tunUser'], sp['tunPass'], sp['ip'], sp['secure_port'])

    if forwardThread2.status == 2:
        raise Exception('Unable to open tunnel')
else:
    secure_port = -1

theFile = theFile.format(
    secure_port=secure_port,
    port=port
)

filename = tools.saveTempFile(theFile)
subprocess.Popen([remoteViewer, filename])
