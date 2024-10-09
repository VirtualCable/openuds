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
import datetime
from unittest import mock

from uds import models
from uds.core import consts, types
from uds.core.util import fields

from ...utils.test import UDSTransactionTestCase

from uds.migrations.fixers.providers_v4 import physical_machine_multiple

from uds.services.PhysicalMachines import (
    service_single,
    service_multi,
    deployment,
    deployment_multi,
)

# Data from 3.6 version

PROVIDER_DATA: typing.Final[dict[str, typing.Any]] = {
    'id': 1,
    'uuid': 'e8af96f0-49aa-5a14-be45-1ffea6e4d340',
    'name': '--- Test Machines',
    'data_type': 'PhysicalMachinesServiceProvider',
    'data': 'eJxLzs9Ly0xnBgALIAJ6',
    'comments': '',
    'maintenance_mode': False,
}

SERVICES_DATA: typing.Final[list[dict[str, typing.Any]]] = [
    {
        'id': 144,
        'uuid': '35a58de3-5af9-5099-bfcf-25a1581c2385',
        'name': 'Multiple IPS',
        'data_type': 'IPMachinesService',
        'data': 'djcATVVMVElfVE9LRU4AMAAzMgA0OAB0cnVlAHRydWU=',
        'comments': '',
        'provider_id': 1,
        'token': 'MULTI_TOKEN',
    },
    {
        'id': 142,
        'uuid': 'edadff6c-fd63-570f-a8be-0af4574ec3a4',
        'name': 'Single ip',
        'data_type': 'IPSingleMachineService',
        'data': 'eJzLLGDOyU9OzMnILy4BAByIBKY=',
        'comments': '',
        'provider_id': 1,
        'token': None,
    },
]

SINGLE_IP_SERVICE_IDX: typing.Final[int] = 1
MULTIPLE_IP_SERVICE_IDX: typing.Final[int] = 0

SERVICEPOOLS_DATA: typing.Final[list[dict[str, typing.Any]]] = [
    {
        'id': 100,
        'uuid': 'c7b3d1a4-dcf1-5381-96c2-c27c7a7df414',
        'name': '--- Multiple IP',
        'short_name': '',
        'comments': '',
        'service_id': 144,
        'osmanager_id': None,
        'state': 'A',
        'state_date': datetime.datetime(1972, 7, 1, 0, 0),
        'show_transports': True,
        'visible': True,
        'allow_users_remove': False,
        'allow_users_reset': False,
        'ignores_unused': False,
        'image_id': None,
        'servicesPoolGroup_id': None,
        'calendar_message': '',
        'fallbackAccess': 'ALLOW',
        'account_id': None,
        'initial_srvs': 0,
        'cache_l1_srvs': 0,
        'cache_l2_srvs': 0,
        'max_srvs': 0,
        'current_pub_revision': 1,
    },
    {
        'id': 101,
        'uuid': 'a1ea4c12-b625-5bea-9968-e27d1deb5981',
        'name': '--- Single IP',
        'short_name': '',
        'comments': '',
        'service_id': 142,
        'osmanager_id': None,
        'state': 'A',
        'state_date': datetime.datetime(1972, 7, 1, 0, 0),
        'show_transports': True,
        'visible': True,
        'allow_users_remove': False,
        'allow_users_reset': False,
        'ignores_unused': False,
        'image_id': None,
        'servicesPoolGroup_id': None,
        'calendar_message': '',
        'fallbackAccess': 'ALLOW',
        'account_id': None,
        'initial_srvs': 0,
        'cache_l1_srvs': 0,
        'cache_l2_srvs': 0,
        'max_srvs': 0,
        'current_pub_revision': 1,
    },
]

SINGLE_IP_SERVICEPOOL_IDX: typing.Final[int] = 1
MULTIPLE_IP_SERVICEPOOL_IDX: typing.Final[int] = 0

