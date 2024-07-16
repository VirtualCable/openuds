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

from tests.utils import vars
from tests.utils import helpers

from tests.utils.test import UDSTransactionTestCase

logger = logging.getLogger(__name__)


class TestOpenStackClient(UDSTransactionTestCase):

    _identity_endpoint: str
    _domain: str
    _username: str
    _password: str
    _auth_method: openstack_types.AuthMethod
    _projectid: str

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

    @contextlib.contextmanager
    def create_test_volume(self) -> typing.Iterator[openstack_types.VolumeInfo]:
        volume = self.oclient.t_create_volume(
            name='uds-test-volume' + helpers.random_string(5),
            size=1,
        )
        try:
            yield volume
        finally:
            self.oclient.t_delete_volume(volume.id)

    def test_list_volumes(self) -> None:
        with self.create_test_volume() as volume:
            with self.create_test_volume() as volume2:
                with self.create_test_volume() as volume3:
                    volumes = self.oclient.list_volumes()
                    self.assertGreaterEqual(len(volumes), 3)
                    self.assertIn(volume, volumes)
                    self.assertIn(volume2, volumes)
                    self.assertIn(volume3, volumes)

        # if no project id, should fail
        self.get_client(use_project_id=False)
        with self.assertRaises(Exception):
            self.oclient.list_volumes()
