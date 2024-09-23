import typing

# On older client versions, need importing globally to allow inner functions to work
import subprocess  # type: ignore


try:
    from uds import tools  # type: ignore
except ImportError:
    tools: typing.Any = None

if 'sp' not in globals():
    # Inject local passed sp into globals for inner functions if not already there
    globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


def execUdsRdp(udsrdp: str) -> None:
    import subprocess
    import os.path

    params: typing.List[str] = [os.path.expandvars(i) for i in [udsrdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


def execNewXFreeRdp(xfreerdp: str) -> None:
    import subprocess  # @Reimport
    import os.path

    params: typing.List[str] = [os.path.expandvars(i) for i in [xfreerdp] + sp['as_new_xfreerdp_params'] + ['/v:{}'.format(sp['address'])]]  # type: ignore
    tools.addTaskToWait(subprocess.Popen(params))


# Try to locate a xfreerdp and udsrdp. udsrdp will be used if found.
xfreerdp: typing.Optional[str] = tools.findApp('xfreerdp')
udsrdp: typing.Optional[str] = tools.findApp('udsrdp')
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
