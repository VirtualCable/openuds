import typing
import logging

logger = logging.getLogger(__name__)

# On older client versions, need importing globally to allow inner functions to work
import subprocess  # type: ignore


try:
    from uds import tools  # type: ignore
except ImportError:
    tools: typing.Any = None

if 'sp' not in globals():
    # Inject local passed sp into globals for inner functions if not already there
    globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def exec_udsrdp(udsrdp: str) -> None:
    import subprocess
    import os.path

    params: typing.List[str] = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


def exec_new_xfreerdp(xfreerdp: str) -> None:
    import subprocess  # @Reimport
    import os.path

    params: typing.List[str] = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


import os

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
logger.debug('Searching for Thincast executables in known locations.')
executable = None
kind = ''
for thincast in thincast_list:
    if os.path.isfile(thincast) and os.access(thincast, os.X_OK):
        executable = thincast
        kind = 'thincast'
        logger.debug('Found Thincast executable: %s', thincast)
        break

# If you don't find Thincast, search UDSRDP and XFREERDP
if not executable:
    logger.debug('Thincast not found. Searching for UDSRDP and XFREERDP.')
    udsrdp: typing.Optional[str] = tools.findApp('udsrdp')
    xfreerdp: typing.Optional[str] = tools.findApp('xfreerdp3') or tools.findApp('xfreerdp') or tools.findApp('xfreerdp2')
    logger.debug('UDSRDP found: %s', udsrdp)
    logger.debug('XFREERDP found: %s', xfreerdp)
    if udsrdp:
        executable = udsrdp
        kind = 'udsrdp'
        logger.debug('Selected UDSRDP as executable.')
    elif xfreerdp:
        executable = xfreerdp
        kind = 'xfreerdp'
        logger.debug('Selected XFREERDP as executable.')

if not executable:
    logger.error('No suitable RDP client found. Thincast, UDSRDP, or XFREERDP are required.')
    raise Exception(
        '''<p>You need to have Thincast Remote Desktop Client or xfreerdp (>= 2.0) installed on your system, and have it in your PATH in order to connect to this UDS service.</p>
    <p>Please, install the proper package for your system.</p>
    <ul>
        <li>Thincast: <a href="https://thincast.com/en/products/client">Download</a></li>
        <li>xfreerdp: <a href="https://github.com/FreeRDP/FreeRDP">Download</a></li>
    </ul>
'''
    )
logger.debug('Using RDP client: %s as kind: %s', executable, kind)

# Execute the client found
if kind == 'thincast':
    import subprocess
    import os.path
    params: typing.List[str] = [os.path.expandvars(i) for i in [executable] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))
elif kind == 'udsrdp':
    exec_udsrdp(executable)
elif kind == 'xfreerdp':
    exec_new_xfreerdp(executable)
