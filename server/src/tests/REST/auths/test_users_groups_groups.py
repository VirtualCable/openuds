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
import collections.abc
import functools
import logging

from uds import models

from ...utils import rest
from ...fixtures import rest as rest_fixtures


logger = logging.getLogger(__name__)


class GroupsTest(rest.test.RESTActorTestCase):
    """
    Test users group rest api
    """

    def setUp(self) -> None:
        # Override number of items to create
        rest.test.NUMBER_OF_ITEMS_TO_CREATE = 16
        super().setUp()
        self.login()

    def test_groups(self) -> None:
        url = f'authenticators/{self.auth.uuid}/groups'

        # Now, will work
        response = self.client.rest_get(f'{url}/overview')
        self.assertEqual(response.status_code, 200)
        groups = response.json()
        self.assertEqual(
            len(groups), rest.test.NUMBER_OF_ITEMS_TO_CREATE * 2  # simple + meta
        )
        group: collections.abc.Mapping[str, typing.Any]
        for group in groups:
            # Locate the group in the auth
            dbgrp = self.auth.groups.get(name=group['name'])
            self.assertTrue(
                rest.assertions.assertGroupIs(dbgrp, group, compare_uuid=True)
            )

    def test_groups_tableinfo(self) -> None:
        url = f'authenticators/{self.auth.uuid}/groups/tableinfo'

        # Now, will work
        response = self.client.rest_get(url)
        self.assertEqual(response.status_code, 200)
        tableinfo = response.json()
        self.assertIn('title', tableinfo)
        self.assertIn('subtitle', tableinfo)
        self.assertIn('fields', tableinfo)
        self.assertIn('row-style', tableinfo)

        # Ensure at least name, comments, state and skip_mfa are present on tableinfo['fields']
        # fields: list[collections.abc.Mapping[str, typing.Any]] = tableinfo['fields']
        fields: list[str] = [list(k.keys())[0] for k in tableinfo['fields']]
        for i in ('name', 'comments', 'state', 'skip_mfa'):
            self.assertIn(i, fields)

    def test_group(self) -> None:
        url = f'authenticators/{self.auth.uuid}/groups'
        # Now, will work
        for i in self.groups:
            response = self.client.rest_get(f'{url}/{i.uuid}')
            self.assertEqual(response.status_code, 200)
            group = response.json()
            self.assertTrue(rest.assertions.assertGroupIs(i, group, compare_uuid=True))

        # invalid user
        response = self.client.rest_get(f'{url}/invalid')
        self.assertEqual(response.status_code, 404)

    def test_group_create_edit(self) -> None:
        url = f'authenticators/{self.auth.uuid}/groups'
        # Normal group
        group_dct = rest_fixtures.create_group()
        response = self.client.rest_put(
            url,
            group_dct,
        )

        self.assertEqual(response.status_code, 200)
        group = models.Group.objects.get(name=group_dct['name'])
        self.assertTrue(rest.assertions.assertGroupIs(group, group_dct))

        # Now, will fail because name is already in use
        response = self.client.rest_put(
            url,
            group_dct,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

        # Now a meta group, with some groups inside
        # groups = [self.simple_groups[0].uuid]
        group_dct = rest_fixtures.create_group(
            meta=True, groups=[self.simple_groups[0].uuid, self.simple_groups[1].uuid]
        )

        response = self.client.rest_put(
            url,
            group_dct,
        )
