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

from uds import models

from .. import test
from ...fixtures import authenticators as authenticators_fixtures, services as service_fixtures

NUMBER_OF_ITEMS_TO_CREATE = 4


class WEBTestCase(test.UDSTransactionTestCase):
    # Authenticators related
    auth: models.Authenticator
    groups: list[models.Group]
    admins: list[models.User]
    staffs: list[models.User]
    plain_users: list[models.User]

    def setUp(self) -> None:
        # Set up data for REST Test cases
        # First, the authenticator related
        self.auth = authenticators_fixtures.create_db_authenticator()
        self.groups = authenticators_fixtures.create_db_groups(self.auth, NUMBER_OF_ITEMS_TO_CREATE)
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

        self.provider = service_fixtures.create_db_provider()

    def do_login(
        self, username: str, password: str, authid: str, check: bool = False
    ) -> 'test.UDSHttpResponse':
        response = self.client.post(
            '/uds/page/login',
            {
                'user': username,
                'password': password,
                'authenticator': authid,
            },
        )
        if check:
            self.assertRedirects(response, '/uds/page/services', status_code=302, target_status_code=200)
        return response

    def login(self, user: typing.Optional[models.User] = None, as_admin: bool = True) -> models.User:
        '''
        Login as specified user or first admin
        '''
        user = user or (self.admins[0] if as_admin else self.staffs[0])
        self.do_login(user.name, user.name, user.manager.uuid)
        return user
