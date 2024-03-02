# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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
import pickle
import typing

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core.environment import Environment

from uds.services.PhysicalMachines import provider, service_multi


# if not data.startswith(b'v'):
#     return super().unmarshal(data)  # New format, use parent unmarshal

# values: list[bytes] = data.split(b'\0')
# # Ensure list of ips is at latest "old" format
# d = self.storage.read_from_db('ips')
# if isinstance(d, str):  # "legacy" saved elements
#     _ips = pickle.loads(d.encode('utf8'))  # nosec: pickle is safe here
#     self.storage.save_to_db('ips', pickle.dumps(_ips))

# self._cached_hosts = None  # Invalidate cache

# if values[0] != b'v1':
#     self._token = values[1].decode()
#     if values[0] in (b'v3', b'v4', b'v5', b'v6', b'v7'):
#         self._port = int(values[2].decode())
#     if values[0] in (b'v4', b'v5', b'v6', b'v7'):
#         self._skipTimeOnFailure = int(values[3].decode())
#     if values[0] in (b'v5', b'v6', b'v7'):
#         self._maxSessionForMachine = int(values[4].decode())
#     if values[0] in (b'v6', b'v7'):
#         self._lockByExternalAccess = gui.as_bool(values[5].decode())
#     if values[0] in (b'v7',):
#         self._useRandomIp = gui.as_bool(values[6].decode())

# # Sets maximum services for this
# self.userservices_limit = len(self.hosts)

# self.flag_for_upgrade()  # Flag for upgrade as soon as possible
EXPECTED_FIELDS: typing.Final[set[str]] = {
    '_token',
    '_port',
    '_skip_time_on_failure',
    '_max_session_for_machine',
    '_lock_by_external_access',
    '_use_random_ip',
}

STORED_IPS: typing.Final[typing.List[str]] = [f'{i};mac{i}~{i}' for i in range(1, 128)]
EDITABLE_STORED_IPS: typing.Final[typing.List[str]] = [i.split('~')[0] for i in STORED_IPS]

SERIALIZED_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1',  # Only version
    'v2': b'v2\x00token',
    'v3': b'v3\x00token\x008090',
    'v4': b'v4\x00token\x008090\x0055',
    'v5': b'v5\x00token\x008090\x0055\x001095',
    'v6': b'v6\x00token\x008090\x0055\x001095\x00TRUE',
    'v7': b'v7\x00token\x008090\x0055\x001095\x00TRUE\x00TRUE',
}


class PhysicalMachinesMultiSerializationTest(UDSTestCase):
    environment: Environment

    def setUp(self) -> None:
        self.environment = Environment.temporary_environment()
        self.environment.storage.save_to_db('ips', pickle.dumps(STORED_IPS))

    def check(self, version: str, instance: 'service_multi.IPMachinesService') -> None:
        # Stored list shuld be empty, as it is threated on a different storage
        # So we ensure it's empty
        self.assertEqual(instance.list_of_hosts.as_list(), [])
        
        self.assertEqual([i.as_identifier() for i in instance.hosts], EDITABLE_STORED_IPS)

        if version == 'v1':
            self.assertEqual(instance.token.as_str(), '')
        if version in ('v2', 'v3', 'v4', 'v5', 'v6', 'v7'):
            self.assertEqual(instance.token.as_str(), 'token')
        if version in ('v3', 'v4', 'v5', 'v6', 'v7'):
            self.assertEqual(instance.port.as_int(), 8090)
        if version in ('v4', 'v5', 'v6', 'v7'):
            self.assertEqual(instance.ignore_minutes_on_failure.as_int(), 55)
        if version in ('v5', 'v6', 'v7'):
            self.assertEqual(instance.max_session_hours.as_int(), 1095)
        if version in ('v6', 'v7'):
            self.assertTrue(instance.lock_on_external_access.as_bool())
        if version in ('v7',):
            self.assertTrue(instance.randomize_host.as_bool())

    def test_unmarshall_all_versions(self) -> None:
        for v in range(1, len(SERIALIZED_DATA) + 1):
            version = f'v{v}'
            uninitialized_provider = provider.PhysicalMachinesProvider(
                environment=Environment.testing_environment()
            )

            instance = service_multi.IPMachinesService(
                environment=self.environment, provider=uninitialized_provider
            )
            instance.unmarshal(SERIALIZED_DATA[version])

            self.check(version, instance)

    def test_marshaling(self) -> None:
        # Unmarshall last version, remarshall and check that is marshalled using new marshalling format
        version = f'v{len(SERIALIZED_DATA)}'
        uninitialized_provider = provider.PhysicalMachinesProvider(environment=self.environment)
        instance = service_multi.IPMachinesService(environment=self.environment, provider=uninitialized_provider)
        instance.unmarshal(SERIALIZED_DATA[version])
        marshalled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshalled_data.startswith(b'v'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = service_multi.IPMachinesService(environment=self.environment, provider=uninitialized_provider)
        instance.unmarshal(marshalled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(version, instance)
