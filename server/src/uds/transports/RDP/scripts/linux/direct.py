import subprocess  # noqa

from uds import tools  # type: ignore

# Inject local passed sp into globals for inner functions
globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def execUdsRdp(udsrdp):
    import subprocess
    import os.path

    params = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


def execNewXFreeRdp(xfreerdp):
    import subprocess  # @Reimport
    import os.path

    params = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


# Try to locate a xfreerdp and udsrdp. udsrdp will be used if found.
xfreerdp = tools.findApp('xfreerdp')
udsrdp = tools.findApp('udsrdp')
fnc, app = None, None

if xfreerdp:
    fnc, app = execNewXFreeRdp, xfreerdp

if udsrdp is not None:
    fnc, app = execUdsRdp, udsrdp

if app is None or fnc is None:
    raise Exception(
        '''<p>You need to have xfreerdp (>= 2.0) installed on your systeam, and have it your PATH in order to connect to this UDS service.</p>
    <p>Please, install the proper package for your system.</p>
'''
    )

fnc(app)
