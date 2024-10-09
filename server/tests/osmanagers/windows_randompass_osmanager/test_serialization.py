# pylint: disable=no-member   # ldap module gives errors to pylint
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

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import codecs
import typing

from tests.utils.test import UDSTestCase
from uds.core.environment import Environment
from uds.core.managers.crypto import CryptoManager


from uds.osmanagers.WindowsOsManager import windows_random as osmanager

PASSWD: typing.Final[str] = 'PASSWD'
CRYPTED_PASSWD: typing.Final[str] = CryptoManager().encrypt(PASSWD)

# if data.startswith(b'v'):
#     return super().unmarshal(data)

# values = data.decode('utf8').split('\t')
# if values[0] == 'v1':
#     self._user_account = values[1]
#     self._password = CryptoManager().decrypt(values[2])
#     super().unmarshal(codecs.decode(values[3].encode(), 'hex'))

# self.flag_for_upgrade()  # Force upgrade to new format

SERIALIZED_OSMANAGER_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\tUSER_ACCOUNT\t' + CRYPTED_PASSWD.encode() + b'\t' + codecs.encode(b'v3\tkeep\t30\ttrue', 'hex'),
}


class WindowsOsManagerSerialTest(UDSTestCase):
    def check(self, version: str, instance: 'osmanager.WinRandomPassManager') -> None:
        self.assertEqual(instance.on_logout.value, 'keep')
        self.assertEqual(instance.idle.value, 30)
        self.assertEqual(instance.deadline.value, True)

        self.assertEqual(instance.user_account.value, 'USER_ACCOUNT')
        self.assertEqual(instance.password.value, PASSWD)

    def test_unmarshall_all_versions(self) -> None:
        for v in range(1, len(SERIALIZED_OSMANAGER_DATA) + 1):
            instance = osmanager.WinRandomPassManager(environment=Environment.testing_environment())
            instance.unmarshal(SERIALIZED_OSMANAGER_DATA['v{}'.format(v)])
            self.check(f'v{v}', instance)

    def test_marshaling(self) -> None:
        # Unmarshall last version, remarshall and check that is marshalled using new marshalling format
        LAST_VERSION = 'v{}'.format(len(SERIALIZED_OSMANAGER_DATA))
        instance = osmanager.WinRandomPassManager(environment=Environment.testing_environment())
        instance.unmarshal(SERIALIZED_OSMANAGER_DATA[LAST_VERSION])
        marshaled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'v'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = osmanager.WinRandomPassManager(environment=Environment.testing_environment())
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(LAST_VERSION, instance)
