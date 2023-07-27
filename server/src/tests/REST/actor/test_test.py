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
import logging

from uds.REST.handlers import AUTH_TOKEN_HEADER
from uds.REST.methods.actor_v3 import MANAGED, UNMANAGED, ALLOWED_FAILS

from ...utils import rest

logger = logging.getLogger(__name__)


class ActorTestTest(rest.test.RESTActorTestCase):
    """
    Test actor functionality
    """

    def do_test(self, type_: str, token: str) -> None:
        """
        Test actorv3 test managed
        """
        # No actor token, will fail
        response = self.client.post(
            '/uds/rest/actor/v3/test',
            data={'type': type_},
            content_type='application/json',
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['error'], 'invalid token')

        # Helpers
        success = lambda: self.client.post(
            '/uds/rest/actor/v3/test',
            data={'type': type_, 'token': token},
            content_type='application/json',
        )
        invalid = lambda: self.client.post(
            '/uds/rest/actor/v3/test',
            data={'type': type_, 'token': 'invalid'},
            content_type='application/json',
        )
        
        # Invalid actor token also fails
        response = invalid()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['error'], 'invalid token')

        # This one works
        response = success()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'ok')

        # And this one too, without authentication token
        # Without header, test will success because its not authenticated
        self.client.add_header(AUTH_TOKEN_HEADER, 'invalid')
        response = success()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'ok')

        # We have ALLOWED_FAILS until we get blocked for a while
        # Next one will give 403
        for a in range(ALLOWED_FAILS):
            response = invalid()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['error'], 'invalid token')

        # And this one will give 403
        response = invalid()
        self.assertEqual(response.status_code, 403)
    
    def test_test_managed(self) -> None:
        rest_token, actor_token = self.login_and_register()
        self.do_test(MANAGED, actor_token)

    def test_test_unmanaged(self) -> None:
        # try for a first few services
        service = self.user_service_managed.deployed_service.service
        rest_token, actor_token = self.login_and_register()
        # Get service token
        self.do_test(UNMANAGED, service.token or '')

