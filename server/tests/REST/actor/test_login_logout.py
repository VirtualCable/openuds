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
import random
import typing
import collections.abc


from uds.core import consts

from ...fixtures import authenticators as fixtures_authenticators
from ...utils import rest, test


class LoginLogoutTest(test.UDSTestCase):
    """
    Test login and logout
    """

    def test_login_logout(self) -> None:
        """
        Test login and logout
        """
        auth = fixtures_authenticators.create_db_authenticator()
        # Create some ramdom users
        admins = fixtures_authenticators.create_db_users(
            auth, number_of_users=8, is_admin=True
        )
        staffs = fixtures_authenticators.create_db_users(
            auth, number_of_users=8, is_staff=True
        )
        users = fixtures_authenticators.create_db_users(auth, number_of_users=8)

        # Create some groups
        groups = fixtures_authenticators.create_db_groups(auth, number_of_groups=32)

        # Add users to some groups, ramdomly
        for user in users + admins + staffs:
            for group in random.sample(
                groups,
                random.randint(  # nosec: not used with cryptographic pourposes just for testing
                    1, len(groups)
                ),
            ):  # nosec: Simple test, not strong cryptograde needed
                user.groups.add(group)

        # All users, admin and staff must be able to login
        for user in users + admins + staffs:
            # Valid
            response = rest.login(
                self, self.client, auth.uuid, user.name, user.name, 200, 'user'
            )
            self.assertEqual(
                response['result'], 'ok', 'Login user {}'.format(user.name)
            )
            self.assertIsNotNone(response['token'], 'Login user {}'.format(user.name))
            self.assertIsNotNone(response['version'], 'Login user {}'.format(user.name))
            self.assertIsNotNone(
                response['scrambler'], 'Login user {}'.format(user.name)
            )
            self.client.add_header(consts.auth.AUTH_TOKEN_HEADER, response['token'])
            rest.logout(self, self.client)

        # Login with invalid creds just for a single user, because server will "block" us for a while
        response = rest.login(
            self, self.client, auth.uuid, 'invalid', 'invalid', 200, 'user'
        )
        self.assertEqual(response['result'], 'error', 'Login user invalid')
