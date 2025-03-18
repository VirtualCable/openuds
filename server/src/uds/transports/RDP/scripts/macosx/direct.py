import typing
import shutil
import os
import os.path

# On older client versions, need importing globally to allow inner functions to work
import subprocess  # type: ignore

# Avoid type checking annoing errors
try:
    from uds import tools  # type: ignore
except ImportError:
    tools: typing.Any = None
    raise

if 'sp' not in globals():
    # Inject local passed sp into globals for inner functions if not already there
    globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def fix_resolution() -> typing.List[str]:
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
        width, height = str(int(res[1]) - 4), str(int(int(res[3]) * 90 / 100))  # Width and Height
    return list(map(lambda x: x.replace('#WIDTH#', width).replace('#HEIGHT#', height), sp['as_new_xfreerdp_params']))  # type: ignore


msrdc_list = [
    '/Applications/Microsoft Remote Desktop.app',
    '/Applications/Microsoft Remote Desktop.localized/Microsoft Remote Desktop.app',
    '/Applications/Windows App.app',
    '/Applications/Windows App.localized/Windows App.app',
]

thincast_list = [
    '/Applications/Thincast Remote Desktop Client.app/Contents/MacOS/Thincast Remote Desktop Client',
]

xfreerdp_list = [
    'udsrdp',
    'xfreerdp',
    'xfreerdp3',
    'xfreerdp2',
]


executable = None
kind = ''

# Check first thincast (better option right now, prefer it)
for thincast in thincast_list:
    if os.path.isfile(thincast):
        executable = thincast
        kind = 'thincast'
        break

if not executable:
    for xfreerdp_executable in xfreerdp_list:
        xfreerdp: str = tools.findApp(xfreerdp_executable)
        if xfreerdp and os.path.isfile(xfreerdp):
            executable = xfreerdp
            # Ensure that the kind is 'xfreerdp' and not 'xfreerdp3' or 'xfreerdp2'
            kind = xfreerdp_executable.rstrip('3').rstrip('2')
            break
    else:
        for msrdc in msrdc_list:
            if os.path.isdir(msrdc) and sp['as_file']:  # type: ignore
                executable = msrdc
                kind = 'msrdc'
                break

if not executable:
    msrd = msrd_li = ''
    if sp['as_rdp_url']:  # type: ignore
        msrd = ', Microsoft Remote Desktop'
        msrd_li = '<li><p><b>{}</b> from Apple Store</p></li>'.format(msrd)

    raise Exception(
        f'''<p><b>xfreerdp{msrd} or thincast client not found</b></p>
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
            {msrd_li}
            <li>
                <p>ThinCast Remote Desktop Client (from <a href="https://thincast.com/en/products/client">thincast website</a>)</p>
            </li>
        </ul>
        '''
    )

if kind == 'msrdc':
    theFile = sp['as_file']  # type: ignore
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
                executable,
                filename + '.rdp',
            ]
        )
    )
    tools.addFileToUnlink(filename + '.rdp')
else:  # thincast, udsrdp, freerdp
    # Fix resolution...
    try:
        xfparms = fix_resolution()
    except Exception as e:
        xfparms = list(map(lambda x: x.replace('#WIDTH#', '1400').replace('#HEIGHT#', '800'), sp['as_new_xfreerdp_params']))  # type: ignore

    params = [os.path.expandvars(i) for i in [executable] + xfparms + ['/v:{}'.format(sp['address'])]]  # type: ignore
    subprocess.Popen(params)
