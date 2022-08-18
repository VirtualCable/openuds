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

from uds.REST.handlers import AUTH_TOKEN_HEADER
from uds.REST.methods.actor_v3 import MANAGED, UNMANAGED, ALLOWED_FAILS

from ..utils import rest

logger = logging.getLogger(__name__)


class TestActorV3(rest.test.RESTTestCase):
    """
    Test actor functionality
    """

    def test_test_managed(self) -> None:
        """
        Test actorv3 initialization
        """
        rest_token, actor_token = self.login_and_register()
        # Auth token already set in client headers

        # No actor token, will fail
        response = self.client.post(
            '/uds/rest/actor/v3/test',
            data={'type': MANAGED},
            content_type='application/json',
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'invalid token')
        
        # Invalid actor token also fails
        response = self.client.post(
            '/uds/rest/actor/v3/test',
            data={'type': MANAGED, 'token': 'invalid'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'invalid token')

        # Without header, test will success because its not authenticated
        self.client.add_header(AUTH_TOKEN_HEADER, 'invalid')
        response = self.client.post(
            '/uds/rest/actor/v3/test',
            data={'type': MANAGED, 'token': actor_token},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)

        # We have 2 attempts failed
