# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core.managers import crypto
from uds.core.environment import Environment

from uds.services.Proxmox.provider import ProxmoxProvider


PROVIDER_SERIALIZE_DATA: typing.Final[str] = (
    'R1VJWgF2Mf5E0Eb/AlXtUzvdsF+YFTi08PsxvNhRm+Hu3Waqa0Gw0WeReoM5XTnmvopa9+Ex99oRhzW7xr6THkQ7vMZvwKlcI77l'
    '+Zz3FKXnbZnXZkqY0GIqvUzHjQra2Xx9koxkvtAXl64aldXSCjO4xMqCzsCsxgn2fPYnD76TgSccUftTLr5UpaKxXrOg5qr836Si'
    'Y83F6Ko20viicmczi3NmMTR+ii+lmSCUrnRJc/IcxTrfmturJu0X0TipMX5C3xqMyIa1LtsPyHO3yTkYW9bGqP/B1DbDOHy27gu6'
    'DlJwQpi2SRSYEO9pOCTosuVqOpP7hDwCFYn5D1jcEDKZcOmOMuN9qDD423eXUUoCRx2YHmSS0mt03nWxZScV7Ny4U9gmv/x2jsK3'
    '4YL88CPDjh/eMGc7V+LhCSqpEOFmvEz6DVAf'
)

PROVIDER_FIELDS_DATA: typing.Final[dict[str, typing.Any]] = {
    'host': 'proxmox_host',
    'port': 8666,
    'username': 'proxmox_username',
    'password': 'proxmox_passwd',
    'concurrent_creation_limit': 31,
    'concurrent_removal_limit': 32,
    'timeout': 9999,
    'start_vmid': 99999,
    'macs_range': '52:54:01:02:03:04-52:54:05:06:07:08',
}


class ProxmoxProviderSerializationTest(UDSTestCase):
    _oldUDSK: bytes

    def setUp(self) -> None:
        # Override UDSK
        self._oldUDSK = crypto.UDSK
        # Set same key as used to encrypt serialized data
        crypto.UDSK = b'f#s35!e38xv%e-+i'  # type: ignore  # UDSK is final, but this is a test
        return super().setUp()

    def tearDown(self) -> None:
        crypto.UDSK = self._oldUDSK  # type: ignore  # UDSK is final, but this is a test
        return super().tearDown()

    def test_provider_serialization(self) -> None:
        provider = ProxmoxProvider(environment=Environment.testing_environment())
        provider.deserialize(PROVIDER_SERIALIZE_DATA)

        # Ensure values are ok
        for field in PROVIDER_FIELDS_DATA:
            self.assertEqual(getattr(provider, field).value, PROVIDER_FIELDS_DATA[field])
