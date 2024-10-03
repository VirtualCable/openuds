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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging


from uds import models
from uds.core.managers.crypto import CryptoManager
from ...utils import rest


logger = logging.getLogger(__name__)


class ActorUnmanagedTest(rest.test.RESTActorTestCase):
    """
    Test actor functionality
    """

    def invoke_success(
        self,
        token: str,
        *,
        mac: typing.Optional[str] = None,
        ip: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        response = self.client.post(
            '/uds/rest/actor/v3/unmanaged',
            data={
                'id': [{'mac': mac or '42:AC:11:22:33', 'ip': ip or '1.2.3.4'}],
                'token': token,
                'seecret': 'test_secret',
                'port': 1234,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data['result'], dict)
        return data['result']

    def invoke_failure(
        self,
        token: str,
        *,
        mac: typing.Optional[str] = None,
        ip: typing.Optional[str] = None,
        expect_forbidden: bool = False,
    ) -> dict[str, typing.Any]:
        response = self.client.post(
            '/uds/rest/actor/v3/unmanaged',
            data={
                'id': [{'mac': mac or '42:AC:11:22:33', 'ip': ip or '1.2.3.4'}],
                'token': token,
                'seecret': 'test_secret',
                'port': 1234,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200 if not expect_forbidden else 403)
        if expect_forbidden:
            return {}

        data = response.json()
        self.assertIsInstance(data['result'], dict)
        return data['result']

    def test_unmanaged(self) -> None:
        """
        Test actor initialize v3 for unmanaged actor
        """
        userservice = self.userservice_unmanaged
        actor_token: str = (
            userservice.deployed_service.service.token if userservice.deployed_service.service else None
        ) or ''

        if actor_token == '':
            self.fail('Service token not found')

        TEST_MAC: typing.Final[str] = '00:00:00:00:00:00'

        # This will succeed, but only alias token is returned because MAC is not registered by UDS
        result = self.invoke_success(
            actor_token,
            mac=TEST_MAC,
        )

        # 'private_key': key,  # To be removed on 5.0
        # 'key': key,
        # 'server_certificate': certificate,  # To be removed on 5.0
        # 'certificate': certificate,
        # 'password': password,
        # 'ciphers': getattr(settings, 'SECURE_CIPHERS', ''),

        self.assertIn('private_key', result)
        self.assertIn('key', result)
        self.assertIn('server_certificate', result)
        self.assertIn('certificate', result)
        self.assertIn('password', result)
        self.assertIn('ciphers', result)

        # Create a token_alias assiciated with the service
        token_alias = CryptoManager.manager().random_string(40)
        models.ServiceTokenAlias.objects.create(
            alias=token_alias,
            unique_id=TEST_MAC,
            service=userservice.service_pool.service,
        )
        
        result2 = self.invoke_success(
            actor_token,
            mac=TEST_MAC,
        )
        
        # Keys showld be different
        self.assertIn('private_key', result2)
        self.assertIn('key', result2)
        self.assertIn('server_certificate', result2)
        self.assertIn('certificate', result2)
        self.assertIn('password', result2)
        self.assertEqual(result['ciphers'], result2['ciphers'])
