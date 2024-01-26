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

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core import ui
from uds.core.ui.user_interface import gui, UDSB, UDSK
from uds.core.environment import Environment
from uds.core.managers import crypto

from django.conf import settings


from uds.auths.SimpleLDAP import authenticator

PASSWD: typing.Final[str] = 'PASSWD'

# v1:
#   self.host.value,
#   self.port.value,
#   self.use_ssl.value,
#   self.username.value,
#   self.password.value,
#   self.timeout.value,
#   self.ldap_base.value,
#   self.user_class.value,
#   self.userid_attr.value,
#   self.groupname_attr.value,
# v2:
#   self.username_attr.value = vals[11]
# v3:
#   self.alternate_class.value = vals[12]
# v4:
#   self.mfa_attribute.value = vals[13]
# v5:
#   self.verify_ssl.value = vals[14]
#   self.certificate.value = vals[15]
SERIALIZED_AUTH_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\thost\t166\t1\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tuseridAttr\tgroup_attr\t\tusernattr',
    'v2': b'v2\thost\t166\t1\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tuseridAttr\tgroup_attr\tusernattr',
    'v3': b'v3\thost\t166\t1\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tuseridAttr\tgroup_attr\tusernattr\taltClass',
    'v4': b'v4\thost\t166\t1\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tuseridAttr\tgroup_attr\tusernattr\taltClass\tmfa',
    'v5': b'v5\thost\t166\t1\tuame\t' + PASSWD.encode('utf8') + b'\t99\tdc=dom,dc=m\tuclass\tuseridAttr\tgroup_attr\tusernattr\taltClass\tmfa\tTRUE\tcert',    
}


class RegexSerializationTest(UDSTestCase):
    def check_provider(self, version: str, instance: 'authenticator.SimpleLDAPAuthenticator'):
        self.assertEqual(instance.host.as_str(), 'host')
        self.assertEqual(instance.port.as_int(), 166)
        self.assertEqual(instance.use_ssl.as_bool(), True)
        self.assertEqual(instance.username.as_str(), 'uame')
        self.assertEqual(instance.password.as_str(), PASSWD)
        self.assertEqual(instance.timeout.as_int(), 99)
        self.assertEqual(instance.ldap_base.as_str(), 'dc=dom,dc=m')
        self.assertEqual(instance.user_class.as_str(), 'uclass')
        self.assertEqual(instance.userid_attr.as_str(), 'useridAttr')
        self.assertEqual(instance.groupname_attr.as_str(), 'group_attr')
        if version >= 'v2':
            self.assertEqual(instance.username_attr.as_str(), 'usernattr')

    def test_unmarshall_all_versions(self):
        return
        for v in range(1, len(SERIALIZED_AUTH_DATA) + 1):
            instance = authenticator.SimpleLDAPAuthenticator(environment=Environment.get_temporary_environment())
            instance.unmarshal(SERIALIZED_AUTH_DATA['v{}'.format(v)])
            self.check_provider(f'v{v}', instance)

    def test_marshaling(self):
        return
        # Unmarshall last version, remarshall and check that is marshalled using new marshalling format
        LAST_VERSION = 'v{}'.format(len(SERIALIZED_AUTH_DATA))
        instance = authenticator.SimpleLDAPAuthenticator(
            environment=Environment.get_temporary_environment()
        )
        instance.unmarshal(SERIALIZED_AUTH_DATA[LAST_VERSION])
        marshaled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.flag_for_upgrade(False)  # reset flag

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'v'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = authenticator.SimpleLDAPAuthenticator(
            environment=Environment.get_temporary_environment()
        )
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check_provider(LAST_VERSION, instance)
