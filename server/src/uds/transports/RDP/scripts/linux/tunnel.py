import typing
import shutil
import os
import logging

logger = logging.getLogger(__name__)

# On older client versions, need importing globally to allow inner functions to work
import subprocess  # type: ignore

# Avoid type checking annoing errors
try:
    from uds.tunnel import forward  # type: ignore
except ImportError:
    forward: typing.Any = None
    raise

try:
    from uds import tools  # type: ignore
except ImportError:
    tools: typing.Any = None
    raise

if 'sp' not in globals():
    # Inject local passed sp into globals for inner functions if not already there
    globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def exec_udsrdp(udsrdp: str, port: int) -> None:
    import subprocess  # @Reimport
    import os.path
    params: typing.List[str] = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + ['/v:127.0.0.1:{}'.format(port)]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))

def exec_new_xfreerdp(xfreerdp: str, port: int) -> None:
    import subprocess  # @Reimport
    import os.path
    params: typing.List[str] = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + ['/v:127.0.0.1:{}'.format(port)]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))

# Add thinclast support
thincast_list = [
    '/usr/bin/thincast-remote-desktop-client',
    '/usr/bin/thincast',
    '/opt/thincast/thincast-remote-desktop-client',
    '/opt/thincast/thincast',
    '/snap/bin/thincast-remote-desktop-client',
    '/snap/bin/thincast',
    '/snap/bin/thincast-client'
]
thincast_executable = None
for thincast in thincast_list:
    if os.path.isfile(thincast) and os.access(thincast, os.X_OK):
        thincast_executable = thincast
        break

def exec_thincast(thincast: str, port: int) -> None:
    import subprocess
    import os.path
    params: typing.List[str] = [os.path.expandvars(i) for i in [thincast] + sp['as_new_xfreerdp_params'] + ['/v:127.0.0.1:{}'.format(port)]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))

# Open tunnel and connect
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

# Check that tunnel works..
if fs.check() is False:
    raise Exception(
        '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
    )

# If thincast exists, use it. If not, continue with UDSRDP/XFREERDP as before
if thincast_executable:
    logging.debug('Thincast client found, using it')
    logging.debug(f'RDP file params: {sp.get("as_file", "")}')
    # Check if kind is 'thincast' to handle .rdp file execution
    if sp.get('as_file', '') != '':
        logging.debug('Thincast client will use .rdp file')
        theFile = sp.get('as_file', '')
        if '{password}' not in theFile:
            theFile += f'\npassword:s:{sp.get("password", "")}'
        theFile = theFile.format(
            address='127.0.0.1:{}'.format(fs.server_address[1])
        )
        filename = tools.saveTempFile(theFile)
        home_dir = os.path.expanduser("~")
        dest_filename = os.path.join(home_dir, os.path.basename(filename) + '.rdp')
        shutil.move(filename, filename + '.rdp')
        shutil.move(filename + '.rdp', dest_filename)
        subprocess.Popen([thincast_executable, dest_filename])
        tools.addFileToUnlink(dest_filename)
        fnc, app = None, None  # Prevent further execution below
    else:
        logging.debug('Thincast client will use command line parameters')
        fnc, app = exec_thincast, thincast_executable
else:
    xfreerdp: typing.Optional[str] = tools.findApp('xfreerdp3') or tools.findApp('xfreerdp') or tools.findApp('xfreerdp2')
    udsrdp = tools.findApp('udsrdp')
    fnc, app = None, None
    if xfreerdp:
        fnc, app = exec_new_xfreerdp, xfreerdp
    if udsrdp:
        fnc, app = exec_udsrdp, udsrdp
    if app is None or fnc is None:
        raise Exception(
            '''<p>You need to have Thincast Remote Desktop Client o xfreerdp (>= 2.0) installed on your system, y tenerlo en tu PATH para conectar con este servicio UDS.</p>
        <p>Please install the right package for your system.</p>
        <ul>
            <li>Thincast: <a href="https://thincast.com/en/products/client">Download</a></li>
            <li>xfreerdp: <a href="https://github.com/FreeRDP/FreeRDP">Download</a></li>
        </ul>
'''
        )

if fnc is not None and app is not None:
    fnc(app, fs.server_address[1])
