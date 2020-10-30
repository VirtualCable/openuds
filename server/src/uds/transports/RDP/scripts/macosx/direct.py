# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
import subprocess
import os

from uds import tools  # @UnresolvedImport

# Inject local passed sp into globals for functions
globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable

msrdc = '/Applications/Microsoft Remote Desktop.app/Contents/MacOS/Microsoft Remote Desktop'
xfreerdp = 'xfreerdp' # TODO
executable = None

# Check first xfreerdp, allow password redir
if os.path.isfile(xfreerdp):
    executable = xfreerdp
elif os.path.isfile(msrdc) and sp['as_rdp_url']:
    executable = msrdc

if executable is None:
    if sp['as_rdp_url']:
        raise Exception('''<p><b>Microsoft Remote Desktop or xfreerdp not found</b></p>
            <p>In order to connect to UDS RDP Sessions, you need to have a<p>
            <ul>
                <li>
                    <p><b>Microsoft Remote Desktop</b> from Apple Store</p>
                </li>
                <li>
                    <p><b>Xfreerdp</b> from homebrew</p>
                </li>
            </ul>
            ''')
    else:
        raise Exception('''<p><b>xfreerdp not found</b></p>
            <p>In order to connect to UDS RDP Sessions, you need to have a<p>
            <ul>
                <li>
                    <p><b>Xfreerdp</b> from homebrew</p>
                </li>
            </ul>
            ''')
elif executable == msrdc:
    url = sp['as_rdp_url']  # @UndefinedVariable

    tools.addTaskToWait(subprocess.Popen(['open', url]))
