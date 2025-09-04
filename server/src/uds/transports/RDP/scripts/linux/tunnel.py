import typing
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

# Añadir soporte para Thincast
import os
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



# Si existe Thincast, usarlo. Si no, seguir con udsrdp/xfreerdp como antes
if thincast_executable:
    logger.debug('Thincast executable found: %s', thincast_executable)
    fnc, app = exec_thincast, thincast_executable
else:
    logger.debug('Thincast not found, searching for xfreerdp and udsrdp')
    xfreerdp: typing.Optional[str] = tools.findApp('xfreerdp3') or tools.findApp('xfreerdp') or tools.findApp('xfreerdp2')
    udsrdp = tools.findApp('udsrdp')
    fnc, app = None, None
    if xfreerdp:
        logger.debug('xfreerdp found: %s', xfreerdp)
        fnc, app = exec_new_xfreerdp, xfreerdp
    if udsrdp:
        logger.debug('udsrdp found: %s', udsrdp)
        fnc, app = exec_udsrdp, udsrdp
    if app is None or fnc is None:
        logger.error('No suitable RDP client found (Thincast, xfreerdp, udsrdp)')
        raise Exception(
            '''<p>You need to have Thincast Remote Desktop Client or xfreerdp (>= 2.0) installed on your system, and have it in your PATH to connect to this UDS service.</p>
        <p>Please, install the appropriate package for your system.</p>
        <ul>
            <li>Thincast: <a href="https://thincast.com/en/products/client">Download</a></li>
            <li>xfreerdp: <a href="https://github.com/FreeRDP/FreeRDP">Download</a></li>
        </ul>
'''
        )

logger.debug('Using RDP client: %s with function: %s', app, fnc)

# Open tunnel and connect
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

logger.debug('Checking tunnel connection...')
# Check that tunnel works..
if fs.check() is False:
    raise Exception(
        '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
    )

logger.debug('Launching RDP client %s to connect to tunnel port %s', app, fs.server_address[1])
fnc(app, fs.server_address[1])
