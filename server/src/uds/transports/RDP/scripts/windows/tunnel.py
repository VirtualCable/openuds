import subprocess
import win32crypt  # type: ignore
import codecs

try:
    import winreg as wreg
except ImportError:  # Python 2.7 fallback
    import _winreg as wreg  # type: ignore
from uds.tunnel import forward  # type: ignore
from uds.log import logger  # type: ignore

from uds import tools  # type: ignore

# Open tunnel
fs = forward(remote=(sp['tunHost'], int(sp['tunPort'])), ticket=sp['ticket'], timeout=sp['tunWait'], check_certificate=sp['tunChk'])  # type: ignore

# Check that tunnel works..
if fs.check() is False:
    raise Exception(
        '<p>Could not connect to tunnel server.</p><p>Please, check your network settings.</p>'
    )

thePass = sp['password'].encode('UTF-16LE')  # type: ignore

try:
    password = codecs.encode(
        win32crypt.CryptProtectData(thePass, None, None, None, None, 0x01), 'hex'
    ).decode()
except Exception:
    # Cannot encrypt for user, trying for machine
    password = codecs.encode(
        win32crypt.CryptProtectData(thePass, None, None, None, None, 0x05), 'hex'
    ).decode()

# The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
theFile = sp['as_file'].format(  # type: ignore
    password=password, address='127.0.0.1:{}'.format(fs.server_address[1])
)

filename = tools.saveTempFile(theFile)
executable = tools.findApp('mstsc.exe')
if executable is None:
    raise Exception(
        'Unable to find mstsc.exe. Check that path points to your SYSTEM32 folder'
    )

try:
    key = wreg.OpenKey(
        wreg.HKEY_CURRENT_USER,
        'Software\\Microsoft\\Terminal Server Client\\LocalDevices',
        0,
        wreg.KEY_SET_VALUE,
    )
    wreg.SetValueEx(key, '127.0.0.1', 0, wreg.REG_DWORD, 255)  # type: ignore
    wreg.CloseKey(key)
except Exception as e:
    # logger.warn('Exception fixing redirection dialog: %s', e)
    pass  # Key does not exists, but it's ok

subprocess.Popen([executable, filename])
tools.addFileToUnlink(filename)
