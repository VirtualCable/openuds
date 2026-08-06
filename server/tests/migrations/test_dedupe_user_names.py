# -*- coding: utf-8 -*-

#
# Copyright (c) 2026 Virtual Cable S.L.U.
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
import importlib

from django.apps import apps

from uds import models

from ..fixtures import authenticators as fixtures_authenticators
from ..fixtures import services as fixtures_services
from ..utils.test import UDSTestCase

# Module name is not a valid identifier, so it cannot be imported directly
migration = importlib.import_module('uds.migrations.0048_dedupe_user_names')


class DedupeUserNamesTest(UDSTestCase):
    """
    The data migration runs against historical models; the real models are
    equivalent for the fields it touches, so we can drive it with `django.apps`.
    """

    def test_duplicates_are_merged_into_the_clean_row(self) -> None:
        auth = fixtures_authenticators.create_db_authenticator()
        group = fixtures_authenticators.create_db_groups(auth, 1)[0]

        clean = auth.users.create(name='alice@example.com', real_name='Alice', state='A')
        dirty = auth.users.create(name='﻿alice@example.com', real_name='Alice', state='A')
        dirty.groups.add(group)

        provider = fixtures_services.create_db_provider()
        userservice = fixtures_services.create_db_one_assigned_userservice(
            provider, dirty, [group], 'managed'
        )

        migration._dedupe_user_names(apps, None)  # pyright: ignore[reportPrivateUsage]

        # Only the clean row survives, and it keeps the duplicate's service and group
        self.assertEqual(auth.users.count(), 1)
        survivor = auth.users.get(name='alice@example.com')
        self.assertEqual(survivor.id, clean.id)
        self.assertEqual(models.UserService.objects.get(id=userservice.id).user, survivor)
        self.assertIn(group, survivor.groups.all())

    def test_lone_dirty_row_is_renamed_in_place(self) -> None:
        auth = fixtures_authenticators.create_db_authenticator()
        dirty = auth.users.create(name='bob​-x', real_name='Bob', state='A')

        migration._dedupe_user_names(apps, None)  # pyright: ignore[reportPrivateUsage]

        dirty.refresh_from_db()
        self.assertEqual(dirty.name, 'bob-x')

    def test_all_invisible_name_is_left_alone(self) -> None:
        auth = fixtures_authenticators.create_db_authenticator()
        weird = auth.users.create(name='​‌', real_name='?', state='A')

        migration._dedupe_user_names(apps, None)  # pyright: ignore[reportPrivateUsage]

        weird.refresh_from_db()
        self.assertEqual(weird.name, '​‌')
