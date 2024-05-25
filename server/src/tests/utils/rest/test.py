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
import typing

from uds import models
from uds.core import consts, types
from uds.core.util import log

from ...fixtures import authenticators as authenticators_fixtures
from ...fixtures import services as services_fixtures
from .. import constants, generators, rest, test

NUMBER_OF_ITEMS_TO_CREATE = 4


class RESTTestCase(test.UDSTransactionTestCase):
    # Authenticators related
    auth: models.Authenticator
    simple_groups: list[models.Group]
    meta_groups: list[models.Group]
    admins: list[models.User]  # Users that are admin
    staffs: list[models.User]  # Users that are not admin but are staff
    plain_users: list[models.User]  # Users that are not admin or staff

    users = property(lambda self: self.admins + self.staffs + self.plain_users)
    groups = property(lambda self: self.simple_groups + self.meta_groups)

    provider: models.Provider
    user_service_managed: models.UserService
    user_service_unmanaged: models.UserService

    user_services: list[models.UserService]

    auth_token: str = ''

    def setUp(self) -> None:
        # Set up data for REST Test cases
        # First, the authenticator related
        self.auth = authenticators_fixtures.create_db_authenticator()
        self.simple_groups = authenticators_fixtures.create_db_groups(self.auth, NUMBER_OF_ITEMS_TO_CREATE)
        self.meta_groups = authenticators_fixtures.create_db_metagroups(self.auth, NUMBER_OF_ITEMS_TO_CREATE)
        # Create some users, one admin, one staff and one user
        self.admins = authenticators_fixtures.create_db_users(
            self.auth,
            number_of_users=NUMBER_OF_ITEMS_TO_CREATE,
            is_admin=True,
            groups=self.groups,
        )
        self.staffs = authenticators_fixtures.create_db_users(
            self.auth,
            number_of_users=NUMBER_OF_ITEMS_TO_CREATE,
            is_staff=True,
            groups=self.groups,
        )
        self.plain_users = authenticators_fixtures.create_db_users(
            self.auth, number_of_users=NUMBER_OF_ITEMS_TO_CREATE, groups=self.groups
        )

        for user in self.users:
            log.log(user, types.log.LogLevel.DEBUG, f'Debug Log for {user.name}')
            log.log(user, types.log.LogLevel.INFO, f'Info Log for {user.name}')
            log.log(user, types.log.LogLevel.WARNING, f'Warning Log for {user.name}')
            log.log(user, types.log.LogLevel.ERROR, f'Error Log for {user.name}')

        self.provider = services_fixtures.create_db_provider()

        self.user_service_managed = services_fixtures.create_db_one_cache_userservice(
            self.provider,
            self.admins[0],
            self.groups,
            'managed',
        )
        self.user_service_unmanaged = services_fixtures.create_db_one_cache_userservice(
            self.provider,
            self.admins[0],
            self.groups,
            'unmanaged',
        )

        self.user_services = []
        for user in self.users:
            self.user_services.append(
                services_fixtures.create_db_one_cache_userservice(self.provider, user, self.groups, 'managed')
            )
            self.user_services.append(
                services_fixtures.create_db_one_cache_userservice(
                    self.provider, user, self.groups, 'unmanaged'
                )
            )

    def login(self, user: typing.Optional[models.User] = None, as_admin: bool = True) -> None:
        '''
        Login as specified and returns the auth token
        The token is inserted on the header of the client, so it can be used in the rest of the tests
        Also, it is stored on self.auth_token
        '''
        user = user or (self.admins[0] if as_admin else self.staffs[0])
        response = rest.login(
            self,
            self.client,
            auth_id=self.auth.uuid,
            username=user.name,
            password=user.name,
        )
        self.assertEqual(response['result'], 'ok', f'Login failed: {response}')
        # Insert token into headers
        self.client.add_header(consts.auth.AUTH_TOKEN_HEADER, response['token'])
        self.auth_token = response['token']


class RESTActorTestCase(RESTTestCase):
    # Login as admin or staff and register an actor
    # Returns as a tuple the auth token and the actor registration result token:
    #   - The login auth token
    #   - The actor token
    def login_and_register(self, as_admin: bool = True) -> str:
        self.login(as_admin=as_admin)  # Token not used, alreade inserted on login
        response = self.client.post(
            '/uds/rest/actor/v3/register',
            data=self.register_data(constants.STRING_CHARS),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, 'Actor registration failed')
        return response.json()['result']

    def register_data(self, chars: typing.Optional[str] = None) -> dict[str, str]:
        # Data for registration
        return {
            'username': generators.random_string(size=12, chars=chars)
            + '@AUTH'
            + generators.random_string(size=12, chars=chars),
            'hostname': generators.random_string(size=48, chars=chars),
            'ip': generators.random_ip(),
            'mac': generators.random_mac(),
            'pre_command': generators.random_string(size=64, chars=chars),
            'run_once_command': generators.random_string(size=64, chars=chars),
            'post_command': generators.random_string(size=64, chars=chars),
            'log_level': '0',
        }
