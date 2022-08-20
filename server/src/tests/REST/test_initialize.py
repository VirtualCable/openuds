# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging

from django.conf import settings

from uds import models
from uds.core import VERSION
from uds.REST.handlers import AUTH_TOKEN_HEADER

from ..utils import rest, constants


logger = logging.getLogger(__name__)


class ActorInitializeV3(rest.test.RESTTestCase):
    """
    Test actor functionality
    """

    def test_initialize_managed(self) -> None:
        """
        Test actor initialize v3
        """
        rest_token, actor_token = self.login_and_register()

        # Get the user service unique_id
        unique_id = self.user_service.getUniqueId()


        # IP Will not be "recorded" by uds on initialization, but on "ready" stage
        # So these ips are in fact not used
        success = lambda: self.client.post(
            '/uds/rest/actor/v3/initialize',
            data={
                'type': 'managed',
                'version': VERSION,
                'token': actor_token,
                'id': [{'mac': unique_id, 'ip': '1.2.3.4'}],
            },
            content_type='application/json',
        )
        fail = lambda: self.client.post(
            '/uds/rest/actor/v3/initialize',
            data={
                'type': 'managed',
                'version': VERSION,
                'token': 'invalid',
                'id': [{'mac': unique_id, 'ip': '1.2.3.4'}],
            }
        )

        response = success()
        self.assertEqual(response.status_code, 200)

        # Ensure result is fine
        data = response.json()
        self.assertIsInstance(data['result'], dict)
        result = data['result']

        # Ensure own token is assigned
        self.assertEqual(result['own_token'], self.user_service.uuid)
        logger.info('Response: %s', response.json())

        # Ensure no alias token is provided
        self.assertIsNone(result['alias_token'])

        # Ensure os is set and it is a dict
        self.assertIsInstance(result['os'], dict)
        os = result['os']

        # Ensure requested action is rename
        self.assertEqual(os['action'], 'rename')
        # And name is userservice name
        self.assertEqual(os['name'], self.user_service.friendly_name)


        #