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

from uds.core.environment import Environment
from uds.core import consts

from uds.osmanagers.LinuxOsManager import linux_ad_osmanager as osmanager

from tests.utils import rest
from tests.fixtures import services as services_fixtures

from .. import fixtures


class LinuxAdOsManagerActorTest(rest.test.RESTActorTestCase):
    def test_initialize(self) -> None:
        actor_token = self.login_and_register()

        # Get the user service unique_id, the default

        osm_instance = osmanager.LinuxOsADManager(
            environment=Environment.testing_environment(), values=fixtures.LINUX_AD_FIELDS
        )
        userservice = services_fixtures.create_db_one_assigned_userservice(
            self.provider,
            self.plain_users[0],
            self.simple_groups[:3],
            'managed',
            osm_instance,
        )
        unique_id = userservice.get_unique_id()

        response = self.client.post(
            '/uds/rest/actor/v3/initialize',
            data={
                'type': osm_instance.type_type,
                'version': consts.system.VERSION,
                'token': actor_token,
                'id': [{'mac': unique_id, 'ip': '1.2.3.4'}],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('error', response.json())
        result = response.json()['result']

        # Should have a token / own token, but not checked here because it's generic
        self.assertEqual(result['unique_id'], unique_id)
        self.assertIn('os', result)
        os = result['os']
        self.assertEqual(os['action'], 'rename_ad')
        self.assertEqual(os['name'], userservice.friendly_name)
        self.assertIn('custom', os)
        custom = os['custom']
        self.assertEqual(custom['domain'], osm_instance.domain.value)
        self.assertEqual(custom['username'], osm_instance.account.value)
        self.assertEqual(custom['password'], osm_instance.password.value)
        self.assertEqual(custom['ou'], osm_instance.ou.value)
        self.assertEqual(custom['is_persistent'], osm_instance.remove_on_exit.value)
        self.assertEqual(custom['client_software'], osm_instance.client_software.value)
        self.assertEqual(custom['server_software'], osm_instance.server_software.value)
        self.assertEqual(custom['membership_software'], osm_instance.membership_software.value)
        self.assertEqual(custom['ssl'], osm_instance.use_ssl.value)
        self.assertEqual(custom['automatic_id_mapping'], osm_instance.automatic_id_mapping.value)
