# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import random
import typing


from django.test import TestCase
from django.test.client import Client
from django.conf import settings

from uds.tests import fixtures, tools


class RESTLoginLogoutCase(TestCase):
    """
    Test login and logout
    """

    def setUp(self):
        self.client = tools.getClient()

    def test_login_logout(self):
        """
        Test login and logout
        """
        auth = fixtures.authenticators.createAuthenticator()
        # Create some ramdom users
        admins = fixtures.authenticators.createUsers(
            auth, number_of_users=8, is_admin=True
        )
        stafs = fixtures.authenticators.createUsers(
            auth, number_of_users=8, is_staff=True
        )
        users = fixtures.authenticators.createUsers(auth, number_of_users=8)

        # Create some groups
        groups = fixtures.authenticators.createGroups(auth, number_of_groups=32)

        # Add users to some groups, ramdomly
        for user in users + admins + stafs:
            for group in random.sample(groups, random.randint(1, len(groups))):
                user.groups.add(group)

        # All users, admin and staff must be able to login
        for user in users + admins + stafs:
            response = self.invokeLogin(auth.uuid, user.name, user.name, 200, 'user')
            self.assertEqual(
                response['result'], 'ok', 'Login user {}'.format(user.name)
            )
            self.assertIsNotNone(response['token'], 'Login user {}'.format(user.name))
            self.assertIsNotNone(response['version'], 'Login user {}'.format(user.name))
            self.assertIsNotNone(
                response['scrambler'], 'Login user {}'.format(user.name)
            )

    def invokeLogin(
        self, auth_id: str, username: str, password: str, expectedResponse, what: str
    ) -> typing.Mapping[str, typing.Any]:
        response = self.client.post(
            '/uds/rest/auth/login',
            {
                'auth_id': auth_id,
                'username': username,
                'password': password,
            },
            content_type='application/json',
        )
        self.assertEqual(
            response.status_code, expectedResponse, 'Login {}'.format(what)
        )
        if response.status_code == 200:
            return response.json()

        return {}
