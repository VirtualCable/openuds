# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2021 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import tempfile
import string
import random
import os
import os.path
import sys
import socket
import stat
import sys
import time
import base64
import typing

import certifi

# For signature checking
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import utils, padding

try:
    import psutil
except ImportError:
    psutil = None


from .log import logger

_unlinkFiles: typing.List[typing.Tuple[str, bool]] = []
_tasksToWait: typing.List[typing.Tuple[typing.Any, bool]] = []
_execBeforeExit: typing.List[typing.Callable[[], None]] = []

sys_fs_enc = sys.getfilesystemencoding() or 'mbcs'

# Public key for scripts
PUBLIC_KEY = b'''-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAuNURlGjBpqbglkTTg2lh
dU5qPbg9Q+RofoDDucGfrbY0pjB9ULgWXUetUWDZhFG241tNeKw+aYFTEorK5P+g
ud7h9KfyJ6huhzln9eyDu3k+kjKUIB1PLtA3lZLZnBx7nmrHRody1u5lRaLVplsb
FmcnptwYD+3jtJ2eK9ih935DYAkYS4vJFi2FO+npUQdYBZHPG/KwXLjP4oGOuZp0
pCTLiCXWGjqh2GWsTECby2upGS/ZNZ1r4Ymp4V2A6DZnN0C0xenHIY34FWYahbXF
ZGdr4DFBPdYde5Rb5aVKJQc/pWK0CV7LK6Krx0/PFc7OGg7ItdEuC7GSfPNV/ANt
5BEQNF5w2nUUsyN8ziOrNih+z6fWQujAAUZfpCCeV9ekbwXGhbRtdNkbAryE5vH6
eCE0iZ+cFsk72VScwLRiOhGNelMQ7mIMotNck3a0P15eaGJVE2JV0M/ag/Cnk0Lp
wI1uJQRAVqz9ZAwvF2SxM45vnrBn6TqqxbKnHCeiwstLDYG4fIhBwFxP3iMH9EqV
2+QXqdJW/wLenFjmXfxrjTRr+z9aYMIdtIkSpADIlbaJyTtuQpEdWnrlDS2b1IGd
Okbm65EebVzOxfje+8dRq9Uqwip8f/qmzFsIIsx3wPSvkKawFwb0G5h2HX5oJrk0
nVgtClKcDDlSaBsO875WDR0CAwEAAQ==
-----END PUBLIC KEY-----'''


def saveTempFile(content: str, filename: typing.Optional[str] = None) -> str:
    if filename is None:
        filename = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(16))
        filename = filename + '.uds'

    filename = os.path.join(tempfile.gettempdir(), filename)

    with open(filename, 'w') as f:
        f.write(content)

    logger.info('Returning filename')
    return filename


def readTempFile(filename: str) -> typing.Optional[str]:
    filename = os.path.join(tempfile.gettempdir(), filename)
    try:
        with open(filename, 'r') as f:
            return f.read()
    except Exception:
        return None


def testServer(host: str, port: typing.Union[str, int], timeOut: int = 4) -> bool:
    try:
        sock = socket.create_connection((host, int(port)), timeOut)
        sock.close()
    except Exception:
        return False
    return True


def findApp(appName: str, extraPath: typing.Optional[str] = None) -> typing.Optional[str]:
    searchPath = os.environ['PATH'].split(os.pathsep)
    if extraPath:
        searchPath += list(extraPath)

    for path in searchPath:
        fileName = os.path.join(path, appName)
        if os.path.isfile(fileName) and (os.stat(fileName).st_mode & stat.S_IXUSR) != 0:
            return fileName
    return None


def getHostName() -> str:
    '''
    Returns current host name
    In fact, it's a wrapper for socket.gethostname()
    '''
    hostname = socket.gethostname()
    logger.info('Hostname: %s', hostname)
    return hostname


# Queing operations (to be executed before exit)


def addFileToUnlink(filename: str, early: bool = False) -> None:
    '''
    Adds a file to the wait-and-unlink list
    '''
    logger.debug('Added file %s to unlink on %s stage', filename, 'early' if early else 'later')
    _unlinkFiles.append((filename, early))


