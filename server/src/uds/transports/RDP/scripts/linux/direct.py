# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
import subprocess
import re

from uds import tools  # @UnresolvedImport

import six


def execNewXFreeRdp(parent, xfreerdp):
    import subprocess  # @Reimport
    params = [xfreerdp] + {m.r.as_new_xfreerdp_params} + ['/v:{m.r.address}']  # @UndefinedVariable
    tools.addTaskToWait(subprocess.Popen(params))


def execRdesktop(parent, rdesktop):
    import subprocess  # @Reimport
    params = [rdesktop] + {m.r.as_rdesktop_params} + ['{m.r.address}']  # @UndefinedVariable
    p = subprocess.Popen(params, stdin=subprocess.PIPE)
    if '{m.password}' != '':
        p.stdin.write('{m.password}')
    p.stdin.close()
    tools.addTaskToWait(p)

# Try to locate a "valid" version of xfreerdp as first option (<1.1 does not allows drive redirections, so it will not be used if found)
xfreerdp = tools.findApp('xfreerdp')
rdesktop = tools.findApp('rdesktop')
fnc, app = None, None

if rdesktop is not None:
    fnc, app = execRdesktop, rdesktop

if xfreerdp is not None:
    # Check for nice version
    try:
        try:
            version = subprocess.check_output([xfreerdp, '--version'])
        except subprocess.CalledProcessError as e:
            version = e.output

        version = float(re.search(r'version ([0-9]*\.[0-9]*)', version).groups()[0])
        if version < 1.1:
            raise Exception()
        else:
            fnc, app = execNewXFreeRdp, xfreerdp

    except Exception as e:  # Valid version not found, pass to check rdesktop
        pass

if app is None or fnc is None:
    raise Exception('''<p>You need to have installed xfreerdp (>= 1.1) or rdesktop, and have them in your PATH in order to connect to this UDS service.</p>
    <p>Please, install apropiate package for your system.</p>
    <p>Also note that xfreerdp prior to version 1.1 will not be taken into consideration.</p>
''')
else:
    fnc(parent, app)  # @UndefinedVariable
