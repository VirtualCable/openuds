import typing
import shutil
import os
import subprocess
import os.path

# Asegura que subprocess y shutil estén en el scope global para clientes antiguos (3.6)
globals()['subprocess'] = subprocess
globals()['shutil'] = shutil
globals()['os'] = os
globals()['os.path'] = os.path
globals()['typing'] = typing

try:
    from uds.log import logger  # For UDS Clients 3.6
except ImportError:
    import logger
    logger = logger.getLogger(__name__)  # For UDS Clients 4.0

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

def _prepare_rdp_file(theFile: str, port: int, extension: str = '.rdp') -> str:
    """Save RDP file to user's home directory with the given extension and return its path."""
    # Replace the address in the RDP file with 127.0.0.1:{port}
    # Replace any line starting with "full address:s:" with the desired value
    theFile = theFile.format(
        address='127.0.0.1:{}'.format(port)
    )
    logger.info(f'Preparing RDP file with address 127.0.0.1:{port}')
    logger.debug(f'RDP file content (forced): {theFile}')
    filename = tools.saveTempFile(theFile)
    home_dir = os.path.expanduser("~")
    base_name = os.path.basename(filename)
    dest_filename = os.path.join(home_dir, base_name + extension)
    temp_rdp_filename = filename + extension
    logger.debug(f'Renaming temp file {filename} to {temp_rdp_filename}')
    os.rename(filename, temp_rdp_filename)
    logger.debug(f'Moving temp file {temp_rdp_filename} to {dest_filename}')
    shutil.move(temp_rdp_filename, dest_filename)
    logger.debug(f'RDP file content (forced): {theFile}')
    return dest_filename

def _exec_client_with_params(executable: str, params: typing.List[str], unlink_file: typing.Optional[str] = None) -> None:
    logger.info(f'Executing {executable} with params: {params}')
    tools.addTaskToWait(subprocess.Popen(params))
    if unlink_file:
        tools.addFileToUnlink(unlink_file)

def exec_udsrdp(udsrdp: str, port: int) -> None:
    logger.debug('UDSRDP client will use command line parameters')
    params: typing.List[str] = [os.path.expandvars(i) for i in [app] + sp['as_new_xfreerdp_params'] + [f'/v:127.0.0.1:{port}']]  # type: ignore
    _exec_client_with_params(udsrdp, params)

def exec_new_xfreerdp(xfreerdp: str, port: int) -> None:
    if sp.get('as_file', ''): # type: ignore
        logger.debug('XFREERDP client will use RDP file')
        dest_filename = _prepare_rdp_file(sp['as_file'], port, '.rdp') # type: ignore
        params = [xfreerdp, dest_filename, f'/p:{sp.get("password", "")}'] # type: ignore
        _exec_client_with_params(xfreerdp, params, unlink_file=dest_filename)
    else:
        logger.debug('XFREERDP client will use command line parameters (xfreerdp)')
        params: typing.List[str] = [os.path.expandvars(i) for i in [app] + sp['as_new_xfreerdp_params'] + [f'/v:127.0.0.1:{port}']]  # type: ignore
        _exec_client_with_params(xfreerdp, params)

def exec_thincast(thincast: str, port: int) -> None:
    if sp.get('as_file', ''): # type: ignore
        logger.debug('Thincast client will use RDP file')
        dest_filename = _prepare_rdp_file(sp['as_file'], port, '.rdp') # type: ignore
        params = [thincast, dest_filename, f'/p:{sp.get("password", "")}'] # type: ignore
        _exec_client_with_params(thincast, params, unlink_file=dest_filename)
    else:
        logger.debug('Thincast client will use command line parameters (xfreerdp)')
        params: typing.List[str] = [os.path.expandvars(i) for i in [app] + sp['as_new_xfreerdp_params'] + [f'/v:127.0.0.1:{port}']]  # type: ignore
        _exec_client_with_params(thincast, params)

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

# Open tunnel and connect
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

# Check that tunnel works..
if fs.check() is False:
    raise Exception(
        '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
    )

# If thincast exists, use it. If not, continue with UDSRDP/XFREERDP as before
if thincast_executable:
    logger.debug('Thincast client found, using it')
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

# Asegura que app y fnc sean globales para clientes antiguos (3.6)
globals()['app'] = app
globals()['fnc'] = fnc

# Añade las funciones al scope global para clientes antiguos (3.6)
globals()['_prepare_rdp_file'] = _prepare_rdp_file
globals()['_exec_client_with_params'] = _exec_client_with_params
globals()['exec_udsrdp'] = exec_udsrdp
globals()['exec_new_xfreerdp'] = exec_new_xfreerdp
globals()['exec_thincast'] = exec_thincast

if fnc is not None and app is not None:
    fnc(app, fs.server_address[1])