USERSERVICES_DATA: typing.Final[list[dict[str, typing.Any]]] = [
    {
        'id': 1000,
        'uuid': 'f1ac7d5-58c8-55c3-8bab-24ea1ed40be5',
        'deployed_service_id': 100,
        'publication_id': None,
        'unique_id': 'localhost',
        'friendly_name': 'localhost',
        'state': 'U',
        'os_state': 'U',
        'state_date': datetime.datetime(2024, 4, 25, 2, 51, 13),
        'creation_date': datetime.datetime(2024, 4, 25, 2, 51, 12),
        'data': 'QlpoOTFBWSZTWR3s2WMAAJbfgDAQAEF/4CEBEQC+9d8gMAD4AwyNNNMjCZGCaAwYZGmmmRhMjBNAYG9VIJ6U8jTRMEmnoGmp+qfP8+6zBteG1ucJvU7tHB7PDN+qJKe/t1dlXWO88OKzF0gvY0JepWOsfMfq2LmqsX6sdKvdkxWx5jKLe61gxYLGr6VUWMpNHla6mqi9g52xyXNkUjLmzf7nZFjfZFViriy4OVIuUa4bElzVxWyOzFJ57RVJyVVjfWvq3M5fok0ii5q2xsaqs3RV6OcZqR0VVdmT/i7kinChIDvZssY=',
        'user_id': None,  # Invalid value on a production system, but valid for tests
        'in_use': False,
        'in_use_date': datetime.datetime(1972, 7, 1, 0, 0),
        'cache_level': 0,
        'src_hostname': '172.27.0.8',
        'src_ip': '172.27.0.8',
    },
    {
        'id': 1001,
        'uuid': 'd78c4e51-58d2-55dc-902e-07c45b8ba636',
        'deployed_service_id': 100,
        'publication_id': None,
        'unique_id': '172.27.1.26',
        'friendly_name': '172.27.1.26',
        'state': 'U',
        'os_state': 'U',
        'state_date': datetime.datetime(2024, 4, 25, 2, 56, 17),
        'creation_date': datetime.datetime(2024, 4, 25, 2, 56, 12),
        'data': 'QlpoOTFBWSZTWSXhxOYAAJrfgDAQAEF/4CEBEQC+td8gMAD4AwaaNNMJiZMBA0wwaaNNMJiZMBA0wb1URMJiNI0yGmk09D1Pn67XzBm8M2jk4u7Vyezw0faiS3t7dXqwdY7y3LXw8m7N0jppVjZKyMKKY1jeupIxZR1j/R9rI3Nl8bOHO5wZMVkfkb47qsGbBVs+mKirKTV+rHubKNzBWPNY3RSN/Vok2aVi5Vc1cXlSLFF1qSxs4rJHRgk/PSL0nJevjS7Vm0t4JO0UWtmUXNl7RzXsXnGikc1690ZP4XckU4UJAl4cTmA=',
        'user_id': None,
        'in_use': False,
        'in_use_date': datetime.datetime(1972, 7, 1, 0, 0),
        'cache_level': 0,
        'src_hostname': '172.27.0.1',
        'src_ip': '172.27.0.1',
    },
    {
        'id': 1002,
        'uuid': '57d441a4-d152-583c-b11a-0a0a7b36ab09',
        'deployed_service_id': 101,
        'publication_id': None,
        'unique_id': 'dc.dkmon.local:1',
        'friendly_name': 'dc.dkmon.local:1',
        'state': 'U',
        'os_state': 'U',
        'state_date': datetime.datetime(2024, 4, 25, 3, 13, 47),
        'creation_date': datetime.datetime(2024, 4, 25, 3, 13, 47),
        'data': 'QlpoOTFBWSZTWbWQavUAAJlfgDAQAEF/4CEBEQC+v98hMAD4Aw0MmQMjEGJk0NMGGhkyBkYgxMmhpgbVJkekMlPEm0yhhNNqep+qePjyyiSPRImZL2HdTEyNj0YG44Sr+duhqROiOq/DM7v1kaoo5JESbgUR1yGRaj9HogUGRQsvzY+i8uHo3RvJEO5AtLi0qKHkwiVvIE0siQ82DgcVlxUjkPK0ORbzI4D3I4S/sE9ESoiZmuZzpUiscRsEnlCY9I2LhLjZDCXuMMjGzkSMIYiWKHECheiwoMTNBi00RMcjQYY1Lxv8XckU4UJC1kGr1A==',
        'user_id': None,
        'in_use': True,
        'in_use_date': datetime.datetime(2024, 4, 25, 3, 13, 47),
        'cache_level': 0,
        'src_hostname': '172.27.0.8',
        'src_ip': '172.27.0.8',
    },
]

STORAGE_DATA: typing.Final[list[dict[str, typing.Any]]] = [
    {
        'owner': 't-service-144',
        'key': '1511fcef403a937af1d7360a297e2b44',
        'data': 'gASVBgAAAAAAAABKMaopZi4=\n',
        'attr1': '',
    },
    {
        'owner': 't-service-144',
        'key': '848d16fb421048c690c9761c11dc1699',
        'data': 'gASVVQAAAAAAAABdlCiMDTE3Mi4yNy4xLjI1fjCUjA0xNzIuMjcuMS4yNn4xlIwNMTcyLjI3LjEuMjd+MpSMHWxvY2FsaG9zdDswMToyMzo0NTo2Nzo4OTpBQn4zlGUu\n',
        'attr1': '',
    },
    {'owner': 't-service-142', 'key': 'b6ac33477ae0a82fa2681c4d398d88d7', 'data': 'gARLAS4=\n', 'attr1': ''},
]


