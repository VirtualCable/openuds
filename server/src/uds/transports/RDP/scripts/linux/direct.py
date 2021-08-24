import subprocess  # noqa

from uds import tools  # type: ignore

# Inject local passed sp into globals for inner functions
globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def execUdsRdp(udsrdp):
    import subprocess  # @Reimport
    import os.path

    params = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


def execNewXFreeRdp(xfreerdp):
    import subprocess  # @Reimport
    import os.path

    params = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


# Try to locate a "valid" version of xfreerdp as first option (<1.1 does not allows drive redirections, so it will not be used if found)
xfreerdp = tools.findApp('xfreerdp')
udsrdp = tools.findApp('udsrdp')
fnc, app = None, None

if xfreerdp:
    fnc, app = execNewXFreeRdp, xfreerdp

if udsrdp is not None:
    fnc, app = execUdsRdp, udsrdp

if app is None or fnc is None:
    raise Exception(
        '''<p>You need to have installed xfreerdp (>= 1.1) or rdesktop, and have them in your PATH in order to connect to this UDS service.</p>
    <p>Please, install the proper package for your system.</p>
    <p>Also note that xfreerdp prior to version 1.1 will not be taken into consideration.</p>
'''
    )
else:
    fnc(app)  # @UndefinedVariable
