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

from django.conf import settings


from uds.osmanagers.WindowsOsManager import windows_domain as osmanager

PASSWD: typing.Final[str] = 'PASSWD'
CRYPTED_PASSWD: typing.Final[str] = CryptoManager().encrypt(PASSWD)

# values = data.decode('utf8').split('\t')
# if values[0] in ('v1', 'v2', 'v3', 'v4'):
#     self.domain.value = values[1]
#     self.ou.value = values[2]
#     self.account.value = values[3]
#     self.password.value = CryptoManager().decrypt(values[4])

# if values[0] in ('v2', 'v3', 'v4'):
#     self.grp.value = values[6]
# else:
#     self.grp.value = ''

# if values[0] in ('v3', 'v4'):
#     self.server_hint.value = values[7]
# else:
#     self.server_hint.value = ''

# if values[0] == 'v4':
#     self.use_ssl.value = values[8] == 'y'
#     self.remove_on_exit.value = values[9] == 'y'
# else:
#     self.use_ssl.value = False
#     self.remove_on_exit.value = True
# super().unmarshal(codecs.decode(values[5].encode(), 'hex'))

# self.flag_for_upgrade()  # Force upgrade to new format

SERIALIZED_OSMANAGER_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\tDOMAIN\tOU\tACCOUNT\t' + CRYPTED_PASSWD.encode() + b'\t' + codecs.encode(b'v3\tkeep\t30\ttrue', 'hex'),
    'v2': b'v2\tDOMAIN\tOU\tACCOUNT\t' + CRYPTED_PASSWD.encode() + b'\t' + codecs.encode(b'v3\tkeep\t30\ttrue', 'hex') + b'\tGRP',
    'v3': b'v3\tDOMAIN\tOU\tACCOUNT\t' + CRYPTED_PASSWD.encode() + b'\t' + codecs.encode(b'v3\tkeep\t30\ttrue', 'hex') + b'\tGRP\tSERVER_HINT',
    'v4': b'v4\tDOMAIN\tOU\tACCOUNT\t' + CRYPTED_PASSWD.encode() + b'\t' + codecs.encode(b'v3\tkeep\t30\ttrue', 'hex') + b'\tGRP\tSERVER_HINT\ty\ty',
}


class WindowsOsManagerSerialTest(UDSTestCase):
    def check(self, version: str, instance: 'osmanager.WinDomainOsManager') -> None:
        self.assertEqual(instance.on_logout.value, 'keep')
        self.assertEqual(instance.idle.value, 30)
        self.assertEqual(instance.deadline.value, True)
        
        self.assertEqual(instance.domain.value, 'DOMAIN')
        self.assertEqual(instance.ou.value, 'OU')
        self.assertEqual(instance.account.value, 'ACCOUNT')
        self.assertEqual(instance.password.value, PASSWD)
        
        if version in ('v2', 'v3', 'v4'):
            self.assertEqual(instance.grp.value, 'GRP')
            
        if version in ('v3', 'v4'):
            self.assertEqual(instance.server_hint.value, 'SERVER_HINT')
        
        if version == 'v4':
            self.assertEqual(instance.use_ssl.value, True)
            self.assertEqual(instance.remove_on_exit.value, True)

    def test_unmarshall_all_versions(self) -> None:
        for v in range(1, len(SERIALIZED_OSMANAGER_DATA) + 1):
            instance = osmanager.WinDomainOsManager(environment=Environment.testing_environment())
            instance.unmarshal(SERIALIZED_OSMANAGER_DATA['v{}'.format(v)])
            self.check(f'v{v}', instance)

    def test_marshaling(self) -> None:
        # Unmarshall last version, remarshall and check that is marshalled using new marshalling format
        LAST_VERSION = 'v{}'.format(len(SERIALIZED_OSMANAGER_DATA))
        instance = osmanager.WinDomainOsManager(
            environment=Environment.testing_environment()
        )
        instance.unmarshal(SERIALIZED_OSMANAGER_DATA[LAST_VERSION])
        marshaled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'v'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = osmanager.WinDomainOsManager(
            environment=Environment.testing_environment()
        )
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(LAST_VERSION, instance)
