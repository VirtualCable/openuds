import typing
import shutil
import os
import os.path
import logging

logger = logging.getLogger(__name__)

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
    '/Applications/Thincast Remote Desktop Client.app',
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
logger.debug('Searching for Thincast in: %s', thincast_list)
for thincast in thincast_list:
    if os.path.isdir(thincast):
        logger.debug('Thincast found: %s', thincast)
        executable = thincast
        kind = 'thincast'
        break

if not executable:
    logger.debug('Searching for xfreerdp in: %s', xfreerdp_list)
    found_xfreerdp = False
    for xfreerdp_executable in xfreerdp_list:
        xfreerdp = tools.findApp(xfreerdp_executable) # type: ignore
        logger.debug('tools.findApp(%s) result: %s', xfreerdp_executable, xfreerdp) # type: ignore
        if xfreerdp and os.path.isfile(xfreerdp): # type: ignore
            logger.debug('xfreerdp found: %s', xfreerdp) # type: ignore
            executable = xfreerdp # type: ignore
            # Ensure that the kind is 'xfreerdp' and not 'xfreerdp3' or 'xfreerdp2'
            kind = xfreerdp_executable.rstrip('3').rstrip('2')
            break
    if not found_xfreerdp:
        logger.debug('Searching for MSRDC in: %s', msrdc_list)
        for msrdc in msrdc_list:
            if os.path.isdir(msrdc) and sp['as_file']:  # type: ignore
                executable = msrdc
                kind = 'msrdc'
                break

if not executable:
    logger.debug('No compatible executable found (Thincast, xfreerdp, MSRDC)')
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

logger.debug('Using %s client of kind %s', executable, kind) # type: ignore

if kind == 'msrdc':
    theFile = sp['as_file']  # type: ignore
    filename = tools.saveTempFile(theFile) # type: ignore
    # Rename as .rdp, so open recognizes it
    shutil.move(filename, filename + '.rdp') # type: ignore

    # tools.addTaskToWait(subprocess.Popen(['open', filename + '.rdp']))
    # Force MSRDP to be used with -a (thanks to Dani Torregrosa @danitorregrosa (https://github.com/danitorregrosa))
    tools.addTaskToWait( # type: ignore
        subprocess.Popen(
            [
                'open',
                '-a',
                executable,
                filename + '.rdp',
            ] # type: ignore
        )
    )
    tools.addFileToUnlink(filename + '.rdp') # type: ignore


if kind == 'thincast':
    if sp['as_file']:  # type: ignore
        logger.debug('Opening Thincast with RDP file %s', sp['as_file']) # type: ignore
        theFile = sp['as_file']  # type: ignore
        filename = tools.saveTempFile(theFile) # type: ignore

        # # add to file the encrypted password for RDP
        # import win32crypt
        # import binascii

        # def encrypt_password_rdp(plain_text_password):
        #     # Convert password to UTF-16-LE (Unicode string used by RDP)
        #     data = plain_text_password.encode('utf-16-le')
        #     # Encrypt with DPAPI (CryptProtectData)
        #     encrypted_data = win32crypt.CryptProtectData(data, None, None, None, None, 0)
        #     # Convert bytes to hexadecimal for RDP
        #     encrypted_hex = binascii.hexlify(encrypted_data).decode('ascii')
        #     return encrypted_hex

        # filename_handle = open(filename, 'a') # type: ignore
        # if sp.get('password', ''):  # type: ignore
        #     encrypted_password = encrypt_password_rdp(sp["password"])
        #     filename_handle.write(f'password 51:b:{encrypted_password}\n')  # type: ignore
        # filename_handle.close()

        # add to file the password without encryption (Thincast will encrypt it)
        filename_handle = open(filename, 'a') # type: ignore
        if sp.get('password', ''):  # type: ignore
            filename_handle.write(f'password 51:b:{sp["password"]}\n')  # type: ignore
        filename_handle.close()

        # Rename as .rdp, so open recognizes it
        shutil.move(filename, filename + '.rdp') # type: ignore
        params = [ # type: ignore
            'open',
            '-a',
            executable,
            filename + '.rdp', # type: ignore
        ]
        logger.debug('Opening Thincast with RDP file with params: %s', ' '.join(params)) # type: ignore
        tools.addTaskToWait( # type: ignore
            subprocess.Popen(params) # type: ignore
        )
        tools.addFileToUnlink(filename + '.rdp') # type: ignore
    else:
        logger.debug('Opening Thincast with xfreerdp parameters')
        # Fix resolution...
        try:
            xfparms = fix_resolution()
        except Exception as e:
            xfparms = list(map(lambda x: x.replace('#WIDTH#', '1400').replace('#HEIGHT#', '800'), sp['as_new_xfreerdp_params']))  # type: ignore

        params = [ # type: ignore
            'open',
            '-a',
            executable,
            '--args',
        ] + [os.path.expandvars(i) for i in xfparms + ['/v:{}'.format(sp['address'])]]  # type: ignore
        #logger.debug('Executing: %s', ' '.join(params))
        subprocess.Popen(params) # type: ignore
else:  # for now, both xfreerdp or udsrdp
    # Fix resolution...
    try:
        xfparms = fix_resolution()
    except Exception as e:
        xfparms = list(map(lambda x: x.replace('#WIDTH#', '1400').replace('#HEIGHT#', '800'), sp['as_new_xfreerdp_params']))  # type: ignore

    params = [os.path.expandvars(i) for i in [executable] + xfparms + ['/v:{}'.format(sp['address'])]]  # type: ignore
    logger.debug('Executing: %s', ' '.join(params)) # type: ignore
    subprocess.Popen(params) # type: ignore
