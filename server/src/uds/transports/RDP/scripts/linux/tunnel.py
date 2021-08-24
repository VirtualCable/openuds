import subprocess  # noqa

from uds.tunnel import forward  # type: ignore

from uds import tools  # type: ignore

# Inject local passed sp into globals for functions
globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def execUdsRdp(udsrdp, port):
    import subprocess  # @Reimport
    import os.path

    params = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + ['/v:127.0.0.1:{}'.format(port)]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


def execNewXFreeRdp(xfreerdp, port):
    import subprocess  # @Reimport
    import os.path

    params = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + ['/v:127.0.0.1:{}'.format(port)]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


# Try to locate a "valid" version of xfreerdp as first option (<1.1 does not allows drive redirections, so it will not be used if found)
xfreerdp = tools.findApp('xfreerdp')
udsrdp = tools.findApp('udsrdp')
fnc, app = None, None

if xfreerdp:
    fnc, app = execNewXFreeRdp, xfreerdp

if udsrdp:
    fnc, app = execUdsRdp, udsrdp

if app is None or fnc is None:
    raise Exception(
        '''<p>You need to have installed xfreerdp (>= 1.1) or rdesktop, and have them in your PATH in order to connect to this UDS service.</p>
    <p>Please, install apropiate package for your system.</p>
    <p>Also note that xfreerdp prior to version 1.1 will not be taken into consideration.</p>
'''
    )
else:
    # Open tunnel
    fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

    # Check that tunnel works..
    if fs.check() is False:
        raise Exception(
            '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
        )

    fnc(app, fs.server_address[1])
