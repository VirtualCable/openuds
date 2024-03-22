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
from unittest import mock

from uds import models
from uds.core import types

from . import fixtures

from ...utils.test import UDSTransactionTestCase
from ...utils.generators import limited_iterator


# We use transactions on some related methods (storage access, etc...)
class TestProxmovLinkedService(UDSTransactionTestCase):
    def setUp(self) -> None:
        fixtures.set_all_vm_state('stopped')

    def test_userservice_fixed_user(self) -> None:
        """
        Test the user service
        """
        with fixtures.patch_provider_api() as _api:
            userservice = fixtures.create_userservice_fixed()
            service = userservice.service()
            with service._assigned_machines_access() as assigned_machines:
                self.assertEqual(assigned_machines, set())

            # patch userservice db_obj() method to return a mock
            userservice_db = mock.MagicMock()
            userservice.db_obj = mock.MagicMock(return_value=userservice_db)
            # Test Deploy for cache, should set to error due
            # to the fact fixed services cannot have cached items
            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)
            self.assertEqual(state, types.states.TaskState.ERROR)

            # Test Deploy for user
            state = userservice.deploy_for_user(models.User())

            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED)

            # userservice_db Should have halle set_in_use(True)
            userservice_db.set_in_use.assert_called_once_with(True)

            # vmid should have been assigned, so it must be in the assigned machines
            with service._assigned_machines_access() as assigned_machines:
                self.assertEqual({userservice._vmid}, assigned_machines)
            
            # Now, let's release the service
            state = userservice.destroy()
            
            self.assertEqual(state, types.states.TaskState.RUNNING)
            
            while state == types.states.TaskState.RUNNING:
                state = userservice.check_state()
                
            self.assertEqual(state, types.states.TaskState.FINISHED)
            
            # must be empty now
            with service._assigned_machines_access() as assigned_machines:
                self.assertEqual(assigned_machines, set())
            
            # set_ready, machine is "started", set by mock fixture with the start invokation
            state = userservice.set_ready()
            self.assertEqual(state, types.states.TaskState.FINISHED)
            
            # Set vm state to stopped
            fixtures.set_all_vm_state('stopped')
            # Anc clear userservice cache
            userservice.cache.clear()
            
            state = userservice.set_ready()
            self.assertEqual(state, types.states.TaskState.RUNNING)  # Now running
            
            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=32):
                state = userservice.check_state()
            
            # Should be finished now
            self.assertEqual(state, types.states.TaskState.FINISHED)
            
            