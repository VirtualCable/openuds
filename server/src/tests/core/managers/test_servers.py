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
import typing
import datetime
import time
from unittest import mock
import functools

from uds import models
from uds.core import types, exceptions
from uds.core.managers import servers
from uds.core.util import storage

from ...fixtures import servers as servers_fixtures
from ...fixtures import services as services_fixtures
from ...utils.test import UDSTestCase

NUM_REGISTEREDSERVERS = 8
NUM_USERSERVICES = NUM_REGISTEREDSERVERS + 1


class ServerManagerUnmanagedServersTest(UDSTestCase):
    user_services: typing.List['models.UserService']
    manager: 'servers.ServerManager' = servers.ServerManager().manager()
    registered_servers_group: 'models.RegisteredServerGroup'
    manager_storage: 'storage.Storage'
    assign: typing.Callable[..., typing.Tuple[str, int]]

    def setUp(self) -> None:
        super().setUp()
        self.user_services = []
        for i in range(NUM_USERSERVICES):
            # So we have 8 userservices, each one with a different user
            self.user_services.extend(services_fixtures.createCacheTestingUserServices())

        self.registered_servers_group = servers_fixtures.createRegisteredServerGroup(
            type=types.servers.ServerType.UNMANAGED, subtype='test', num_servers=NUM_REGISTEREDSERVERS
        )
        self.manager_storage = storage.Storage(servers.ServerManager.STORAGE_NAME)
        # commodity call to assign
        self.assign = functools.partial(
            self.manager.assign,
            serverGroup=self.registered_servers_group,
            serviceType=types.services.ServiceType.VDI,
            minMemoryMB=128,
        )

    def testAssignAuto(self) -> None:
        all_uuids: typing.List[str] = list(
            self.registered_servers_group.servers.all().values_list('uuid', flat=True)
        )

        with mock.patch('uds.core.managers.servers_api.request.ServerApiRequester') as mockServerApiRequester:
            # Patch ApiRequester.getStats to return None, because unmanaged does not have Stats (nor any other data :P)
            mockServerApiRequester.return_value.getStats.return_value = None
            for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                expected_getStats_calls = NUM_REGISTEREDSERVERS * (elementNumber + 1)
                expected_notifyAssign_calls = elementNumber * 33  # 32 in loop + 1 in first assign
                uuid, counter = self.assign(userService)
                storage_key = self.manager.storage_key(self.registered_servers_group, userService.user)
                # uuid shuld be one on registered servers
                self.assertTrue(uuid in all_uuids)
                # Server locked should be None
                self.assertIsNone(models.RegisteredServer.objects.get(uuid=uuid).locked)

                # mockServer.getStats has been called NUM_REGISTEREDSERVERS times
                self.assertEqual(
                    mockServerApiRequester.return_value.getStats.call_count,
                    expected_getStats_calls,
                    f'Error on loop {elementNumber}',
                )
                # notifyAssign should has been called once
                self.assertEqual(
                    mockServerApiRequester.return_value.notifyAssign.call_count, expected_notifyAssign_calls + 1
                )
                # Server storage should contain the assignation
                with self.manager_storage.map() as stor:
                    self.assertEqual(len(stor), elementNumber + 1)
                    uuid_counter = stor[storage_key]
                    # uuid_counter is (uuid, assign counter)
                    self.assertEqual(uuid_counter[0], uuid)
                    self.assertEqual(uuid_counter[1], counter)

                # Again, try to assign, same user service, same group, same service type, same minMemoryMB and same uuid
                for i in range(32):
                    uuid2, counter = self.assign(userService)
                    # uuid2 should be the same as uuid
                    self.assertEqual(uuid, uuid2)
                    # uuid2 should be one on registered servers
                    self.assertTrue(uuid2 in all_uuids)
                    self.assertIsNone(models.RegisteredServer.objects.get(uuid=uuid).locked)  # uuid is uuid2

                    # mockServer.getStats has been called NUM_REGISTEREDSERVERS times, because no new requests has been done
                    self.assertEqual(
                        mockServerApiRequester.return_value.getStats.call_count, expected_getStats_calls
                    )
                    # notifyAssign should has been called twice
                    self.assertEqual(
                        mockServerApiRequester.return_value.notifyAssign.call_count,
                        expected_notifyAssign_calls + i + 2,
                    )
                    # Server storage should contain the assignation
                    with self.manager_storage.map() as stor:
                        self.assertEqual(len(stor), elementNumber + 1)
                        uuid_counter = stor[storage_key]
                        # uuid_counter is (uuid, assign counter)
                        self.assertEqual(uuid_counter[0], uuid)
                        self.assertEqual(uuid_counter[1], counter)

            # Now, remove all asignations..
            for elementNumber, userService in enumerate(self.user_services):
                expected_getStats_calls = NUM_REGISTEREDSERVERS * (elementNumber + 1)
                expected_notifyAssign_calls = elementNumber * 33  # 32 in loop + 1 in first assign
                storage_key = self.manager.storage_key(self.registered_servers_group, userService.user)


                # # Remove it, should decrement counter
                for i in range(32, -1, -1):  # Deletes 33 times
                    res = self.manager.release(userService, self.registered_servers_group)

                    with self.manager_storage.map() as stor:
                        if i != 0:
                            self.assertEqual(len(stor), NUM_USERSERVICES - elementNumber)
                            uuid_counter = stor[storage_key]
                            # uuid_counter is (uuid, assign counter)
                            self.assertEqual(uuid_counter[0], res[0])  # type: ignore
                            self.assertEqual(uuid_counter[1], i)
                        else:
                            self.assertEqual(len(stor), NUM_USERSERVICES - elementNumber - 1)
                            self.assertIsNone(res)

    def testAssignAutoLock(self) -> None:
        all_uuids: typing.List[str] = list(
            self.registered_servers_group.servers.all().values_list('uuid', flat=True)
        )
        with mock.patch('uds.core.managers.servers_api.request.ServerApiRequester') as mockServerApiRequester:
            # def getStats(self) -> typing.Optional[types.servers.ServerStatsType]:
            mockServerApiRequester.return_value.getStats.return_value = None
            # Assign all user services with lock
            for elementNumber, userService in enumerate(self.user_services[:NUM_REGISTEREDSERVERS]):
                uuid, counter = self.assign(
                    userService,
                    lockTime=datetime.timedelta(seconds=1),
                )
                storage_key = self.manager.storage_key(self.registered_servers_group, userService.user)
                # uuid shuld be one on registered servers
                self.assertTrue(uuid in all_uuids)
                # Server locked should not be None (that is, it should be locked)
                self.assertIsNotNone(models.RegisteredServer.objects.get(uuid=uuid).locked)

                with self.manager_storage.map() as stor:
                    self.assertEqual(len(stor), elementNumber + 1)
                    uuid_counter = stor[storage_key]
                    # uuid_counter is (uuid, assign counter)
                    self.assertEqual(uuid_counter[0], uuid)
                    self.assertEqual(uuid_counter[1], counter)

                
            # Next one should fail with an exceptions.UDSException
            with self.assertRaises(exceptions.UDSException):
                self.assign(self.user_services[NUM_REGISTEREDSERVERS], lockTime=datetime.timedelta(seconds=1))
                
            # Wait a couple of seconds, and try again, it should work
            time.sleep(2)
            self.assign(self.user_services[NUM_REGISTEREDSERVERS], lockTime=datetime.timedelta(seconds=1))
            
            # notifyRelease should has been called once
            self.assertEqual(mockServerApiRequester.return_value.notifyRelease.call_count, 1)
            

            # # Server storage should contain the assignation
            # with self.manager_storage.map() as stor:
            #     self.assertEqual(len(stor), 1)
            #     uuid_counter = stor[storage_key]
            #     # uuid_counter is (uuid, assign counter)
            #     self.assertEqual(uuid_counter[0], uuid)
            #     self.assertEqual(uuid_counter[1], counter)

            # If ask for another the same user_service, should return the same uuid
