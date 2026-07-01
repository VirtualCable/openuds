# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import logging
from unittest import mock

from uds import models
from uds.core import types as core_types

from uds.core.managers.userservice import UserServiceManager


from tests.fixtures import services as services_fixtures

from tests.utils.test import UDSTransactionTestCase

logger = logging.getLogger(__name__)


class TestUserserviceManager(UDSTransactionTestCase):
    manager: UserServiceManager = UserServiceManager.manager()  # For convenience debugging

    def test_forced_mode_assigned_to_l1(self) -> None:
        # Create an user service, we need
        userservice = services_fixtures.create_db_assigned_userservices()[0]

        orig_uuid = userservice.uuid
        orig_src_ip = userservice.src_ip
        orig_src_hostname = userservice.src_hostname

        self.assertEqual(models.UserService.objects.all().count(), 1)
        # And uuser service is assigned to an user
        self.assertIsNotNone(userservice.user)
        # And cache level is None
        self.assertEqual(userservice.cache_level, core_types.services.CacheLevel.NONE)

        self.manager.forced_move_assigned_to_cache_l1(userservice)

        # Now, should have 2 user services, one in cache and one in db
        self.assertEqual(models.UserService.objects.all().count(), 2)
        # Reload userservice, that should be now in cache
        userservice = models.UserService.objects.get(uuid=orig_uuid)
        self.assertEqual(userservice.cache_level, core_types.services.CacheLevel.L1)
        # Should have no user assigned
        self.assertIsNone(userservice.user)
        # Should be usable
        self.assertTrue(userservice.is_usable())
        # Should not be in use
        self.assertFalse(userservice.in_use)
        # Source ip and hostname should be empty
        self.assertEqual(userservice.src_ip, '')
        self.assertEqual(userservice.src_hostname, '')

        # Look for the created one (that is the assigned, deleted)
        assigned = models.UserService.objects.exclude(uuid=orig_uuid).get()
        self.assertEqual(assigned.cache_level, core_types.services.CacheLevel.NONE)
        # Should have the user assigned
        self.assertIsNotNone(assigned.user)
        # Should be removed
        self.assertEqual(assigned.state, core_types.states.State.REMOVED)

        # unique_id should be same as the original one
        self.assertEqual(userservice.unique_id, assigned.unique_id)
        # src_ip and src_hostname should be the original ones
        self.assertEqual(assigned.src_ip, orig_src_ip)
        self.assertEqual(assigned.src_hostname, orig_src_hostname)

    def test_release_from_logout_no_cache_releases(self) -> None:
        # When the pool does not allow putting machines back to cache, a logout must
        # mark the assigned service for removal.
        userservice = services_fixtures.create_db_assigned_userservices()[0]

        with mock.patch.object(models.UserService, 'allow_putting_back_to_cache', return_value=False):
            self.manager.release_from_logout(userservice)

        userservice.refresh_from_db()
        self.assertEqual(userservice.state, core_types.states.State.REMOVABLE)

    def test_release_from_logout_already_in_cache_is_not_released(self) -> None:
        # Regression: a duplicate/racing logout event must NOT release a machine that a
        # previous logout already returned to cache (cache_level != NONE). Doing so would
        # destroy a valid cache element and cause the observed cache churn.
        userservice = services_fixtures.create_db_assigned_userservices()[0]
        # Simulate the machine already moved back to L1 cache by a prior logout event
        userservice.cache_level = core_types.services.CacheLevel.L1
        userservice.user = None
        userservice.state = core_types.states.State.USABLE
        userservice.os_state = core_types.states.State.USABLE
        userservice.save()

        with mock.patch.object(models.UserService, 'allow_putting_back_to_cache', return_value=True):
            self.manager.release_from_logout(userservice)

        userservice.refresh_from_db()
        # Must remain a valid, usable L1 cache element, NOT marked for removal
        self.assertEqual(userservice.cache_level, core_types.services.CacheLevel.L1)
        self.assertEqual(userservice.state, core_types.states.State.USABLE)

    def test_release_from_logout_missing_row_is_noop(self) -> None:
        # Regression: a prior logout may release & clean the row before we lock it. The
        # select_for_update re-read then raises DoesNotExist -> must be a no-op, not a crash.
        userservice = services_fixtures.create_db_assigned_userservices()[0]
        # Row already gone by the time we re-read under lock
        models.UserService.objects.filter(id=userservice.id).delete()

        # Must not raise (DoesNotExist swallowed) and leave nothing behind
        self.manager.release_from_logout(userservice)

        self.assertEqual(models.UserService.objects.all().count(), 0)

    def test_release_from_logout_l1_overflow_releases(self) -> None:
        # Logout on a pool whose L1 cache already overflows -> release, do NOT cache
        userservice = services_fixtures.create_db_assigned_userservices()[0]

        stats = mock.NonCallableMagicMock()
        stats.is_null.return_value = False
        stats.has_l1_cache_overflow.return_value = True
        stats.is_l1_cache_growth_required.return_value = False

        with mock.patch.object(models.UserService, 'allow_putting_back_to_cache', return_value=True):
            with mock.patch.object(
                UserServiceManager, 'get_cache_servicepool_stats', return_value=stats
            ):
                self.manager.release_from_logout(userservice)

        userservice.refresh_from_db()
        self.assertEqual(userservice.state, core_types.states.State.REMOVABLE)
        # No clone: released, not moved to cache
        self.assertEqual(models.UserService.objects.all().count(), 1)

    def test_release_from_logout_l1_growth_moves_to_cache(self) -> None:
        # Logout on a pool still needing L1 growth -> move back to cache, do NOT release
        userservice = services_fixtures.create_db_assigned_userservices()[0]
        orig_uuid = userservice.uuid

        stats = mock.NonCallableMagicMock()
        stats.is_null.return_value = False
        stats.has_l1_cache_overflow.return_value = False
        stats.is_l1_cache_growth_required.return_value = True

        with mock.patch.object(models.UserService, 'allow_putting_back_to_cache', return_value=True):
            with mock.patch.object(
                UserServiceManager, 'get_cache_servicepool_stats', return_value=stats
            ):
                self.manager.release_from_logout(userservice)

        # forced_move clones the record: original -> L1 cache, a REMOVED copy kept for
        # tracking -> 2 rows
        self.assertEqual(models.UserService.objects.all().count(), 2)
        moved = models.UserService.objects.get(uuid=orig_uuid)
        self.assertEqual(moved.cache_level, core_types.services.CacheLevel.L1)
        self.assertIsNone(moved.user)
        self.assertTrue(moved.is_usable())

    def test_get_user_service_with_initial_no_cache(self) -> None:
        userservice = services_fixtures.create_db_assigned_userservices()[0]
        user = userservice.user
        assert user is not None

        # Fix userservice to set it as cache l1
        userservice.cache_level = core_types.services.CacheLevel.L1
        userservice.user = None
        userservice.save()

        service_pool = userservice.service_pool

        service_pool.initial_srvs = 1
        service_pool.cache_l1_srvs = 0
        service_pool.cache_l2_srvs = 0
        service_pool.max_srvs = 3
        service_pool.save()

        assigned_info = self.manager.get_user_service_info(
            user,
            core_types.os.DetectedOsInfo(
                core_types.os.KnownOS.LINUX, core_types.os.KnownBrowser.CHROME, '1.0.0'
            ),
            '1.2.3.4',
            f'P{service_pool.uuid}',
            service_pool.transports.all()[0].uuid,
        )

        self.assertEqual(assigned_info.userservice.uuid, userservice.uuid)
        self.assertEqual(assigned_info.userservice.cache_level, core_types.services.CacheLevel.NONE)
        self.assertEqual(assigned_info.userservice.user, user)
        self.assertEqual(assigned_info.userservice.src_ip, '1.2.3.4')
        self.assertEqual(assigned_info.userservice.src_hostname, '1.2.3.4')
        self.assertEqual(assigned_info.transport.uuid, service_pool.transports.all()[0].uuid)
