# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, undefined-variable
import subprocess

from uds import tools  # @UnresolvedImport
from uds.forward import forward  # @UnresolvedImport

executable = tools.findApp('remote-viewer')

if executable is None:
    raise Exception('''<p>You need to have installed virt-viewer to connect to this UDS service.</p>
<p>
    Please, install appropriate package for your system.
</p>
<p>
    Please, install appropriate package for your Linux system. (probably named something like <b>virt-viewer</b>)
</p>
''')


if {m.port} != -1:  # @UndefinedVariable
    forwardThread1, port = forward('{m.tunHost}', '{m.tunPort}', '{m.tunUser}', '{m.tunPass}', '{m.ip}', {m.port})  # @UndefinedVariable

    if forwardThread1.status == 2:
        raise Exception('Unable to open tunnel')
else:
    port = -1

if {m.secure_port} != -1:  # @UndefinedVariable
    forwardThread2, secure_port = forwardThread1.clone('{m.ip}', {m.secure_port})  # @UndefinedVariable

    if forwardThread2.status == 2:
        raise Exception('Unable to open tunnel')
else:
    secure_port = -1

theFile = '''{m.r.as_file}'''.format(
    secure_port=secure_port,
    port=port
)

filename = tools.saveTempFile(theFile)


subprocess.Popen([executable, filename])
