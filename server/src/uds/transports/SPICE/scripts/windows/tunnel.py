# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import os
import glob
import subprocess

from uds import tools  # @UnresolvedImport
from uds.forward import forward  # @UnresolvedImport

# Lets find remote viewer
# There is a bug that when installed, the remote viewer (at least 64 bits version) does not store correctly its path, so lets find it "a las bravas"
extraPaths = ()
for env in ('PROGRAMFILES', 'PROGRAMW6432'):
    if env in os.environ:
        extraPaths += tuple(p + '\\bin' for p in glob.glob(os.environ[env] + '\\VirtViewer*'))

executable = tools.findApp('remote-viewer.exe', extraPaths)

if executable is None:
    raise Exception('''<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>
    Please, install appropriate package for your system.
</p>
<p>
    <a href="http://virt-manager.org/download/">Open download page</a>
</p>
''')
theFile = '''{m.r.as_file_ns}'''
if {m.port} != -1:  # @UndefinedVariable
    forwardThread1, port = forward('{m.tunHost}', '{m.tunPort}', '{m.tunUser}', '{m.tunPass}', '{m.ip}', {m.port})  # @UndefinedVariable

    if forwardThread1.status == 2:
        raise Exception('Unable to open tunnel')
else:
    port = -1

if {m.secure_port} != -1:  # @UndefinedVariable
    theFile = '''{m.r.as_file}'''
    if port != -1:
        forwardThread2, secure_port = forwardThread1.clone('{m.ip}', {m.secure_port})  # @UndefinedVariable
    else:
        forwardThread2, secure_port = forward('{m.tunHost}', '{m.tunPort}', '{m.tunUser}', '{m.tunPass}', '{m.ip}', {m.secure_port})  # @UndefinedVariable


    if forwardThread2.status == 2:
        raise Exception('Unable to open tunnel')
else:
    secure_port = -1

theFile = theFile.format(
    secure_port=secure_port,
    port=port
)

filename = tools.saveTempFile(theFile)

subprocess.Popen([executable, filename])
