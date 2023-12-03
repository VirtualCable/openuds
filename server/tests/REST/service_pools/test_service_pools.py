# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import typing
import collections.abc

from uds import models
from uds.core import consts
from uds.REST.handlers import AUTH_TOKEN_HEADER
from uds.REST.methods.actor_v3 import MANAGED, UNMANAGED

from ...fixtures import rest as rest_fixtures
from ...utils import rest

logger = logging.getLogger(__name__)


class ServicePoolTest(rest.test.RESTTestCase):
    def setUp(self) -> None:
        # Override number of items to create
        super().setUp()
        self.login()

    def test_invalid_servicepool(self) -> None:
        url = f'servicespools/INVALID/overview'

        response = self.client.rest_get(url)
        self.assertEqual(response.status_code, 404)

    def test_service_pools(self) -> None:
        url = f'servicespools/overview'

        # Now, will work
        response = self.client.rest_get(url)
        self.assertEqual(response.status_code, 200)
        # Get the list of service pools from DB
        db_pools_len = models.ServicePool.objects.all().count()
        re_pools: list[dict[str, typing.Any]] = response.json()

        self.assertIsInstance(re_pools, list)
        self.assertEqual(db_pools_len, len(re_pools))

        for service_pool in re_pools:
            # Get from DB the service pool
            db_pool = models.ServicePool.objects.get(uuid=service_pool['id'])
            self.assertTrue(rest.assertions.assertServicePoolIs(db_pool, service_pool))
