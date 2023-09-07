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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import random
import typing
from unittest import mock

from uds.core import types, consts
from uds.core.util import log
from uds.core.util.model import getSqlStamp

from ...fixtures import servers as servers_fixtures
from ...utils import random_ip_v4, random_ip_v6, random_mac, rest

if typing.TYPE_CHECKING:
    from uds import models

    from ...utils.test import UDSHttpResponse

logger = logging.getLogger(__name__)


class ServerEventsPingTest(rest.test.RESTTestCase):
    """
    Test server functionality
    """

    server: 'models.Server'

    def setUp(self) -> None:
        super().setUp()
        self.server = servers_fixtures.createServer()

    def test_event_ping_with_stats(self) -> None:
        # Ping event
        # Can include "stats"
        # Stats is like types.servers.ServerStatsType as dict
        # memused: int = 0  # In bytes
        # memtotal: int = 0  # In bytes
        # cpuused: float = 0  # 0-1 (cpu usage)
        # uptime: int = 0  # In seconds
        # disks: typing.List[typing.Tuple[str, int, int]] = []  # List of tuples (name, used, total)
        # connections: int = 0  # Number of connections
        # current_users: int = 0  # Number of current users

        # Create an stat object
        memTotal = random.randint(100000000, 1000000000)  # nosec: test data
        memUsed = random.randint(0, memTotal)  # nosec: test data
        stats = types.servers.ServerStatsType(
            memused=memTotal,
            memtotal=memUsed,
            cpuused=random.random(),  # nosec: test data
            uptime=random.randint(0, 1000000),  # nosec: test data
            disks=[
                (
                    'c:\\',
                    random.randint(0, 100000000),  # nosec: test data
                    random.randint(100000000, 1000000000),  # nosec: test data
                ),
                (
                    'd:\\',
                    random.randint(0, 100000000),  # nosec: test data
                    random.randint(100000000, 1000000000),  # nosec: test data
                ),
            ],
            connections=random.randint(0, 100),  # nosec: test data
            current_users=random.randint(0, 100),  # nosec: test data
        )

        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'ping',
                'stats': stats.asDict(),
            },
        )

        self.assertEqual(response.status_code, 200)

        server_stats = self.server.properties.get('stats', None)
        self.assertIsNotNone(server_stats)
        # Get stats, but clear stamp
        statsResponse = types.servers.ServerStatsType.fromDict(server_stats, stamp=0)
        self.assertEqual(statsResponse, stats)
        # Ensure that stamp is not 0 on server_stats dict
        self.assertNotEqual(server_stats['stamp'], 0)

        # Ensure stat is valid right now
        statsResponse = types.servers.ServerStatsType.fromDict(server_stats)
        self.assertTrue(statsResponse.is_valid)
        statsResponse = types.servers.ServerStatsType.fromDict(server_stats, stamp=getSqlStamp() - consts.DEFAULT_CACHE_TIMEOUT - 1)
        self.assertFalse(statsResponse.is_valid)

    def test_event_ping_without_stats(self) -> None:
        # Create an stat object
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'ping',
            },
        )

        self.assertEqual(response.status_code, 200)

        server_stats = self.server.properties.get('stats', None)
        self.assertIsNone(server_stats)
