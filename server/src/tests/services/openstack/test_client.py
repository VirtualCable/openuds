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
        v = vars.get_vars('openstack')
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

    @contextlib.contextmanager
    def create_test_volume(self) -> typing.Iterator[openstack_types.VolumeInfo]:
        volume = self.oclient.t_create_volume(
            name='uds-test-volume' + helpers.random_string(5),
            size=1,
        )
        try:
            self.wait_for_volume(volume)
            yield volume
        finally:
            self.wait_for_volume(volume)
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

    @contextlib.contextmanager
    def create_test_server(self) -> typing.Iterator[openstack_types.ServerInfo]:
        with self.create_test_volume() as volume:
            with self.create_test_snapshot(volume) as snapshot:
                server = self.oclient.create_server_from_snapshot(
                    snapshot_id=snapshot.id,
                    name='uds-test-server' + helpers.random_string(5),
                    flavor_id=self._flavorid,
                    network_id=self._networkid,
                    security_groups_names=[],
                    availability_zone=self._availability_zone_id,
                )
        try:
            yield server
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
