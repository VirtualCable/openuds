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

from django.conf import settings


from uds.osmanagers.LinuxOsManager import linux_ad_osmanager as osmanager

# This class has no old serialization format, so we can use the same data for all versions
DOMAIN: typing.Final[str] = 'domain.dom'
ACCOUNT: typing.Final[str] = 'account'
PASSWORD: typing.Final[str] = 'password'
OU: typing.Final[str] = 'ou=ou,dc=domain,dc=dom'
CLIENT_SOFTWARE: typing.Final[str] = 'sssd'
MEMBERSHIP_SOFTWARE: typing.Final[str] = 'samba'
SERVER_SOFTWARE: typing.Final[str] = 'freeipa'
REMOVE_ON_EXIT: typing.Final[bool] = True
USE_SSL: typing.Final[bool] = True
AUTOMATIC_ID_MAPPING: typing.Final[bool] = True


class LinuxAdOsManagerSerialTest(UDSTestCase):
    def test_marshaling(self) -> None:
        instance = osmanager.LinuxOsADManager(environment=Environment.testing_environment())
        instance.domain.value = DOMAIN
        instance.account.value = ACCOUNT
        instance.password.value = PASSWORD
        instance.ou.value = OU
        instance.client_software.value = CLIENT_SOFTWARE
        instance.membership_software.value = MEMBERSHIP_SOFTWARE
        instance.server_software.value = SERVER_SOFTWARE
        instance.remove_on_exit.value = REMOVE_ON_EXIT
        instance.use_ssl.value = USE_SSL
        instance.automatic_id_mapping.value = AUTOMATIC_ID_MAPPING

        marshaled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertFalse(instance.needs_upgrade())

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'v'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = osmanager.LinuxOsADManager(environment=Environment.testing_environment())
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that all fields are ok
        self.assertEqual(instance.domain.value, DOMAIN)
        self.assertEqual(instance.account.value, ACCOUNT)
        self.assertEqual(instance.password.value, PASSWORD)
        self.assertEqual(instance.ou.value, OU)
        self.assertEqual(instance.client_software.value, CLIENT_SOFTWARE)
        self.assertEqual(instance.membership_software.value, MEMBERSHIP_SOFTWARE)
        self.assertEqual(instance.server_software.value, SERVER_SOFTWARE)
        self.assertEqual(instance.remove_on_exit.value, REMOVE_ON_EXIT)
        self.assertEqual(instance.use_ssl.value, USE_SSL)
        self.assertEqual(instance.automatic_id_mapping.value, AUTOMATIC_ID_MAPPING)
