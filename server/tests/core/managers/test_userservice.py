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
        
    def test_release_from_logout(self) -> None:
        pass