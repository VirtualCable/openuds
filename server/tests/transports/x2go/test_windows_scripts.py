# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
"""
Author: Janier Rodríguez, jrodriguez at virtualcable dot es
"""
import base64
import os
import stat
import sys
import tempfile
import types
import typing
from unittest import mock

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from uds.transports.X2GO import x2go, x2gotunnel

from tests.utils.test import UDSTestCase

SCRIPTS_DIR: typing.Final[str] = os.path.join(os.path.dirname(x2go.__file__), 'scripts', 'windows')

# Public key the UDS client validates downloaded scripts with (client/src/uds/consts.py)
CLIENT_PUBLIC_KEY: typing.Final[bytes] = b'''-----BEGIN PUBLIC KEY-----
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

SCRIPT_PARAMS: typing.Final[dict[str, typing.Any]] = {
    'ip': '10.0.0.1',
    'port': 22,
    'key': 'fake-private-key',
    'xf': '[UDS/connect]\nhost={ip}\nport={port}\nkey={keyFile}\nexport={export}',
    'tunHost': 'tunnel.example',
    'tunPort': '443',
    'ticket': 'x' * 40,
    'tunWait': 30,
    'tunChk': False,
}


def find_application_current(application_name: str, extra_path: typing.Optional[str] = None) -> typing.Optional[str]:
    # Client find_application since March 2025: extra_path is one folder
    search_path = os.environ['PATH'].split(os.pathsep)
    if extra_path:
        search_path.append(extra_path)
    return _first_executable(search_path, application_name)


def find_application_legacy(application_name: str, extra_path: typing.Optional[str] = None) -> typing.Optional[str]:
    # Client find_application before March 2025: extra_path is a list of folders
    search_path = os.environ['PATH'].split(os.pathsep)
    if extra_path:
        search_path += list(extra_path)
    return _first_executable(search_path, application_name)


def _first_executable(search_path: list[str], application_name: str) -> typing.Optional[str]:
    for path in search_path:
        filename = os.path.join(path, application_name)
        if os.path.isfile(filename) and (os.stat(filename).st_mode & stat.S_IXUSR) != 0:
            return filename
    return None


def fake_client_modules(find_application: typing.Callable[..., typing.Optional[str]]) -> dict[str, types.ModuleType]:
    tools = types.ModuleType('uds.tools')
    tools.findApp = find_application  # type: ignore
    tools.saveTempFile = lambda content, filename=None: '/tmp/fake-' + str(len(content))  # type: ignore

    tunnel = types.ModuleType('uds.tunnel')
    forwarder = mock.Mock()
    forwarder.check.return_value = True
    forwarder.server_address = ('127.0.0.1', 45000)
    tunnel.forward = mock.Mock(return_value=forwarder)  # type: ignore

    return {'uds.tools': tools, 'uds.tunnel': tunnel}


class TestX2GoWindowsScripts(UDSTestCase):
    program_files: str

    def setUp(self) -> None:
        super().setUp()
        self.program_files = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__('shutil').rmtree(self.program_files, ignore_errors=True))
        env_patch = mock.patch.dict(os.environ, {'PROGRAMFILES(X86)': self.program_files, 'PATH': self.program_files})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def install_x2go_client(self) -> str:
        # The script builds a Windows path; a backslash is a valid filename character on Linux
        client_dir = self.program_files + '\\x2goclient'
        os.mkdir(client_dir)
        executable = os.path.join(client_dir, 'x2goclient.exe')
        with open(executable, 'w', encoding='utf8') as f:
            f.write('')
        os.chmod(executable, stat.S_IRWXU)
        return executable

    def run_script(self, script_name: str, find_application: typing.Callable[..., typing.Optional[str]]) -> mock.Mock:
        with open(os.path.join(SCRIPTS_DIR, script_name), 'r', encoding='utf8') as f:
            script = f.read()
        with mock.patch.dict(sys.modules, fake_client_modules(find_application)), mock.patch(
            'subprocess.Popen'
        ) as popen:
            exec(script, {'sp': dict(SCRIPT_PARAMS)})  # pylint: disable=exec-used
        return popen

    def assert_launches_client(self, script_name: str, find_application: typing.Callable[..., typing.Optional[str]]) -> None:
        executable = self.install_x2go_client()
        popen = self.run_script(script_name, find_application)
        popen.assert_called_once()
        argv = popen.call_args[0][0]
        self.assertEqual(argv[0], executable)
        self.assertIn('--session=UDS/connect', argv)

    def test_direct_finds_client_with_current_client(self) -> None:
        self.assert_launches_client('direct.py', find_application_current)

    def test_direct_finds_client_with_legacy_client(self) -> None:
        self.assert_launches_client('direct.py', find_application_legacy)

    def test_tunnel_finds_client_with_current_client(self) -> None:
        self.assert_launches_client('tunnel.py', find_application_current)

    def test_tunnel_finds_client_with_legacy_client(self) -> None:
        self.assert_launches_client('tunnel.py', find_application_legacy)

    def test_scripts_fail_when_client_is_not_installed(self) -> None:
        for script_name in ('direct.py', 'tunnel.py'):
            for find_application in (find_application_current, find_application_legacy):
                with self.subTest(script=script_name, client=find_application.__name__):
                    with self.assertRaisesRegex(Exception, 'X2GO Client'):
                        self.run_script(script_name, find_application)

    def test_scripts_are_signed_for_the_client(self) -> None:
        public_key = serialization.load_pem_public_key(CLIENT_PUBLIC_KEY)
        for transport in (x2go.X2GOTransport, x2gotunnel.TX2GOTransport):
            for script_type in ('direct', 'tunnel'):
                with self.subTest(transport=transport.__name__, script=script_type):
                    script = transport(self.create_environment(), None).get_script('windows', script_type, {})
                    public_key.verify(  # type: ignore
                        base64.b64decode(script.signature_b64),
                        script.script.encode('utf8'),
                        padding.PKCS1v15(),
                        hashes.SHA256(),
                    )
