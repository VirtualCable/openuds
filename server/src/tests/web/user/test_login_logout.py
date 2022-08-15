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


from django.test import TestCase, TransactionTestCase
from django.db import transaction

from ... import fixtures, tools

if typing.TYPE_CHECKING:
    from django.http import HttpResponse

from uds import models

class WebLoginLogoutCase(TransactionTestCase):
    """
    Test login and logout
    """

    def setUp(self):
        self.client = tools.getClient()

    def assertInvalidLogin(self, response: 'HttpResponse') -> None:
        # Returns login page with a message on uds.js
        self.assertContains(response, '<svg', status_code=200)
        # Fetch uds.js
        response = typing.cast('HttpResponse', self.client.get('/uds/utility/uds.js'))
        self.assertContains(response, '"errors": ["Access denied"]', status_code=200)

    def do_login(self, username: str, password: str, authid: str) -> 'HttpResponse':
        return typing.cast(
            'HttpResponse',
            self.client.post(
                '/uds/page/login',
                {
                    'user': username,
                    'password': password,
                    'authenticator': authid,
                },
            ),
        )

    def test_login_logout_success(self):
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
            for group in random.sample(groups, random.randint(1, len(groups))):  # nosec: Simple test, not strong cryptograde needed
                user.groups.add(group)

        # All users, admin and staff must be able to login
        for num, user in enumerate(users + admins + stafs, start=1):
            response = self.do_login(user.name, user.name, auth.uuid)
            self.assertRedirects(response, '/uds/page/services', status_code=302)
            # Now invoke logout
            response = typing.cast('HttpResponse', self.client.get('/uds/page/logout'))
            self.assertRedirects(
                response, 'http://testserver/uds/page/login', status_code=302
            )
            # Ensures a couple of logs are created for every operation
            self.assertEqual(models.Log.objects.count(), num*4)


    def test_login_valid_user_no_group(self):
        user = fixtures.authenticators.createUsers(
            fixtures.authenticators.createAuthenticator(),
        )[0]

        response = self.do_login(user.name, user.name, user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 2)

        user = fixtures.authenticators.createUsers(
            fixtures.authenticators.createAuthenticator(),
            is_staff=True,
        )[0]

        response = self.do_login(user.name, user.name, user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 4)

        user = fixtures.authenticators.createUsers(
            fixtures.authenticators.createAuthenticator(),
            is_admin=True,
        )[0]

        response = self.do_login(user.name, user.name, user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 6)


    def test_login_invalid_user(self):
        user = fixtures.authenticators.createUsers(
            fixtures.authenticators.createAuthenticator(),
        )[0]

        response = self.do_login(user.name, 'wrong password', user.manager.uuid)
        self.assertInvalidLogin(response)

        # Invalid password log & access denied, in auth and user log
        self.assertEqual(models.Log.objects.count(), 4)

        user = fixtures.authenticators.createUsers(
            fixtures.authenticators.createAuthenticator(),
            is_staff=True,
        )[0]

        response = self.do_login(user.name, 'wrong password', user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 8)

        user = fixtures.authenticators.createUsers(
            fixtures.authenticators.createAuthenticator(),
            is_admin=True,
        )[0]

        response = self.do_login(user.name, 'wrong password', user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 12)
