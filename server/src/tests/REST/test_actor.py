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

from django.test import TestCase
from django.test.client import Client
from django.conf import settings

from uds.REST.handlers import AUTH_TOKEN_HEADER

from .. import fixtures, tools


logger = logging.getLogger(__name__)

class RESTActorCase(TestCase):
    """
    Test actor functionality
    """

    def setUp(self) -> None:
        self.client = tools.getClient()

    def test_register_actor(self) -> None:
        """
        Test actor rest api registration
        """

        def data(chars: typing.Optional[str] = None) -> typing.Dict[str, str]:
            # Data for registration
            return {
                'username': tools.random_string_generator(size=12, chars=chars)
                + '@AUTH'
                + tools.random_string_generator(size=12, chars=chars),
                'hostname': tools.random_string_generator(size=48, chars=chars),
                'ip': tools.random_ip_generator(),
                'mac': tools.random_mac_generator(),
                'pre_command': tools.random_string_generator(size=64, chars=chars),
                'run_once_command': tools.random_string_generator(size=64, chars=chars),
                'post_command': tools.random_string_generator(size=64, chars=chars),
                'log_level': '0',
            }

        # Create three users, one admin, one staff and one user
        auth = fixtures.authenticators.createAuthenticator()
        groups = fixtures.authenticators.createGroups(auth, 1)
        admin = fixtures.authenticators.createUsers(auth, number_of_users=2, is_admin=True, groups=groups)
        staff = fixtures.authenticators.createUsers(auth, number_of_users=2, is_staff=True, groups=groups)
        plain_user = fixtures.authenticators.createUsers(auth, number_of_users=2, groups=groups)

    
        response: typing.Any
        for i, usr in enumerate(admin + staff + plain_user):
            response = tools.rest_login(
                self,
                self.client,
                auth_id=auth.uuid,
                username=usr.name,
                password=usr.name
            )
            self.assertEqual(
                response['result'], 'ok', 'Login user {}'.format(usr.name)
            )
            token = response['token']

            # Try to register. Plain users will fail
            will_fail = usr in plain_user
            response = self.client.post(
                '/uds/rest/actor/v3/register',
                data=data(tools.STRING_CHARS if i%2 == 0 else tools.STRING_CHARS_INVALID),
                content_type='application/json',
                **{AUTH_TOKEN_HEADER: token}
            )
            if will_fail:
                self.assertEqual(response.status_code, 403)
            logger.debug('Response: %s', response)


    def initialize_actor(self):
        """
        Test actor rest api registration
        """
        provider = fixtures.services.createProvider()
        # Create some random services of all kinds
        services = fixtures.services.createServices(
            provider, number_of_services=2, type_of_service=1
        )
        services = services + fixtures.services.createServices(
            provider, number_of_services=2, type_of_service=2
        )

        print(provider)
        print(services)
