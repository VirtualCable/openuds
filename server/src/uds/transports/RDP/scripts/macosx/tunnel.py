# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
import subprocess
import shutil
import os
import os.path

from uds.tunnel import forward  # type: ignore

from uds import tools  # type: ignore

# Inject local passed sp into globals for functions
globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def fixResolution():
    import re
    import subprocess

    results = str(
        subprocess.Popen(
            ['system_profiler SPDisplaysDataType'], stdout=subprocess.PIPE, shell=True
        ).communicate()[0]
    )
    groups = re.search(r': \d* x \d*', results)
    width, height = '1024', '768'  # Safe default values
    if groups:
        res = groups.group(0).split(' ')
        width, height = str(int(res[1]) - 4), str(
            int(int(res[3]) * 90 / 100)
        )  # Width and Height
    return list(map(lambda x: x.replace('#WIDTH#', width).replace('#HEIGHT#', height), sp['as_new_xfreerdp_params']))  # type: ignore


msrdc = (
    '/Applications/Microsoft Remote Desktop.app/Contents/MacOS/Microsoft Remote Desktop'
)
xfreerdp = tools.findApp('xfreerdp')
executable = None

# Check first xfreerdp, allow password redir
if xfreerdp and os.path.isfile(xfreerdp):
    executable = xfreerdp
elif msrdc and os.path.isfile(msrdc) and sp['as_file']:  # type: ignore
    executable = msrdc

if executable is None:
    if sp['as_rdp_url']:  # type: ignore
        raise Exception(
            '''<p><b>Microsoft Remote Desktop or xfreerdp not found</b></p>
            <p>In order to connect to UDS RDP Sessions, you need to have a<p>
            <ul>
                <li>
                    <p><b>Microsoft Remote Desktop</b> from Apple Store</p>
                </li>
                <li>
                    <p><b>Xfreerdp</b> from homebrew</p>
                </li>
            </ul>
            '''
        )
    else:
        raise Exception(
            '''<p><b>xfreerdp not found</b></p>
            <p>In order to connect to UDS RDP Sessions, you need to have a<p>
            <ul>
                <li>
                    <p><b>Xfreerdp</b> from homebrew</p>
                    <p>
                        <ul>
                            <li>Install brew (from <a href="https://brew.sh">brew website</a>)</li>
                            <li>Install xquartz<br/>
                                <b>brew install --cask xquartz</b></li>
                            <li>Install freerdp<br/>
                                <b>brew install freerdp</b></li>
                            <li>Reboot so xquartz will be automatically started when needed</li>
                        </ul>
                    </p>
                </li>
            </ul>
            '''
        )

# Open tunnel
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore
address = '127.0.0.1:{}'.format(fs.server_address[1])

# Check that tunnel works..
if fs.check() is False:
    raise Exception(
        '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
    )

if executable == msrdc:
    theFile = theFile = sp['as_file'].format(address=address)  # type: ignore

    filename = tools.saveTempFile(theFile)
    # Rename as .rdp, so open recognizes it
    shutil.move(filename, filename + '.rdp')

    # tools.addTaskToWait(subprocess.Popen(['open', filename + '.rdp']))
    # Force MSRDP to be used with -a (thanks to Dani Torregrosa @danitorregrosa (https://github.com/danitorregrosa) )
    tools.addTaskToWait(
        subprocess.Popen(
            [
                'open',
                '-a',
                '/Applications/Microsoft Remote Desktop.app',
                filename + '.rdp',
            ]
        )
    )
    tools.addFileToUnlink(filename + '.rdp')
elif executable == xfreerdp:
    # Fix resolution...
    try:
        xfparms = fixResolution()
    except Exception as e:
        xfparms = list(map(lambda x: x.replace('#WIDTH#', '1400').replace('#HEIGHT#', '800'), sp['as_new_xfreerdp_params']))  # type: ignore

    params = [
        os.path.expandvars(i)
        for i in [executable] + xfparms + ['/v:{}'.format(address)]
    ]
    subprocess.Popen(params)
