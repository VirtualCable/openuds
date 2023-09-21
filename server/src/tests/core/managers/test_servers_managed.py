# -*- coding: utf-8 -*-

#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
from contextlib import contextmanager
import typing
import datetime
import time
from unittest import mock
import functools
import logging

from uds import models
from uds.core import types, exceptions
from uds.core.managers import servers

from ...fixtures import servers as servers_fixtures
from ...fixtures import services as services_fixtures
from ...utils.test import UDSTestCase

logger = logging.getLogger(__name__)

NUM_REGISTEREDSERVERS: typing.Final[int] = 8
NUM_USERSERVICES: typing.Final[int] = NUM_REGISTEREDSERVERS * 2

MB: typing.Final[int] = 1024 * 1024
GB: typing.Final[int] = 1024 * MB

MIN_TEST_MEMORY_MB: typing.Final[int] = 512


class ServerManagerManagedServersTest(UDSTestCase):
    user_services: typing.List['models.UserService']
    manager: 'servers.ServerManager'
    registered_servers_group: 'models.ServerGroup'
    assign: typing.Callable[..., typing.Optional[types.servers.ServerCounter]]
    all_uuids: typing.List[str]
    server_stats: typing.Dict[str, 'types.servers.ServerStats']

    def setUp(self) -> None:
        super().setUp()
        self.user_services = []
        self.manager = servers.ServerManager().manager()
        # Manager is a singleton, clear counters
        # self.manager.clearCounters()

        for i in range(NUM_USERSERVICES):
            # So we have 8 userservices, each one with a different user
            self.user_services.extend(services_fixtures.createCacheTestingUserServices())

        self.registered_servers_group = servers_fixtures.createServerGroup(
            type=types.servers.ServerType.SERVER, subtype='test', num_servers=NUM_REGISTEREDSERVERS
        )
        # commodity call to assign
        self.assign = functools.partial(
            self.manager.assign,
            serverGroup=self.registered_servers_group,
            serviceType=types.services.ServiceType.VDI,
            minMemoryMB=MIN_TEST_MEMORY_MB,
        )
        self.all_uuids: typing.List[str] = list(
            self.registered_servers_group.servers.all().values_list('uuid', flat=True)
        )

        self.server_stats = {
            server.uuid: types.servers.ServerStats(
                memused=(NUM_REGISTEREDSERVERS - i) * GB,
                memtotal=NUM_REGISTEREDSERVERS * 2 * GB,
                cpuused=(NUM_REGISTEREDSERVERS - i) / NUM_REGISTEREDSERVERS,
                current_users=0,
            )
            for i, server in enumerate(list(self.registered_servers_group.servers.all()))
        }

    @contextmanager
    def createMockApiRequester(
        self,
        getStats: typing.Optional[
            typing.Callable[['models.Server'], typing.Optional['types.servers.ServerStats']]
        ] = None,
    ) -> typing.Iterator[mock.Mock]:
        with mock.patch('uds.core.managers.servers_api.requester.ServerApiRequester') as mockServerApiRequester:

            def _getStats() -> typing.Optional[types.servers.ServerStats]:
                # Get first argument from call to init on serverApiRequester
                server = mockServerApiRequester.call_args[0][0]
                logger.debug('Getting stats for %s', server.host)
                return (getStats or (lambda x: self.server_stats.get(x.uuid)))(server)

            # return_value returns the instance of the mock
            mockServerApiRequester.return_value.getStats.side_effect = _getStats
            yield mockServerApiRequester

    def testAssignAuto(self) -> None:
        with self.createMockApiRequester() as mockServerApiRequester:
            for elementNumber, userService in enumerate(self.user_services):
                expected_getStats_calls = NUM_REGISTEREDSERVERS * (elementNumber + 1)
                expected_notifyAssign_calls = elementNumber * 33  # 32 in loop + 1 in first assign
                assignation = self.assign(userService)
                if assignation is None:
                    self.fail('Assignation returned None')
                    return  # For mypy
                uuid, counter = assignation
                # Update only users, as the connection does not consume memory nor cpu
                self.server_stats[uuid] = self.server_stats[uuid]._replace(
                    current_users=self.server_stats[uuid].current_users + 1
                )

                prop_name = self.manager.propertyName(userService.user)
                # uuid shuld be one on registered servers
                self.assertTrue(uuid in self.all_uuids)
                # Server locked should be None
                self.assertIsNone(models.Server.objects.get(uuid=uuid).locked_until)

                # mockServer.getStats has been called NUM_REGISTEREDSERVERS times
                self.assertEqual(
                    mockServerApiRequester.return_value.getStats.call_count,
                    expected_getStats_calls,
                    f'Error on loop {elementNumber}',
                )
                # notifyAssign should has been called once for each user service
                self.assertEqual(
                    mockServerApiRequester.return_value.notifyAssign.call_count, expected_notifyAssign_calls + 1
                )
                # notifyAssign paramsh should have been
                # request.ServerApiRequester(bestServer).notifyAssign(userService, serviceType, uuid_counter[1])
                self.assertEqual(
                    mockServerApiRequester.return_value.notifyAssign.call_args[0][0], userService
                )  # userService
                self.assertEqual(
                    mockServerApiRequester.return_value.notifyAssign.call_args[0][1],
                    types.services.ServiceType.VDI,
                )
                self.assertEqual(
                    mockServerApiRequester.return_value.notifyAssign.call_args[0][2], counter
                )  # counter

                # Server storage should contain the assignation
                self.assertEqual(len(self.registered_servers_group.properties), elementNumber + 1)
                uuid_counter = self.registered_servers_group.properties[prop_name]
                # uuid_counter is (uuid, assign counter)
                self.assertEqual(uuid_counter[0], uuid)
                self.assertEqual(uuid_counter[1], counter)

                # Again, try to assign, same user service, same group, same service type, same minMemoryMB and same uuid
                for i in range(32):
                    assignation = self.assign(userService)
                    if assignation is None:
                        self.fail('Assignation returned None')
                        return  # For mypy
                    uuid2, counter = assignation
                    # uuid2 should be the same as uuid
                    self.assertEqual(uuid, uuid2)
                    # uuid2 should be one on registered servers
                    self.assertTrue(uuid2 in self.all_uuids)
                    self.assertIsNone(models.Server.objects.get(uuid=uuid).locked_until)  # uuid is uuid2

                    # mockServer.getStats has been called NUM_REGISTEREDSERVERS times, because no new requests has been done
                    self.assertEqual(
                        mockServerApiRequester.return_value.getStats.call_count, expected_getStats_calls
                    )
                    # notifyAssign should has been called twice
                    self.assertEqual(
                        mockServerApiRequester.return_value.notifyAssign.call_count,
                        expected_notifyAssign_calls + i + 2,
                    )

                    # Server storage should have elementNumber + 1 elements
                    self.assertEqual(len(self.registered_servers_group.properties), elementNumber + 1)
                    uuid_counter = self.registered_servers_group.properties[prop_name]
                    # uuid_counter is (uuid, assign counter)
                    self.assertEqual(uuid_counter[0], uuid)
                    self.assertEqual(uuid_counter[1], counter)

            # Now, remove all asignations..
            for elementNumber, userService in enumerate(self.user_services):
                expected_getStats_calls = NUM_REGISTEREDSERVERS * (elementNumber + 1)
                expected_notifyAssign_calls = elementNumber * 33  # 32 in loop + 1 in first assign

                # # Remove it, should decrement counter
                for i in range(32, -1, -1):  # Deletes 33 times
                    res = self.manager.release(userService, self.registered_servers_group)

            self.assertEqual(len(self.registered_servers_group.properties), 0)

    def testAssignAutoLockLimit(self) -> None:
        with self.createMockApiRequester() as mockServerApiRequester:
            # Assign all user services with lock
            for userService in self.user_services[:NUM_REGISTEREDSERVERS]:
                assignation = self.assign(userService, lockTime=datetime.timedelta(seconds=1))
                if assignation is None:
                    self.fail('Assignation returned None')
                    return  # For mypy
                uuid, counter = assignation
                # uuid shuld be one on registered servers
                self.assertTrue(uuid in self.all_uuids)
                # And only one assignment, so counter is 1, (because of the lock)
                self.assertTrue(counter, 1)
                # Server locked should not be None (that is, it should be locked)
                self.assertIsNotNone(models.Server.objects.get(uuid=uuid).locked_until)

            # Next one should fail returning None
            self.assertIsNone(
                self.assign(self.user_services[NUM_REGISTEREDSERVERS], lockTime=datetime.timedelta(seconds=1))
            )

            # Wait a second, and try again, it should work
            time.sleep(1)
            self.assign(self.user_services[NUM_REGISTEREDSERVERS], lockTime=datetime.timedelta(seconds=1))

            # notifyRelease should has been called once
            self.assertEqual(mockServerApiRequester.return_value.notifyRelease.call_count, 1)

    def testAssignReleaseMax(self) -> None:
        with self.createMockApiRequester() as mockServerApiRequester:
            serverApiRequester = mockServerApiRequester.return_value
            for assignations in range(2):  # Second pass will get current assignation, not new ones
                for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                    # Ensure locking server, so we have to use every server only once
                    assignation = self.assign(userService, lockTime=datetime.timedelta(seconds=32))
                    self.assertEqual(
                        serverApiRequester.notifyAssign.call_count,
                        assignations * NUM_REGISTEREDSERVERS + elementNumber + 1,
                    )
                    if assignation is None:
                        self.fail('Assignation returned None')
                        return  # For mypy
                    uuid, counter = assignation
                    # uuid shuld be one on registered servers
                    self.assertTrue(uuid in self.all_uuids)
                    # And only one assignment, so counter is 1
                    self.assertTrue(counter, 1)
                    # Server locked should be None
                    self.assertIsNotNone(models.Server.objects.get(uuid=uuid).locked_until)

            # Trying to lock a new one, should fail
            self.assertIsNone(
                self.assign(self.user_services[NUM_REGISTEREDSERVERS], lockTime=datetime.timedelta(seconds=32))
            )

            # All servers should be locked
            for server in self.registered_servers_group.servers.all():
                self.assertIsNotNone(server.locked_until)

            # Storage should have NUM_REGISTEREDSERVERS elements
            self.assertEqual(len(self.registered_servers_group.properties), NUM_REGISTEREDSERVERS)

            with self.manager.cntStorage() as stor:
                self.assertEqual(len(stor), 0)  # No counter storage for managed servers

            # Now release all, twice
            for release in range(2):
                for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                    res = self.manager.release(userService, self.registered_servers_group)
                    if res:
                        uuid, counter = res
                        # uuid shuld be one on registered servers
                        self.assertTrue(uuid in self.all_uuids)
                        # Number of lasting assignations should be one less than before
                        self.assertEqual(counter, 2 - release - 1)
                    else:
                        self.fail('Release returned None')
                    self.assertEqual(
                        serverApiRequester.notifyRelease.call_count,
                        release * NUM_REGISTEREDSERVERS + elementNumber + 1,
                        f'Error on loop {release} - {elementNumber}',
                    )

            # All servers should be unlocked
            for server in self.registered_servers_group.servers.all():
                self.assertIsNone(server.locked_until)

            self.assertEqual(len(self.registered_servers_group.properties), 0)

            with self.manager.cntStorage() as stor:
                self.assertEqual(len(stor), 0)

            # Trying to release again should return '', 0
            for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                res = self.manager.release(userService, self.registered_servers_group)
                if res:
                    uuid, counter = res
                    self.assertEqual(uuid, '')
                    # Number of lasting assignations should be one less than before
                    self.assertEqual(counter, 0)
                    self.assertEqual(
                        serverApiRequester.notifyRelease.call_count,
                        2 * NUM_REGISTEREDSERVERS,  # No release if all are released already, so no notifyRelease
                    )
