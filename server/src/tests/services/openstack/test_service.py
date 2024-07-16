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
# from uds.core import types, environment
import typing
from unittest import mock

from . import fixtures

from ...utils.test import UDSTransactionTestCase

# from uds.services.OpenStack.service import OpenStackLiveService
from uds.services.OpenStack.openstack import types as openstack_types

# We have only one service type for both providers


class TestOpenstackService(UDSTransactionTestCase):
    def test_service(self) -> None:
        """
        Test the service for all kind of providers
        """
        for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
            with patcher() as prov:
                api = typing.cast(mock.MagicMock, prov.api())
                service = fixtures.create_live_service(prov)  # Will use provider patched api
                self.assertEqual(service.api, api)
                self.assertEqual(service.sanitized_name('a b c'), 'a_b_c')

                template = service.make_template('template', 'desc')
                self.assertIsInstance(template, openstack_types.SnapshotInfo)
                api.create_volume_snapshot.assert_called_once_with(service.volume.value, 'template', 'desc')

                template = service.get_template(fixtures.VOLUME_SNAPSHOTS_LIST[0].id)
                self.assertIsInstance(template, openstack_types.SnapshotInfo)
                api.get_volume_snapshot.assert_called_once_with(fixtures.VOLUME_SNAPSHOTS_LIST[0].id)

                data: typing.Any = service.deploy_from_template('name', fixtures.VOLUME_SNAPSHOTS_LIST[0].id)
                self.assertIsInstance(data, openstack_types.ServerInfo)
                api.create_server_from_snapshot.assert_called_once_with(
                    snapshot_id=fixtures.VOLUME_SNAPSHOTS_LIST[0].id,
                    name='name',
                    availability_zone=service.availability_zone.value,
                    flavor_id=service.flavor.value,
                    network_id=service.network.value,
                    security_groups_ids=service.security_groups.value,
                )
                data = service.api.get_server_info(fixtures.SERVERS_LIST[0].id).status
                self.assertIsInstance(data, openstack_types.ServerStatus)
                api.get_server.assert_called_once_with(fixtures.SERVERS_LIST[0].id)
                # Reset mocks, get server should be called again
                api.reset_mock()

                data = service.api.get_server_info(fixtures.SERVERS_LIST[0].id).power_state
                self.assertIsInstance(data, openstack_types.PowerState)
                api.get_server.assert_called_once_with(fixtures.SERVERS_LIST[0].id)

                server = fixtures.SERVERS_LIST[0]
                service.api.start_server(server.id)
                
                server.power_state = openstack_types.PowerState.SHUTDOWN
                api.start_server.assert_called_once_with(server.id)

                server.power_state = openstack_types.PowerState.RUNNING
                service.api.stop_server(server.id)
                api.stop_server.assert_called_once_with(server.id)

                server.power_state = openstack_types.PowerState.RUNNING
                service.api.suspend_server(server.id)
                api.suspend_server.assert_called_once_with(server.id)

                server.power_state = openstack_types.PowerState.SUSPENDED
                service.api.resume_server(server.id)
                api.resume_server.assert_called_once_with(server.id)

                service.api.reset_server(server.id)
                api.reset_server.assert_called_once_with(server.id)

                service.api.delete_server(server.id)
                api.delete_server.assert_called_once_with(server.id)

                self.assertTrue(service.is_avaliable())
                api.is_available.assert_called_once_with()

                self.assertEqual(service.get_basename(), service.basename.value)
                self.assertEqual(service.get_lenname(), service.lenname.value)
                self.assertEqual(service.allows_errored_userservice_cleanup(), not service.maintain_on_error.value)
                self.assertEqual(service.should_maintain_on_error(), service.maintain_on_error.value)
