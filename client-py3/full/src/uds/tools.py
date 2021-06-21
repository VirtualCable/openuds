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
import socket
import stat
import sys
import time
import base64
import typing

from .log import logger

_unlinkFiles: typing.List[str] = []
_tasksToWait: typing.List[typing.Any] = []
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
        filename = ''.join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(16)
        )
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


def findApp(
    appName: str, extraPath: typing.Optional[str] = None
) -> typing.Optional[str]:
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


def addFileToUnlink(filename: str) -> None:
    '''
    Adds a file to the wait-and-unlink list
    '''
    _unlinkFiles.append(filename)


def unlinkFiles() -> None:
    '''
    Removes all wait-and-unlink files
    '''
    if _unlinkFiles:
        time.sleep(5)  # Wait 5 seconds before deleting anything

        for f in _unlinkFiles:
            try:
                os.unlink(f)
            except Exception:
                pass


def addTaskToWait(taks: typing.Any) -> None:
    _tasksToWait.append(taks)


def waitForTasks() -> None:
    for t in _tasksToWait:
        try:
            if hasattr(t, 'join'):
                t.join()
            elif hasattr(t, 'wait'):
                t.wait()
        except Exception:
            pass


def addExecBeforeExit(fnc: typing.Callable[[], None]) -> None:
    _execBeforeExit.append(fnc)


def execBeforeExit() -> None:
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
    # For signature checking
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import utils, padding

    public_key = serialization.load_pem_public_key(
        data=PUBLIC_KEY, backend=default_backend()
    )

    try:
        public_key.verify(
            base64.b64decode(signature), script, padding.PKCS1v15(), hashes.SHA256()
        )
    except Exception:  # InvalidSignature
        return False

    # If no exception, the script was fine...
    return True
