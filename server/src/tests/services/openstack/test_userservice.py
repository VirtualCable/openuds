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
from uds import models
from uds.core import types
from unittest import mock

from uds.services.OpenStack.openstack import types as openstack_types
from uds.services.OpenStack.deployment import Operation

from . import fixtures

from ...utils.test import UDSTransactionTestCase
from ...utils.generators import limited_iterator


# We use transactions on some related methods (storage access, etc...)
class TestOpenstackLiveDeployment(UDSTransactionTestCase):
    def setUp(self) -> None:
        pass

    # Openstack only have l1 cache. L2 is not considered useful right now
    def test_userservice_cachel1_and_user(self) -> None:
        """
        Test the user service
        """
        # Deploy for cache and deploy for user are the same, so we will test both at the same time
        for to_test in ['cache', 'user']:
            for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
                with patcher() as prov:
                    api = typing.cast(mock.MagicMock, prov.api())
                    service = fixtures.create_live_service(prov)
                    userservice = fixtures.create_live_userservice(service=service)
                    publication = userservice.publication()
                    publication._template_id = 'snap1'

                    if to_test == 'cache':
                        state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)
                    else:
                        state = userservice.deploy_for_user(models.User())

                    self.assertEqual(state, types.states.TaskState.RUNNING, f'Error on {to_test} deployment')

                    # Create server should have been called
                    api.create_server_from_snapshot.assert_called_with(
                        snapshot_id='snap1',
                        name=userservice._name,
                        availability_zone=service.availability_zone.value,
                        flavor_id=service.flavor.value,
                        network_id=service.network.value,
                        security_groups_ids=service.security_groups.value,
                    )

                    vmid = userservice._vmid

                    # Set power state of machine to running (userservice._vmid)
                    fixtures.get_id(fixtures.SERVERS_LIST, vmid).power_state = (
                        openstack_types.PowerState.RUNNING
                    )

                    # Ensure that in the event of failure, we don't loop forever
                    for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                        state = userservice.check_state()

                    self.assertEqual(state, types.states.TaskState.FINISHED, f'Error on {to_test} deployment')

                    # userservice name is UDS-U-
                    self.assertEqual(
                        userservice._name[6: 6+len(service.get_basename())],
                        service.get_basename(),
                        f'Error on {to_test} deployment',
                    )
                    self.assertEqual(
                        len(userservice._name),
                        len(service.get_basename()) + service.get_lenname() + 6,  # for UDS-U- prefix
                        f'Error on {to_test} deployment',
                    )

                    # Get server should have been called at least once
                    api.get_server.assert_called_with(vmid)

                    # Mac an ip should have been set
                    self.assertNotEqual(userservice._mac, '', f'Error on {to_test} deployment')
                    self.assertNotEqual(userservice._ip, '', f'Error on {to_test} deployment')

                    # And queue must be finished
                    self.assertEqual(userservice._queue, [Operation.FINISH], f'Error on {to_test} deployment')

    def test_userservice_cancel(self) -> None:
        """
        Test the user service
        """
        for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
            with patcher() as prov:
                service = fixtures.create_live_service(prov)
                userservice = fixtures.create_live_userservice(service=service)
                publication = userservice.publication()
                publication._template_id = 'snap1'

                state = userservice.deploy_for_user(models.User())

                self.assertEqual(state, types.states.TaskState.RUNNING)

                server = fixtures.get_id(fixtures.SERVERS_LIST, userservice._vmid)
                server.power_state = openstack_types.PowerState.RUNNING

                current_op = userservice._get_current_op()

                # Invoke cancel
                state = userservice.cancel()

                self.assertEqual(state, types.states.TaskState.RUNNING)

                self.assertEqual(
                    userservice._queue,
                    [current_op] + [Operation.STOP, Operation.REMOVE, Operation.FINISH],
                )

                counter = 0
                for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                    state = userservice.check_state()
                    if counter > 5:
                        server.power_state = openstack_types.PowerState.SHUTDOWN

                self.assertGreater(counter, 5)
                self.assertEqual(state, types.states.TaskState.FINISHED)

    def test_userservice_error(self) -> None:
        """
        This test will not have keep on error active, and will create correctly
        but will error on set_ready, so it will be put on error state
        """
        """
        Test the user service
        """
        for keep_on_error in (True, False):
            for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
                with patcher() as prov:
                    service = fixtures.create_live_service(prov, maintain_on_error=keep_on_error)
                    userservice = fixtures.create_live_userservice(service=service)
                    publication = userservice.publication()
                    publication._template_id = 'snap1'

                    state = userservice.deploy_for_user(models.User())
                    self.assertEqual(state, types.states.TaskState.RUNNING)

                    server = fixtures.get_id(fixtures.SERVERS_LIST, userservice._vmid)
                    server.power_state = openstack_types.PowerState.RUNNING

                    for _counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                        state = userservice.check_state()

                    # Correctly created
                    self.assertEqual(state, types.states.TaskState.FINISHED)

                    # We are going to force an error on set_ready
                    server.status = openstack_types.ServerStatus.ERROR

                    state = userservice.set_ready()

                    if keep_on_error:
                        self.assertEqual(state, types.states.TaskState.FINISHED)
                    else:
                        self.assertEqual(state, types.states.TaskState.ERROR)

    def test_userservice_error_keep_create(self) -> None:
        """
        This test will have keep on error active, and will create incorrectly
        so vm will be deleted and put on error state
        """
        for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
            with patcher() as prov:
                api = typing.cast(mock.MagicMock, prov.api())
                service = fixtures.create_live_service(prov, maintain_on_eror=True)
                userservice = fixtures.create_live_userservice(service=service)
                publication = userservice.publication()
                publication._template_id = 'snap1'

                api.create_server_from_snapshot.side_effect = Exception('Error')
                state = userservice.deploy_for_user(models.User())

                self.assertEqual(state, types.states.TaskState.ERROR)
