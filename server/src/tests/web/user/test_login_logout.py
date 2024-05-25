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
import random
import typing

from django.urls import reverse

from uds import models
from uds.core.util.config import GlobalConfig

from ...utils.web import test
from ...fixtures import authenticators as fixtures_authenticators

if typing.TYPE_CHECKING:
    from django.http import HttpResponse


class WebLoginLogoutTest(test.WEBTestCase):
    """
    Test WEB login and logout
    """

    def assertInvalidLogin(self, response: 'HttpResponse') -> None:
        # Returns login page with a message on uds.js
        self.assertContains(response, '<svg', status_code=200)
        # Fetch uds.js
        response = typing.cast('HttpResponse', self.client.get('/uds/utility/uds.js'))
        self.assertContains(response, '"errors": ["Access denied"]', status_code=200)

    def test_login_logout_success(self) -> None:
        """
        Test login and logout
        """
        auth = fixtures_authenticators.create_db_authenticator()
        # Create some ramdom users
        admins = fixtures_authenticators.create_db_users(
            auth, number_of_users=8, is_admin=True
        )
        stafs = fixtures_authenticators.create_db_users(
            auth, number_of_users=8, is_staff=True
        )
        users = fixtures_authenticators.create_db_users(auth, number_of_users=8)

        # Create some groups
        groups = fixtures_authenticators.create_db_groups(auth, number_of_groups=32)

        # Add users to some groups, ramdomly
        for user in users + admins + stafs:
            for group in random.sample(
                groups,
                random.randint(  # nosec: Simple test, no strong cryptograde is needed
                    1, len(groups)
                ),  # nosec: Simple test, not strong cryptograde needed
            ):
                user.groups.add(group)

        # All users, admin and staff must be able to login
        root = GlobalConfig.SUPER_USER_LOGIN.get(True)
        # Ensure web login for super user is enabled
        rootpass = 'testRootPasword'
        GlobalConfig.SUPER_USER_PASS.set(rootpass)       
        # Ensure web login for super user is enabled
        GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.set(True)
        users_pass = [(user.name, user.name) for user in users + admins + stafs]
        users_pass.append((root, rootpass))
        for num, up in enumerate(users_pass, start=1):
            response = self.do_login(up[0], up[1], auth.uuid)
            # Now invoke logout
            response = typing.cast('HttpResponse', self.client.get('/uds/page/logout'))
            self.assertRedirects(response, reverse('page.login'), status_code=302)
            # Ensures a couple of logs are created for every operation
            # Except for root, that has no user associated on db
            if up[0] is not root and up[1] is not rootpass:  # root user is last one
                # 5 = 4 audit logs + 1 system log (auth.log)
                self.assertEqual(models.Log.objects.count(), num * 5)

        # Ensure web login for super user is disabled and that the root login fails
        GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.set(False)
        response = self.do_login(root, rootpass, auth.uuid, False)
        self.assertInvalidLogin(response)

        # Esure invalid password for root user is not allowed
        GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.set(True)
        response = self.do_login(root, 'invalid', auth.uuid)
        self.assertInvalidLogin(response)

        # And also, taht invalid user is not allowed
        response = self.do_login('invalid', rootpass, auth.uuid)
        self.assertInvalidLogin(response)

    def test_login_valid_user_no_group(self) -> None:
        user = fixtures_authenticators.create_db_users(
            fixtures_authenticators.create_db_authenticator(),
        )[0]

        response = self.do_login(user.name, user.name, user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 4)

        user = fixtures_authenticators.create_db_users(
            fixtures_authenticators.create_db_authenticator(),
            is_staff=True,
        )[0]

        response = self.do_login(user.name, user.name, user.manager.uuid, False)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 8)

        user = fixtures_authenticators.create_db_users(
            fixtures_authenticators.create_db_authenticator(),
            is_admin=True,
        )[0]

        response = self.do_login(user.name, user.name, user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 12)

    def test_login_invalid_user(self) -> None:
        user = fixtures_authenticators.create_db_users(
            fixtures_authenticators.create_db_authenticator(),
        )[0]

        response = self.do_login(user.name, 'wrong password', user.manager.uuid)
        self.assertInvalidLogin(response)

        # Invalid password log & access denied, in auth and user log
        # + 2 system logs (auth.log), one for each failed login
        self.assertEqual(models.Log.objects.count(), 6)

        user = fixtures_authenticators.create_db_users(
            fixtures_authenticators.create_db_authenticator(),
            is_staff=True,
        )[0]

        response = self.do_login(user.name, 'wrong password', user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 12)

        user = fixtures_authenticators.create_db_users(
            fixtures_authenticators.create_db_authenticator(),
            is_admin=True,
        )[0]

        response = self.do_login(user.name, 'wrong password', user.manager.uuid)
        self.assertInvalidLogin(response)

        self.assertEqual(models.Log.objects.count(), 18)