class TestPhysicalMigration(UDSTransactionTestCase):
    def setUp(self) -> None:
        """
        Store on DB Data needed for the tests
        """
        # Provider data
        models.Provider.objects.create(**PROVIDER_DATA)
        # Services data
        for service in SERVICES_DATA:
            models.Service.objects.create(**service)

        # Service pools data
        for servicepool in SERVICEPOOLS_DATA:
            models.ServicePool.objects.create(**servicepool)

        # Userservices data
        for userservice in USERSERVICES_DATA:
            models.UserService.objects.create(**userservice)

        # Storage data
        for storage in STORAGE_DATA:
            models.Storage.objects.create(**storage)

    def apps_mock(self) -> mock.MagicMock:
        def _get_model(_app: str, model: str) -> typing.Any:
            if model == 'Service':
                return models.Service
            elif model == 'ServerGroup':
                return models.ServerGroup
            elif model == 'ServicePool':
                return models.ServicePool
            else:
                raise ValueError(f"Model {model} not found")

        apps = mock.MagicMock()
        apps.get_model.side_effect = _get_model
        return apps

    def test_migrate(self) -> None:
        """
        Test that migration works
        """
        # We have 2 services:
        # - Single IP
        #  - IP is localhost, should be migrated to localhost
        #  - One service pool
        #  - One user service
        # - Multiple IP
        #  - Name: Multiple IPS
        #  - Comment: ''
        #  - Token: MULTI_TOKEN
        #  - Check port: 0
        #  - Skip time on failure: 32
        #  - Max session for machine: 48
        #  - Lock by external access: True
        #  - Use random IP: True
        #  - IPs are:
        #    - 172.27.1.25
        #    - 172.27.1.26
        #    - 172.27.1.27
        #    - localhost;01:23:45:67:89:AB
        #  - One service pool
        #  - Two user services
        #    * First one, is localhost
        #    * Second one is 172.27.1.26

        # First, proceed to migration of data
        physical_machine_multiple.migrate(self.apps_mock(), None)

        # Now check that data has been migrated correctly
        # Single ip
        single_ip = typing.cast('service_single.IPSingleMachineService', models.Service.objects.get(uuid=SERVICES_DATA[SINGLE_IP_SERVICE_IDX]['uuid']).get_instance())
        self.assertEqual(single_ip.host.value, 'localhost')
        
        # Multiple ip
        multi_ip = typing.cast('service_multi.IPMachinesService', models.Service.objects.get(uuid=SERVICES_DATA[MULTIPLE_IP_SERVICE_IDX]['uuid']).get_instance())
        server_group = fields.get_server_group_from_field(multi_ip.server_group)
        self.assertEqual(server_group.name, 'Physical Machines Server Group for Multiple IPS')
        ips_to_check = {'172.27.1.25', '172.27.1.26', '172.27.1.27', '127.0.0.1'}
        for server in server_group.servers.all():
            self.assertEqual(server.server_type, types.servers.ServerType.UNMANAGED, f'Invalid server type for {server.ip}')
            self.assertIn(server.ip, ips_to_check, f'Invalid server ip {server.ip}: {ips_to_check}')
            ips_to_check.remove(server.ip)
            # Ensure has a hostname, and MAC is empty
            self.assertNotEqual(server.hostname, '')
            
            # Localhost has a MAC, rest of servers have MAC_UNKNOWN (empty equivalent)
            # Also, should have 127.0.0.1 as ip if localhost
            if server.hostname == 'localhost':
                self.assertEqual(server.ip, '127.0.0.1')
                self.assertEqual(server.mac, '01:23:45:67:89:AB')
            else:
                self.assertEqual(server.mac, consts.MAC_UNKNOWN)
            
            # If is 172.27.1.26 ensure is locked
            if server.ip == '172.27.1.26' or server.hostname == 'localhost':
                self.assertTrue(server.locked_until is not None and server.locked_until > datetime.datetime.now(), f'Server {server.ip} is not locked')
            else:
                self.assertIsNone(server.locked_until, f'Server {server.ip} is locked')
                
        # Ensure all ips have been checked
        self.assertEqual(len(ips_to_check), 0)
        
        # Now, check UserServices
        for userservice_data in USERSERVICES_DATA:
            # Get the user service
            if userservice_data['deployed_service_id'] == SERVICEPOOLS_DATA[SINGLE_IP_SERVICEPOOL_IDX]['id']:
                userservice = typing.cast('deployment.IPMachineUserService', models.UserService.objects.get(uuid=userservice_data['uuid']).get_instance())
                self.assertEqual(userservice._ip, 'dc.dkmon.local~1')  # Same as original data
            else:
                userservice = typing.cast('deployment_multi.IPMachinesUserService', models.UserService.objects.get(uuid=userservice_data['uuid']).get_instance())
                self.assertEqual(userservice._ip, userservice_data['unique_id'], f'Invalid IP for {userservice_data["unique_id"]}: {userservice._ip}')
