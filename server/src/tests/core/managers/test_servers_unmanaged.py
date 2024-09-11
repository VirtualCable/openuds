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
import collections.abc
import datetime
import time
from unittest import mock
import functools
import logging

from uds import models
from uds.core import types
from uds.core.managers import servers

from ...fixtures import servers as servers_fixtures
from ...fixtures import services as services_fixtures
from ...utils.test import UDSTestCase

logger = logging.getLogger(__name__)

NUM_REGISTEREDSERVERS = 8
NUM_USERSERVICES = NUM_REGISTEREDSERVERS + 1


class ServerManagerUnmanagedServersTest(UDSTestCase):
    user_services: list['models.UserService']
    manager: 'servers.ServerManager'
    registered_servers_group: 'models.ServerGroup'
    assign: collections.abc.Callable[..., typing.Optional[types.servers.ServerCounter]]
    all_uuids: list[str]

    def setUp(self) -> None:
        super().setUp()
        self.user_services = []
        self.manager = servers.ServerManager().manager()
        # Manager is a singleton, clear counters
        # self.manager.clearCounters()

        for _ in range(NUM_USERSERVICES):
            # So we have 8 userservices, each one with a different user
            self.user_services.extend(services_fixtures.create_db_assigned_userservices())

        self.registered_servers_group = servers_fixtures.create_server_group(
            type=types.servers.ServerType.UNMANAGED, subtype='test', num_servers=NUM_REGISTEREDSERVERS
        )
        # commodity call to assign
        self.assign = functools.partial(
            self.manager.assign,
            server_group=self.registered_servers_group,
            service_type=types.services.ServiceType.VDI,
        )
        self.all_uuids: list[str] = list(
            self.registered_servers_group.servers.all().values_list('uuid', flat=True)
        )

    @contextmanager
    def createMockApiRequester(self) -> typing.Iterator[mock.Mock]:
        with mock.patch('uds.core.managers.servers_api.requester.ServerApiRequester') as mockServerApiRequester:
            mockServerApiRequester.return_value.get_stats.return_value = None
            yield mockServerApiRequester

    def testAssignAuto(self) -> None:
        with self.createMockApiRequester() as mockServerApiRequester:
            for element_number, userservice in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                expected_get_stats_calls = NUM_REGISTEREDSERVERS * (element_number + 1)
                expected_notify_assign_calls = element_number * 33  # 32 in loop + 1 in first assign
                assignation = self.assign(userservice)
                if assignation is None:
                    self.fail('Assignation returned None')
                    return  # For mypy
                uuid, counter = assignation
                prop_name = self.manager.property_name(userservice.user)
                # uuid shuld be one on registered servers
                self.assertTrue(uuid in self.all_uuids)
                # Server locked should be None
                self.assertIsNone(models.Server.objects.get(uuid=uuid).locked_until)

                # mockServer.get_stats has been called NUM_REGISTEREDSERVERS times
                self.assertEqual(
                    mockServerApiRequester.return_value.get_stats.call_count,
                    expected_get_stats_calls,
                    f'Error on loop {element_number}',
                )
                # notify_assign should has been called once for each user service
                self.assertEqual(
                    mockServerApiRequester.return_value.notify_assign.call_count, expected_notify_assign_calls + 1
                )
                # notify_assign paramsh should have been
                # request.ServerApiRequester(bestServer).notify_assign(userservice, serviceType, uuid_counter[1])
                self.assertEqual(
                    mockServerApiRequester.return_value.notify_assign.call_args[0][0], userservice
                )  # userservice
                self.assertEqual(
                    mockServerApiRequester.return_value.notify_assign.call_args[0][1],
                    types.services.ServiceType.VDI,
                )
                self.assertEqual(
                    mockServerApiRequester.return_value.notify_assign.call_args[0][2], counter
                )  # counter

                # Server storage should contain the assignation
                self.assertEqual(len(self.registered_servers_group.properties), element_number + 1)
                self.assertEqual(self.registered_servers_group.properties[prop_name], [uuid, counter])

                # Again, try to assign, same user service, same group, same service type, same minMemoryMB and same uuid
                for i in range(32):
                    assignation = self.assign(userservice)
                    if assignation is None:
                        self.fail('Assignation returned None')
                        return  # For mypy
                    uuid2, counter = assignation
                    # uuid2 should be the same as uuid
                    self.assertEqual(uuid, uuid2)
                    # uuid2 should be one on registered servers
                    self.assertTrue(uuid2 in self.all_uuids)
                    self.assertIsNone(models.Server.objects.get(uuid=uuid).locked_until)  # uuid is uuid2

                    # mockServer.get_stats has been called NUM_REGISTEREDSERVERS times, because no new requests has been done
                    self.assertEqual(
                        mockServerApiRequester.return_value.get_stats.call_count, expected_get_stats_calls
                    )
                    # notify_assign should has been called twice
                    self.assertEqual(
                        mockServerApiRequester.return_value.notify_assign.call_count,
                        expected_notify_assign_calls + i + 2,
                    )

                    self.assertEqual(len(self.registered_servers_group.properties), element_number + 1)
                    self.assertEqual(self.registered_servers_group.properties[prop_name], [uuid, counter])

            # Now, remove all asignations..
            for element_number, userservice in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                expected_get_stats_calls = NUM_REGISTEREDSERVERS * (element_number + 1)
                expected_notify_assign_calls = element_number * 33  # 32 in loop + 1 in first assign
                prop_name = self.manager.property_name(userservice.user)

                # # Remove it, should decrement counter
                for i in range(32, -1, -1):  # Deletes 33 times
                    _res = self.manager.release(userservice, self.registered_servers_group)

            self.assertEqual(len(self.registered_servers_group.properties), 0)

    def test_assign_autolock_limit(self) -> None:
        with self.createMockApiRequester() as mockServerApiRequester:
            # Assign all user services with lock
            for userservice in self.user_services[:NUM_REGISTEREDSERVERS]:
                assignation = self.assign(userservice, lock_interval=datetime.timedelta(seconds=1.1))
                if assignation is None:
                    self.fail('Assignation returned None')
                    return  # For mypy
                uuid, counter = assignation
                
                # uuid shuld be one on registered servers
                self.assertTrue(uuid in self.all_uuids)
                # And only one assignment, so counter is 1
                self.assertTrue(counter, 1)
                # Server locked should not be None (that is, it should be locked)
                self.assertIsNotNone(models.Server.objects.get(uuid=uuid).locked_until)

            # Next one should fail with aa None return
            self.assertIsNone(
                self.assign(self.user_services[NUM_REGISTEREDSERVERS], lock_interval=datetime.timedelta(seconds=1))
            )

            # Wait a bit more than a second, and try again, it should work
            time.sleep(1.1)
            self.assign(self.user_services[NUM_REGISTEREDSERVERS], lock_interval=datetime.timedelta(seconds=1))

            # notify_release should has been called once
            self.assertEqual(mockServerApiRequester.return_value.notify_release.call_count, 1)

    def testAssignReleaseMax(self) -> None:
        with self.createMockApiRequester() as mockServerApiRequester:
            serverApiRequester = mockServerApiRequester.return_value
            for assignation in range(3):
                for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                    assign = self.assign(userService)
                    self.assertEqual(
                        serverApiRequester.notify_assign.call_count,
                        assignation * NUM_REGISTEREDSERVERS + elementNumber + 1,
                    )
                    if assign is None:
                        self.fail('Assignation returned None')
                        return  # For mypy
                    uuid, counter = assign
                    # uuid shuld be one on registered servers
                    self.assertTrue(uuid in self.all_uuids)
                    # And only one assignment, so counter is 1
                    self.assertTrue(counter, 1)
                    # Server locked should be None
                    self.assertIsNone(models.Server.objects.get(uuid=uuid).locked_until)
                    self.assertEqual(self.manager.get_unmanaged_usage(uuid), assignation + 1)

            self.assertEqual(len(self.registered_servers_group.properties), NUM_REGISTEREDSERVERS)

            # Now release all, 3 times
            for release in range(3):
                for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                    res = self.manager.release(userService, self.registered_servers_group)
                    if res:
                        uuid, counter = res
                        # uuid shuld be one on registered servers
                        self.assertTrue(uuid in self.all_uuids)
                        # Number of lasting assignations should be one less than before
                        self.assertEqual(counter, 3 - release - 1)
                        # Server locked should be None
                        self.assertIsNone(models.Server.objects.get(uuid=uuid).locked_until)
                        # 3 - release -1 because we have released it already
                        self.assertEqual(
                            self.manager.get_unmanaged_usage(uuid),
                            3 - release - 1,
                            f'Error on {elementNumber}/{release}',
                        )
                    self.assertEqual(
                        serverApiRequester.notify_release.call_count,
                        release * NUM_REGISTEREDSERVERS + elementNumber + 1,
                        f'Error on loop {release} - {elementNumber}',
                    )                        
            self.assertEqual(len(self.registered_servers_group.properties), 0)
