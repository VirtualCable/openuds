# pyright: reportUnknownMemberType=false,reportUnknownArgumentType=false,reportAttributeAccessIssue=false
import typing
import win32crypt  # type: ignore
import codecs

# On older client versions, need importing globally to allow inner functions to work
import subprocess  # type: ignore

import winreg as wreg


# Avoid type checking annoing errors
try:
    from uds import tools  # type: ignore
except ImportError:
    tools: typing.Any = None
    raise


if 'sp' not in globals():
    # Inject local passed sp into globals for inner functions if not already there
    globals()['sp'] = sp  # type: ignore  # pylint: disable=undefined-variable


thePass = sp['password'].encode('UTF-16LE')  # type: ignore

try:
    password = codecs.encode(win32crypt.CryptProtectData(thePass, None, None, None, None, 0x01), 'hex').decode()
except Exception:
    password = codecs.encode(win32crypt.CryptProtectData(thePass, None, None, None, None, 0x05), 'hex').decode()

try:
    key: typing.Any = wreg.OpenKey(  
        wreg.HKEY_CURRENT_USER,  
        'Software\\Microsoft\\Terminal Server Client\\LocalDevices',
        0,
        wreg.KEY_SET_VALUE,  
    )
    wreg.SetValueEx(key, sp['ip'], 0, wreg.REG_DWORD, 255)  # type: ignore
    wreg.CloseKey(key)  # type: ignore
except Exception as e:  # nosec: Not really interested in the exception
    pass  # Key does not exists, ok...

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
theFile = sp['as_file'].format(password=password)  # type: ignore
filename = tools.saveTempFile(theFile)

executable = tools.findApp('mstsc.exe')
if executable is None:
    raise Exception('Unable to find mstsc.exe. Check that path points to your SYSTEM32 folder')

subprocess.Popen([executable, filename])  # nosec

# tools.addFileToUnlink(filename)
