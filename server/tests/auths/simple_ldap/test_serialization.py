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
import typing

from tests.utils.test import UDSTestCase
from uds.core.environment import Environment


from uds.auths.SimpleLDAP import authenticator

PASSWD: typing.Final[str] = 'PASSWD'

        # vals = data.decode('utf8').split('\t')
        # self._verifySsl = False  # Backward compatibility
        # self._mfaAttr = ''  # Backward compatibility
        # self._certificate = ''  # Backward compatibility

        # logger.debug("Data: %s", vals[1:])
        # (
        #     self._host,
        #     self._port,
        #     ssl,
        #     self._username,
        #     self._password,
        #     self._timeout,
        #     self._ldapBase,
        #     self._userClass,
        #     self._groupClass,
        #     self._userIdAttr,
        #     self._groupIdAttr,
        #     self._memberAttr,
        #     self._userNameAttr,
        # ) = vals[1:14]
        # if vals[0] == 'v2':
        #     (self._mfaAttr, verifySsl, self._certificate) = vals[14:17]
        #     self._verifySsl = gui.as_bool(verifySsl)

SERIALIZED_AUTH_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\thost\t166\tTRUE\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tgclass\tuid_attr\tgid_attr\tmem_attr\tuname_attr',
    'v2': b'v2\thost\t166\tTRUE\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tgclass\tuid_attr\tgid_attr\tmem_attr\tuname_attr\tmfa_attr\tTRUE\tcert',
}


class SimpleLdapSerializationTest(UDSTestCase):
    def check_provider(self, version: str, instance: 'authenticator.SimpleLDAPAuthenticator') -> None:
        self.assertEqual(instance.host.as_str(), 'host')
        self.assertEqual(instance.port.as_int(), 166)
        self.assertEqual(instance.use_ssl.as_bool(), True)
        self.assertEqual(instance.username.as_str(), 'uame')
        self.assertEqual(instance.password.as_str(), PASSWD)
        self.assertEqual(instance.timeout.as_int(), 99)
        self.assertEqual(instance.ldap_base.as_str(), 'dc=dom,dc=m')
        self.assertEqual(instance.user_class.as_str(), 'uclass')
        self.assertEqual(instance.group_class.as_str(), 'gclass')
        self.assertEqual(instance.user_id_attr.as_str(), 'uid_attr')
        self.assertEqual(instance.group_id_attr.as_str(), 'gid_attr')
        self.assertEqual(instance.member_attr.as_str(), 'mem_attr')
        self.assertEqual(instance.username_attr.as_str(), 'uname_attr')
        
        if version >= 'v2':
            self.assertEqual(instance.mfa_attribute.as_str(), 'mfa_attr')
            self.assertEqual(instance.verify_ssl.as_bool(), True)
            self.assertEqual(instance.certificate.as_str(), 'cert')
            
    def test_unmarshall_all_versions(self) -> None:
        for v in range(1, len(SERIALIZED_AUTH_DATA) + 1):
            with Environment.temporary_environment() as env:
                instance = authenticator.SimpleLDAPAuthenticator(environment=env)
                instance.unmarshal(SERIALIZED_AUTH_DATA['v{}'.format(v)])
                self.check_provider(f'v{v}', instance)

    def test_marshaling(self) -> None:
        # Unmarshall last version, remarshall and check that is marshalled using new marshalling format
        LAST_VERSION = 'v{}'.format(len(SERIALIZED_AUTH_DATA))
        with Environment.temporary_environment() as env:
            instance = authenticator.SimpleLDAPAuthenticator(
                environment=env
            )
            instance.unmarshal(SERIALIZED_AUTH_DATA[LAST_VERSION])
            marshaled_data = instance.marshal()

            # Ensure remarshalled flag is set
            self.assertTrue(instance.needs_upgrade())
            instance.mark_for_upgrade(False)  # reset flag

            # Ensure fields has been marshalled using new format
            self.assertFalse(marshaled_data.startswith(b'v'))
        
        with Environment.temporary_environment() as env:           
            # Reunmarshall again and check that remarshalled flag is not set
            instance = authenticator.SimpleLDAPAuthenticator(
                environment=env
            )
            instance.unmarshal(marshaled_data)
            self.assertFalse(instance.needs_upgrade())

            # Check that data is correct
            self.check_provider(LAST_VERSION, instance)