def unlinkFiles(early: bool = False) -> None:
    '''
    Removes all wait-and-unlink files
    '''
    logger.debug('Unlinking files on %s stage', 'early' if early else 'later')
    filesToUnlink = list(filter(lambda x: x[1] == early, _unlinkFiles))
    if filesToUnlink:
        logger.debug('Files to unlink: %s', filesToUnlink)
        # Wait 2 seconds before deleting anything on early and 5 on later stages
        time.sleep(1 + 2 * (1 + int(early)))

        for f in filesToUnlink:
            try:
                os.unlink(f[0])
            except Exception as e:
                logger.debug('File %s not deleted: %s', f[0], e)


def addTaskToWait(task: typing.Any, includeSubprocess: bool = False) -> None:
    logger.debug(
        'Added task %s to wait %s',
        task,
        'with subprocesses' if includeSubprocess else '',
    )
    _tasksToWait.append((task, includeSubprocess))


def waitForTasks() -> None:
    logger.debug('Started to wait %s', _tasksToWait)
    for task, waitForSubp in _tasksToWait:
        logger.debug('Waiting for task %s, subprocess wait: %s', task, waitForSubp)
        try:
            if hasattr(task, 'join'):
                task.join()
            elif hasattr(task, 'wait'):
                task.wait()
            # If wait for spanwed process (look for process with task pid) and we can look for them...
            logger.debug(
                'Psutil: %s, waitForSubp: %s, hasattr: %s',
                psutil,
                waitForSubp,
                hasattr(task, 'pid'),
            )
            if psutil and waitForSubp and hasattr(task, 'pid'):
                subProcesses = list(
                    filter(
                        lambda x: x.ppid() == task.pid,  # type: ignore
                        psutil.process_iter(attrs=('ppid',)),
                    )
                )
                logger.debug('Waiting for subprocesses... %s, %s', task.pid, subProcesses)
                for i in subProcesses:
                    logger.debug('Found %s', i)
                    i.wait()
        except Exception as e:
            logger.error('Waiting for tasks to finish error: %s', e)


def addExecBeforeExit(fnc: typing.Callable[[], None]) -> None:
    logger.debug('Added exec before exit: %s', fnc)
    _execBeforeExit.append(fnc)


def execBeforeExit() -> None:
    logger.debug('Esecuting exec before exit: %s', _execBeforeExit)
    for fnc in _execBeforeExit:
        fnc()


def verifySignature(script: bytes, signature: bytes) -> bool:
    '''
    Verifies with a public key from whom the data came that it was indeed
    signed by their private key
    param: public_key_loc Path to public key
    param: signature String signature to be verified
    return: Boolean. True if the signature is valid; False otherwise.
    '''
    public_key = serialization.load_pem_public_key(data=PUBLIC_KEY, backend=default_backend())

    try:
        public_key.verify(  # type: ignore
            base64.b64decode(signature), script, padding.PKCS1v15(), hashes.SHA256()  # type: ignore
        )
    except Exception:  # InvalidSignature
        return False

    # If no exception, the script was fine...
    return True


def getCaCertsFile() -> typing.Optional[str]:
    # First, try certifi...

    # If environment contains CERTIFICATE_BUNDLE_PATH, use it
    if 'CERTIFICATE_BUNDLE_PATH' in os.environ:
        return os.environ['CERTIFICATE_BUNDLE_PATH']

    try:
        if os.path.exists(certifi.where()):
            return certifi.where()
    except Exception:
        pass

    logger.info('Certifi file does not exists: %s', certifi.where())

    # Check if "standard" paths are valid for linux systems
    if 'linux' in sys.platform:
        for path in (
            '/etc/pki/tls/certs/ca-bundle.crt',
            '/etc/ssl/certs/ca-certificates.crt',
            '/etc/ssl/ca-bundle.pem',
        ):
            if os.path.exists(path):
                logger.info('Found certifi path: %s', path)
                return path

    return None


def isMac() -> bool:
    return 'darwin' in sys.platform
