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

import contextlib
import logging
import typing

from unittest import mock

from uds.core.services.generics import exceptions as gen_exceptions

from tests.utils import vars, helpers
from tests.utils import search_item_by_attr

from tests.utils.test import UDSTransactionTestCase

from uds.services.OpenStack.openstack import (
    types as openstack_types,
    client as openstack_client,
)

from tests.utils import vars, helpers
from tests.utils import search_item_by_attr

from tests.utils.test import UDSTransactionTestCase

logger = logging.getLogger(__name__)


class TestOpenStackClient(UDSTransactionTestCase):
    _identity_endpoint: str
    _domain: str
    _username: str
    _password: str
    _auth_method: openstack_types.AuthMethod
    _projectid: str
    _regionid: str
    _flavorid: str
    _networkid: str
    _subnetid: str
    _security_group_name: str
    _availability_zone_id: str

    oclient: openstack_client.OpenStackClient

    def get_client(self, use_project_id: bool = True) -> None:
        self.oclient = openstack_client.OpenStackClient(
            identity_endpoint=self._identity_endpoint,
            domain=self._domain,
            username=self._username,
            password=self._password,
            auth_method=self._auth_method,
            projectid=self._projectid if use_project_id else None,
            verify_ssl=False,
        )

    def setUp(self) -> None:
        # v = vars.get_vars('openstack-application-credential')
        v = vars.get_vars('openstack-password')
        if not v:
            self.skipTest('No openstack vars')

        self._identity_endpoint = v['identity_endpoint']
        self._domain = v['domain']
        self._username = v['username']
        self._password = v['password']
        self._auth_method = openstack_types.AuthMethod.from_str(v['auth_method'])
        self._projectid = v['project_id']

        self.get_client()

        # Get region id from region_name
        self._regionid = search_item_by_attr(self.oclient.list_regions(), 'name', v['region_name']).id
        self._flavorid = search_item_by_attr(self.oclient.list_flavors(), 'name', v['flavor_name']).id
        self._networkid = search_item_by_attr(self.oclient.list_networks(), 'name', v['network_name']).id
        self._subnetid = search_item_by_attr(self.oclient.list_subnets(), 'name', v['subnet_name']).id
        self._security_group_name = v['security_group_name']
        self._availability_zone_id = search_item_by_attr(
            self.oclient.list_availability_zones(), 'name', v['availability_zone_name']
        ).id

    def wait_for_volume(self, volume: openstack_types.VolumeInfo) -> None:
        helpers.waiter(
            lambda: self.oclient.get_volume_info(volume.id, force=True).status.is_available(),
            timeout=30,
            msg='Timeout waiting for volume to be available',
        )

    def wait_for_snapshot(self, snapshot: openstack_types.SnapshotInfo) -> None:
        helpers.waiter(
            lambda: self.oclient.get_snapshot_info(snapshot.id).status.is_available(),
            timeout=30,
            msg='Timeout waiting for snapshot to be available',
        )

    def wait_for_server(
        self,
        server: openstack_types.ServerInfo,
        power_state: openstack_types.PowerState = openstack_types.PowerState.RUNNING,
    ) -> None:
        helpers.waiter(
            lambda: self.oclient.get_server_info(server.id, force=True).power_state == power_state,
            timeout=30,
            msg='Timeout waiting for server to be running',
        )

    @contextlib.contextmanager
    def create_test_volume(self) -> typing.Iterator[openstack_types.VolumeInfo]:
        volume = self.oclient.t_create_volume(
            name='uds-test-volume' + helpers.random_string(5),
            size=1,
        )
        try:
            self.wait_for_volume(volume)
            # Set volume bootable
            self.oclient.t_set_volume_bootable(volume.id, bootable=True)
            yield volume
        finally:
            self.wait_for_volume(volume)
            logger.info('Volume; %s', self.oclient.get_volume_info(volume.id, force=True))
            self.oclient.t_delete_volume(volume.id)

    @contextlib.contextmanager
    def create_test_snapshot(
        self, volume: openstack_types.VolumeInfo
    ) -> typing.Iterator[openstack_types.SnapshotInfo]:
        snapshot = self.oclient.create_snapshot(
            volume_id=volume.id,
            name='uds-test-snapshot' + helpers.random_string(5),
        )
        try:
            self.wait_for_snapshot(snapshot)
            yield snapshot
        finally:
            self.wait_for_snapshot(snapshot)
            self.oclient.delete_snapshot(snapshot.id)

            # Ensure that the snapshot is deleted
            def snapshot_removal_checker():
                try:
                    self.oclient.get_snapshot_info(snapshot.id)
                    return False
                except Exception:
                    return True

            helpers.waiter(
                snapshot_removal_checker, timeout=30, msg='Timeout waiting for snapshot to be deleted'
            )

    @contextlib.contextmanager
    def create_test_server(
        self,
    ) -> typing.Iterator[
        tuple[openstack_types.ServerInfo, openstack_types.VolumeInfo, openstack_types.SnapshotInfo]
    ]:
        with self.create_test_volume() as volume:
            with self.create_test_snapshot(volume) as snapshot:
                server = self.oclient.create_server_from_snapshot(
                    snapshot_id=snapshot.id,
                    name='uds-test-server' + helpers.random_string(5),
                    flavor_id=self._flavorid,
                    network_id=self._networkid,
                    security_groups_names=[self._security_group_name],
                    availability_zone=self._availability_zone_id,
                )
                try:
                    # Wait for server to be running
                    self.wait_for_server(server)
                    # Reget server info to complete all data
                    server = self.oclient.get_server_info(server.id, force=True)
                    yield server, volume, snapshot
                finally:
                    self.oclient.delete_server(server.id)

    def test_list_projects(self) -> None:
        projects = self.oclient.list_projects()
        self.assertGreaterEqual(len(projects), 1)
        self.assertIn(self._projectid, [p.id for p in projects])

    def test_list_regions(self) -> None:
        regions = self.oclient.list_regions()
        self.assertGreaterEqual(len(regions), 1)
        self.assertIn(self._regionid, [r.id for r in regions])

    def test_list_servers(self) -> None:
        with self.create_test_server() as (server1, _, _):
            with self.create_test_server() as (server2, _, _):
                servers = self.oclient.list_servers(force=True)
                self.assertGreaterEqual(len(servers), 2)
                self.assertIn(
                    (server1.id, server1.name),
                    [(s.id, s.name) for s in servers],
                )
                self.assertIn(
                    (server2.id, server2.name),
                    [(s.id, s.name) for s in servers],
                )

    def test_list_volumes(self) -> None:
        with self.create_test_volume() as volume:
            with self.create_test_volume() as volume2:
                with self.create_test_volume() as volume3:
                    volumes = self.oclient.list_volumes()
                    self.assertGreaterEqual(len(volumes), 3)
                    self.assertIn(
                        (volume.id, volume.name, volume.description),
                        [(v.id, v.name, v.description) for v in volumes],
                    )
                    self.assertIn(
                        (volume2.id, volume2.name, volume2.description),
                        [(v.id, v.name, v.description) for v in volumes],
                    )
                    self.assertIn(
                        (volume3.id, volume3.name, volume3.description),
                        [(v.id, v.name, v.description) for v in volumes],
                    )

        # if no project id, should fail
        self.get_client(use_project_id=False)
        with self.assertRaises(Exception):
            self.oclient.list_volumes()

    def test_list_availability_zones(self) -> None:
        availability_zones = self.oclient.list_availability_zones()
        self.assertGreaterEqual(len(availability_zones), 1)
        self.assertIn(self._availability_zone_id, [az.id for az in availability_zones])

    def test_list_flavors(self) -> None:
        flavors = self.oclient.list_flavors()
        self.assertGreaterEqual(len(flavors), 1)
        self.assertIn(self._flavorid, [f.id for f in flavors])

    def test_list_networks(self) -> None:
        networks = self.oclient.list_networks()
        self.assertGreaterEqual(len(networks), 1)
        self.assertIn(self._networkid, [n.id for n in networks])

    def test_list_subnets(self) -> None:
        subnets = self.oclient.list_subnets()
        self.assertGreaterEqual(len(subnets), 1)
        self.assertIn(self._subnetid, [s.id for s in subnets])

    def test_list_security_groups(self) -> None:
        security_groups = self.oclient.list_security_groups()
        self.assertGreaterEqual(len(security_groups), 1)
        self.assertIn(self._security_group_name, [sg.name for sg in security_groups])

    def test_get_server_info(self) -> None:
        with self.create_test_server() as (server, _, _):
            server_info = self.oclient.get_server_info(server.id)
            self.assertEqual(server.id, server_info.id)
            self.assertEqual(server.name, server_info.name)
            self.assertEqual(server.flavor, server_info.flavor)

        # Trying to get a non existing server should raise an exceptions.NotFoundException
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.get_server_info('non-existing-server')

    def test_get_volume_info(self) -> None:
        with self.create_test_volume() as volume:
            volume_info = self.oclient.get_volume_info(volume.id)
            self.assertEqual(volume.id, volume_info.id)
            self.assertEqual(volume.name, volume_info.name)
            self.assertEqual(volume.description, volume_info.description)

        # Trying to get a non existing volume should raise an exceptions.NotFoundException
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.get_volume_info('non-existing-volume')

    def test_get_snapshot_info(self) -> None:
        with self.create_test_volume() as volume:
            with self.create_test_snapshot(volume) as snapshot:
                snapshot_info = self.oclient.get_snapshot_info(snapshot.id)
                self.assertEqual(snapshot.id, snapshot_info.id)
                self.assertEqual(snapshot.name, snapshot_info.name)

        # Trying to get a non existing snapshot should raise an exceptions.NotFoundException
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.get_snapshot_info('non-existing-snapshot')

    def test_create_snapshot(self) -> None:
        # Note: create snapshot is used on test_create_server_from_snapshot
        # and it's already tested with test_create_server_from_snapshot, so we just test the exceptions here

        # Trying to create a snapshot from a non existing volume should raise an exceptions.NotFoundException
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.create_snapshot(volume_id='non-existing-volume', name='non-existing-snapshot')

    def test_create_server_from_snapshot(self) -> None:
        with self.create_test_server() as (server, _, _):
            self.assertIsNotNone(server.id)

        # Trying to create a server from a non existing snapshot should raise an exceptions.NotFoundException
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.create_server_from_snapshot(
                snapshot_id='non-existing-snapshot',
                name='non-existing-server',
                flavor_id=self._flavorid,
                network_id=self._networkid,
                security_groups_names=[],
                availability_zone=self._availability_zone_id,
            )

    def test_delete_server(self) -> None:
        # delete_server is tested on test_create_server_from_snapshot and test_list_servers at least
        # so we just test the exceptions here
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.delete_server('non-existing-server')

    def test_delete_snapshot(self) -> None:
        # delete_snapshot is tested on test_create_snapshot at least
        # so we just test the exceptions here
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.delete_snapshot('non-existing-snapshot')

    def test_operations_server(self) -> None:
        with self.create_test_server() as (server, _, _):
            # Server is already running, first stop it
            self.oclient.stop_server(server.id)
            self.wait_for_server(server, openstack_types.PowerState.SHUTDOWN)

            self.oclient.start_server(server.id)
            self.wait_for_server(server)

            self.oclient.reset_server(server.id)
            # Here we need to wait for the server to be active again
            helpers.waiter(
                lambda: self.oclient.get_server_info(server.id, force=True).status.is_active(),
                timeout=30,
                msg='Timeout waiting for server to be running',
            )

            # Suspend
            self.oclient.suspend_server(server.id)
            self.wait_for_server(server, openstack_types.PowerState.SUSPENDED)

            # Resume
            self.oclient.resume_server(server.id)
            self.wait_for_server(server)

            # Reboot
            self.oclient.reboot_server(server.id)
            helpers.waiter(
                lambda: self.oclient.get_server_info(server.id, force=True).status.is_active(),
                timeout=30,
                msg='Timeout waiting for server to be running',
            )

    def test_operations_fail_server(self) -> None:
        # Trying the operations on a non existing server should raise an exceptions.NotFoundException
        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.start_server('non-existing-server')

        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.stop_server('non-existing-server')

        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.reset_server('non-existing-server')

        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.suspend_server('non-existing-server')

        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.resume_server('non-existing-server')

        with self.assertRaises(gen_exceptions.NotFoundError):
            self.oclient.reboot_server('non-existing-server')

    def test_test_connection(self) -> None:
        self.assertTrue(self.oclient.test_connection())

    def test_is_available(self) -> None:
        self.assertTrue(self.oclient.is_available())

    # Some useful tests
    def test_duplicated_server_name(self) -> None:
        with self.create_test_server() as (server, _volume, snapshot):
            res = self.oclient.create_server_from_snapshot(
                snapshot_id=snapshot.id,
                name=server.name,
                flavor_id=self._flavorid,
                network_id=self._networkid,
                security_groups_names=[],
                availability_zone=self._availability_zone_id,
            )
            # Has been created, and no problem at all
            self.assertIsNotNone(res)

            # Now, delete it
            # wait for server to be running
            self.wait_for_server(res)
            self.oclient.delete_server(res.id)

    def test_auth_cached(self) -> None:
        # Get a new client, it should be cached
        cached_value = self.oclient.cache.get('auth')
        # Unauthorized
        self.oclient._authenticated = False

        with mock.patch.object(self.oclient.cache, 'get', return_value=cached_value) as mock_cache_get:
            # Session should not be used
            with mock.patch.object(self.oclient, '_session') as mock_session:
                self.assertTrue(self.oclient.is_available())
                mock_cache_get.assert_called_once()
                mock_session.assert_not_called()
