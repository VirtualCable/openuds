import typing
import logging
import subprocess
import os.path
import shutil
import os

# Asegura que subprocess, shutil, os, os.path y typing estén en el scope global para clientes antiguos (3.6)
globals()['subprocess'] = subprocess
globals()['shutil'] = shutil
globals()['os'] = os
globals()['os.path'] = os.path
globals()['typing'] = typing

try:
    from uds.log import logger  # For UDS Clients 3.6
except ImportError:
    logger = logging.getLogger(__name__)  # For UDS Clients 4.0

# También asegura logger en globales
globals()['logger'] = logger

# Avoid type checking annoing errors
try:
    from uds import tools  # type: ignore
except ImportError:
    tools: typing.Any = None
    raise

# Asegura tools en globales
globals()['tools'] = tools

if 'sp' not in globals():
    # Inject local passed sp into globals for inner functions if not already there
    globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def _prepare_rdp_file(theFile: str, extension: str = '.rdp') -> str:
    """Save RDP file to user's home directory with the given extension and return its path."""
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

def exec_udsrdp(udsrdp: str) -> None:
    params = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + [f'/v:{sp["address"]}']] # type: ignore
    _exec_client_with_params(udsrdp, params)

def exec_new_xfreerdp(xfreerdp: str) -> None:
    if sp.get('as_file', ''): # type: ignore
        dest_filename = _prepare_rdp_file(sp['as_file'], '.uds.rdp') # type: ignore
        params = [xfreerdp, dest_filename, f'/p:{sp.get("password", "")}'] # type: ignore
        _exec_client_with_params(xfreerdp, params, unlink_file=dest_filename)
    else:
        params = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + [f'/v:{sp["address"]}']] # type: ignore
        _exec_client_with_params(xfreerdp, params)

def exec_thincast(thincast: str) -> None:
    if sp.get('as_file', ''): # type: ignore
        dest_filename = _prepare_rdp_file(sp['as_file'], '.rdp') # type: ignore
        params = [thincast, dest_filename, f'/p:{sp.get("password", "")}'] # type: ignore
        _exec_client_with_params(thincast, params, unlink_file=dest_filename)
    else:
        params = [os.path.expandvars(i) for i in [thincast] + sp['as_new_xfreerdp_params'] + [f'/v:{sp["address"]}']] # type: ignore
        _exec_client_with_params(thincast, params)

# Añade las funciones al scope global para clientes antiguos (3.6)
globals()['_prepare_rdp_file'] = _prepare_rdp_file
globals()['_exec_client_with_params'] = _exec_client_with_params
globals()['exec_udsrdp'] = exec_udsrdp
globals()['exec_new_xfreerdp'] = exec_new_xfreerdp
globals()['exec_thincast'] = exec_thincast

# Typical Thincast Routes on Linux
thincast_list = [
    '/usr/bin/thincast-remote-desktop-client',
    '/usr/bin/thincast',
    '/opt/thincast/thincast-remote-desktop-client',
    '/opt/thincast/thincast',
    '/snap/bin/thincast-remote-desktop-client',
    '/snap/bin/thincast',
    '/snap/bin/thincast-client'
]

# Search Thincast first
executable = None
kind = ''
for thincast in thincast_list:
    if os.path.isfile(thincast) and os.access(thincast, os.X_OK):
        executable = thincast
        kind = 'thincast'
        break

# If you don't find Thincast, search UDSRDP and XFREERDP
if not executable:
    udsrdp: typing.Optional[str] = tools.findApp('udsrdp')
    xfreerdp: typing.Optional[str] = tools.findApp('xfreerdp3') or tools.findApp('xfreerdp') or tools.findApp('xfreerdp2')
    if udsrdp:
        executable = udsrdp
        kind = 'udsrdp'
    elif xfreerdp:
        executable = xfreerdp
        kind = 'xfreerdp'

if not executable:
    raise Exception(
        '''<p>You need to have Thincast Remote Desktop Client or xfreerdp (>= 2.0) installed on your system, and have it in your PATH in order to connect to this UDS service.</p>
    <p>Please, install the proper package for your system.</p>
    <ul>
        <li>Thincast: <a href="https://thincast.com/en/products/client">Download</a></li>
        <li>xfreerdp: <a href="https://github.com/FreeRDP/FreeRDP">Download</a></li>
    </ul>
'''
    )
else:
    logger.debug(f'RDP client found: {executable} of kind {kind}')

    # Execute the client found
    if kind == 'thincast':
        if isinstance(executable, str):
            exec_thincast(executable)
        else:
            raise TypeError("Executable must be a string for exec_thincast")
    elif kind == 'udsrdp':
        if isinstance(executable, str):
            exec_udsrdp(executable)
        else:
            raise TypeError("Executable must be a string for exec_udsrdp")
    elif kind == 'xfreerdp':
        if isinstance(executable, str):
            exec_new_xfreerdp(executable)
        else:
            raise TypeError("Executable must be a string for exec_new_xfreerdp")
