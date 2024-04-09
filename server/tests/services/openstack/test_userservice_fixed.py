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

from uds.services.OpenStack.openstack import types as openstack_types


# We use transactions on some related methods (storage access, etc...)
class TestOpenstackFixedUserService(UDSTransactionTestCase):

    def test_userservice_fixed_user(self) -> None:
        """
        Test the user service
        """
        fixtures.set_all_vms_status(openstack_types.ServerStatus.ACTIVE)
        for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
            with patcher() as prov:
                service = fixtures.create_fixed_service(prov)  # Will use provider patched api
                userservice = fixtures.create_fixed_userservice(service)

                # patch userservice db_obj() method to return a mock
                userservice_db = mock.MagicMock()
                userservice.db_obj = mock.MagicMock(return_value=userservice_db)
                # Test Deploy for cache, should raise Exception due
                # to the fact fixed services cannot have cached items
                state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)
                self.assertEqual(state, types.states.TaskState.ERROR)

                state = userservice.deploy_for_user(models.User())

                self.assertEqual(state, types.states.TaskState.RUNNING)

                for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=32):
                    state = userservice.check_state()

                self.assertEqual(state, types.states.TaskState.FINISHED)

                # userservice_db Should have halle set_in_use(True)
                userservice_db.set_in_use.assert_called_once_with(True)

                # vmid should have been assigned, so it must be in the assigned machines
                with service._assigned_access() as assigned_machines:
                    self.assertEqual({userservice._vmid}, assigned_machines)

                # Now, let's release the service
                state = userservice.destroy()

                self.assertEqual(state, types.states.TaskState.RUNNING)

                while state == types.states.TaskState.RUNNING:
                    state = userservice.check_state()

                self.assertEqual(state, types.states.TaskState.FINISHED)

                # must be empty now
                with service._assigned_access() as assigned_machines:
                    self.assertEqual(set(), assigned_machines)

                # set_ready, machine is "stopped" in this test, so must return RUNNING
                # ensure cache is empty, may affect from other tests
                userservice.cache.clear()
                # Also that machine is stopped
                fixtures.get_id(fixtures.SERVERS_LIST, userservice._vmid).power_state = (
                    openstack_types.PowerState.SHUTDOWN
                )
                state = userservice.set_ready()
                self.assertEqual(state, types.states.TaskState.RUNNING)

                for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=32):
                    state = userservice.check_state()

                # Should be finished now
                self.assertEqual(state, types.states.TaskState.FINISHED)
