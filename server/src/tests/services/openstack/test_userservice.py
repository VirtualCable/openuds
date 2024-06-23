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
import typing
import contextlib

from uds import models
from uds.core import types
from unittest import mock

from uds.services.OpenStack.openstack import types as openstack_types

from . import fixtures

#from tests.utils import MustBeOfType
from ...utils.test import UDSTransactionTestCase
from ...utils.helpers import limited_iterator

if typing.TYPE_CHECKING:
    from uds.services.OpenStack.deployment import OpenStackLiveUserService


# We use transactions on some related methods (storage access, etc...)
class TestOpenstackLiveDeployment(UDSTransactionTestCase):
    _old_servers: typing.List['openstack_types.ServerInfo']

    def setUp(self) -> None:
        # Sets all vms to running, later restore original values
        self._old_servers = fixtures.SERVERS_LIST.copy()
        for vm in fixtures.SERVERS_LIST:
            vm.power_state = fixtures.openstack_types.PowerState.RUNNING

    def tearDown(self) -> None:
        fixtures.SERVERS_LIST = self._old_servers

    @contextlib.contextmanager
    def setup_data(self) -> typing.Iterator[
        tuple[
            'OpenStackLiveUserService',
            mock.MagicMock,
        ]
    ]:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_live_service(provider=provider)
            userservice = fixtures.create_live_userservice(service=service)

            yield userservice, api

    def assert_basic_calls(self, userservice: 'OpenStackLiveUserService', api: mock.MagicMock) -> None:
        #return
        service = userservice.service()
        
        api().create_server_from_snapshot.assert_called_with(
            snapshot_id=userservice.publication().get_template_id(),
            name=userservice.get_vmname(),
            availability_zone=service.availability_zone.value,
            flavor_id=service.flavor.value,
            network_id=service.network.value,
            security_groups_ids=service.security_groups.value,
        )        

    def test_userservice_linked_cache_l1(self) -> None:
        """
        Test the user service
        """
        with self.setup_data() as (userservice, api):
            service = userservice.service()
            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)
            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Ensure that in the event of failure, we don't loop forever
            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED, userservice._error_debug_info)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            self.assert_basic_calls(userservice, api)

    def test_userservice_linked_cache_l2(self) -> None:
        """
        Test the user service
        """
        with self.setup_data() as (userservice, api):
            service = userservice.service()
            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L2)
            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()
                

                # If first item in queue is WAIT, we must "simulate" the wake up from os manager
                if userservice._queue[0] == types.services.Operation.WAIT:
                    userservice.process_ready_from_os_manager(None)

            self.assertEqual(state, types.states.TaskState.FINISHED, f'Queue: {userservice._queue} {userservice._error_debug_info}')

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            vmid = userservice._vmid
            self.assert_basic_calls(userservice, api)
            # And stop the machine
            api().stop_server.assert_called_with(vmid)

    def test_userservice_linked_user(self) -> None:
        """
        Test the user service
        """
        with self.setup_data() as (userservice, api):
            service = userservice.service()

            state = userservice.deploy_for_user(models.User())
            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(
                state,
                types.states.TaskState.FINISHED,
                f'Queue: {userservice._queue}, reason: {userservice._reason}, extra_info: {userservice._error_debug_info}',
            )

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            self.assert_basic_calls(userservice, api)

            # Set ready state with the valid machine
            state = userservice.set_ready()
            # Machine is already running, must return FINISH state
            # As long as the machine is not started, START, START_COMPLETED are not added to the queue
            self.assertEqual(state, types.states.TaskState.FINISHED)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=32):
                state = userservice.check_state()

            # Should be finished now
            self.assertEqual(state, types.states.TaskState.FINISHED)

    def test_userservice_cancel(self) -> None:
        """
        Test the user service
        """
        with self.setup_data() as (userservice, api):
            userservice.service().must_stop_before_deletion = False  # To avoid stop before delete on this test, not needed
            state = userservice.deploy_for_user(mock.MagicMock())
            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Invoke cancel
            api.reset_mock()
            state = userservice.cancel()

            self.assertEqual(state, types.states.TaskState.RUNNING)
            # Ensure DESTROY_VALIDATOR is in the queue
            self.assertIn(types.services.Operation.DESTROY_VALIDATOR, userservice._queue)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            # Now, should be finished without any problem, no call to api should have been done
            self.assertEqual(state, types.states.TaskState.FINISHED, f'State: {state} {userservice._error_debug_info}')
            api().get_server.assert_called()
            api().stop_server.assert_called()
            api().delete_server.assert_called()
            
            api().reset_mock()

            # Now again, but process check_queue a couple of times before cancel
            # we we have an _vmid
            userservice._vmid = ''
            state = userservice.deploy_for_user(models.User())
            self.assertNotEqual(userservice._vmid, '')
            self.assertEqual(
                state,
                types.states.TaskState.RUNNING,
                f'Queue: {userservice._queue} {userservice._error_debug_info} {userservice._reason} {userservice._vmid}',
            )
            # Ensure vm is running, so it gets stopped
            fixtures.set_vm_state(userservice._vmid, fixtures.openstack_types.PowerState.RUNNING)
            current_op = userservice._current_op()
            state = userservice.cancel()
            self.assertEqual(state, types.states.TaskState.RUNNING)
            self.assertEqual(userservice._queue[0], current_op)

            self.assertIn(types.services.Operation.STOP, userservice._queue)
            self.assertIn(types.services.Operation.STOP_COMPLETED, userservice._queue)
            self.assertIn(types.services.Operation.DELETE, userservice._queue)
            self.assertIn(types.services.Operation.DELETE_COMPLETED, userservice._queue)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED, f'State: {state} {userservice._error_debug_info}')

            api().stop_server.assert_called()

    def test_userservice_basics(self) -> None:
        with self.setup_data() as (userservice, _api):
            userservice.set_ip('1.2.3.4')
            self.assertEqual(userservice.get_ip(), '1.2.3.4')
