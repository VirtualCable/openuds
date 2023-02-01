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
import functools
import logging

from uds import models
from uds.core import VERSION
from uds.core.managers import cryptoManager

from ...utils import rest
from ...fixtures import rest as rest_fixtures

logger = logging.getLogger(__name__)


class UsersTest(rest.test.RESTActorTestCase):
    """
    Test users group rest api
    """

    def setUp(self) -> None:
        super().setUp()
        self.login()

    def test_users(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users'

        # Now, will work
        response = self.client.rest_get(f'{url}/overview')
        self.assertEqual(response.status_code, 200)
        users = response.json()
        self.assertEqual(
            len(users), rest.test.NUMBER_OF_ITEMS_TO_CREATE * 3
        )  # 3 because will create admins, staff and plain users
        # Ensure values are correct
        user: typing.Mapping[str, typing.Any]
        for user in users:
            # Locate the user in the auth
            self.assertTrue(
                rest_fixtures.assertUserIs(self.auth.users.get(name=user['name']), user)
            )

    def test_users_tableinfo(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users/tableinfo'

        # Now, will work
        response = self.client.rest_get(url)
        self.assertEqual(response.status_code, 200)
        tableinfo = response.json()
        self.assertIn('title', tableinfo)
        self.assertIn('subtitle', tableinfo)
        self.assertIn('fields', tableinfo)
        self.assertIn('row-style', tableinfo)

        # Ensure at least name, role, real_name comments, state and last_access are present on tableinfo['fields']
        fields: typing.List[typing.Mapping[str, typing.Any]] = tableinfo['fields']
        self.assertTrue(
            functools.reduce(
                lambda x, y: x and y,
                map(
                    lambda f: next(iter(f.keys()))
                    in (
                        'name',
                        'role',
                        'real_name',
                        'comments',
                        'state',
                        'last_access',
                    ),
                    fields,
                ),
            )
        )

    def test_user(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users'
        # Now, will work
        for i in self.users:
            response = self.client.rest_get(f'{url}/{i.uuid}')
            self.assertEqual(response.status_code, 200)
            user = response.json()
            self.assertTrue(
                rest_fixtures.assertUserIs(i, user),
                'User {} {} is not correct'.format(
                    i, models.User.objects.filter(uuid=i.uuid).values()[0]
                ),
            )

        # invalid user
        response = self.client.rest_get(f'{url}/invalid')
        self.assertEqual(response.status_code, 404)

    def test_users_log(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users/'
        # Now, will work
        for user in self.users:
            response = self.client.rest_get(url + f'{user.uuid}/log')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()), 4)  # INFO, WARN, ERROR, DEBUG

        # invalid user
        response = self.client.rest_get(url + 'invalid/log')
        self.assertEqual(response.status_code, 404)

    def test_user_create_edit(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users'
        user_dct = rest_fixtures.createUser(
            groups=[self.groups[0].uuid, self.groups[1].uuid]
        )
        # Now, will work
        response = self.client.rest_put(
            url,
            user_dct,
            content_type='application/json',
        )

        # Get user from database and ensure values are correct
        dbusr = self.auth.users.get(name=user_dct['name'])
        self.assertTrue(rest_fixtures.assertUserIs(dbusr, user_dct))

        self.assertEqual(response.status_code, 200)
        # Returns nothing

        # Now, will fail because name is already in use
        response = self.client.rest_put(
            url,
            user_dct,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

        user_dct = rest_fixtures.createUser(  # nosec: test password, also, "fixme" means "create a random password" in this case
            id=dbusr.uuid,
            groups=[self.groups[2].uuid],
            password='fixme',
            mfa_data='mfadata',
        )

        response = self.client.rest_put(
            url,
            user_dct,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        # Get user from database and ensure values are correct
        dbusr = self.auth.users.get(name=user_dct['name'])
        self.assertTrue(
            rest_fixtures.assertUserIs(dbusr, user_dct, compare_password=True)
        )

    def test_user_delete(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users'
        # Now, will work
        response = self.client.rest_delete(url + f'/{self.plain_users[0].uuid}')
        self.assertEqual(response.status_code, 200)
        # Returns nothing

        # Now, will fail because user does not exist
        response = self.client.rest_delete(url + f'/{self.plain_users[0].uuid}')
        self.assertEqual(response.status_code, 404)

    def test_user_userservices_and_servicepools(self) -> None:
        url = f'authenticators/{self.auth.uuid}/users/{self.plain_users[0].uuid}/userServices'
        # Now, will work
        response = self.client.rest_get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

        # Same with service pools
        url = f'authenticators/{self.auth.uuid}/users/{self.plain_users[0].uuid}/servicesPools'
        response = self.client.rest_get(url)
        self.assertEqual(response.status_code, 200)
        groups = self.plain_users[0].groups.all()
        count = len(list(models.ServicePool.getDeployedServicesForGroups(groups)))

        self.assertEqual(len(response.json()), count)
