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
import pickle
import typing

from uds.core.environment import Environment
from uds.core import types as core_types

# We use storage, so we need transactional tests
from tests.utils.test import UDSTransactionTestCase


from uds.services.OpenStack import deployment as deployment

# if data.startswith(b'v'):
#     return super().unmarshal(data)

# vals = data.split(b'\1')
# if vals[0] == b'v1':
#     self._name = vals[1].decode('utf8')
#     self._ip = vals[2].decode('utf8')
#     self._mac = vals[3].decode('utf8')
#     self._vmid = vals[4].decode('utf8')
#     self._reason = vals[5].decode('utf8')
#     self._queue = pickle.loads(vals[6])  # nosec: not insecure, we are loading our own data
EXPECTED_OWN_FIELDS: typing.Final[set[str]] = {
    '_name',
    '_ip',
    '_mac',
    '_vmid',
    '_reason',
    '_queue',
}

OLD_TEST_QUEUE: typing.Final[list[deployment.OldOperation]] = [
    deployment.OldOperation.CREATE,
    deployment.OldOperation.REMOVE,
    deployment.OldOperation.RETRY,
]

TEST_QUEUE = [i.to_operation() for i in OLD_TEST_QUEUE]

SERIALIZED_DEPLOYMENT_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\x01name\x01ip\x01mac\x01vmid\x01reason\x01' + pickle.dumps(OLD_TEST_QUEUE, protocol=0),
}

LAST_VERSION: typing.Final[str] = sorted(SERIALIZED_DEPLOYMENT_DATA.keys(), reverse=True)[0]


class OpenStackDeploymentSerializationTest(UDSTransactionTestCase):
    def check(self, version: str, instance: deployment.OpenStackLiveUserService) -> None:
        self.assertEqual(instance._name, 'name')
        self.assertEqual(instance._ip, 'ip')
        self.assertEqual(instance._mac, 'mac')
        self.assertEqual(instance._vmid, 'vmid')
        self.assertEqual(instance._reason, 'reason')
        self.assertEqual(instance._queue, TEST_QUEUE)

    def test_marshaling(self) -> None:
        # queue is kept on "storage", so we need always same environment
        environment = Environment.testing_environment()

        def _create_instance(unmarshal_data: 'bytes|None' = None) -> deployment.OpenStackLiveUserService:
            instance = deployment.OpenStackLiveUserService(environment=environment, service=None)  # type: ignore
            if unmarshal_data:
                instance.unmarshal(unmarshal_data)
            return instance

        for v in range(1, len(SERIALIZED_DEPLOYMENT_DATA) + 1):
            version = f'v{v}'
            instance = _create_instance(SERIALIZED_DEPLOYMENT_DATA[version])
            self.check(version, instance)
            # Ensure remarshalled flag is set
            self.assertTrue(instance.needs_upgrade())
            instance.mark_for_upgrade(False)  # reset flag

            marshaled_data = instance.marshal()
            self.assertFalse(
                marshaled_data.startswith(b'\v')
            )  # Ensure fields has been marshalled using new format

            instance = _create_instance(marshaled_data)
            self.assertFalse(
                instance.needs_upgrade()
            )  # Reunmarshall again and check that remarshalled flag is not set
            self.check(version, instance)

    def test_marshaling_queue(self) -> None:
        # queue is kept on "storage", so we need always same environment
        environment = Environment.testing_environment()

        def _create_instance(unmarshal_data: 'bytes|None' = None) -> deployment.OpenStackLiveUserService:
            instance = deployment.OpenStackLiveUserService(environment=environment, service=None)  # type: ignore
            if unmarshal_data:
                instance.unmarshal(unmarshal_data)
            return instance

        instance = _create_instance(SERIALIZED_DEPLOYMENT_DATA[LAST_VERSION])
        self.assertEqual(instance._queue, TEST_QUEUE)  # Always unmarshalled as new format

        instance._queue = [
            core_types.services.Operation.CREATE,
            core_types.services.Operation.FINISH,
        ]
        marshaled_data = instance.marshal()

        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [core_types.services.Operation.CREATE, core_types.services.Operation.FINISH],
        )
        # Append something remarshall and check
        instance._queue.insert(0, core_types.services.Operation.RETRY)
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [
                core_types.services.Operation.RETRY,
                core_types.services.Operation.CREATE,
                core_types.services.Operation.FINISH,
            ],
        )
        # Remove something remarshall and check
        instance._queue.pop(0)
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [core_types.services.Operation.CREATE, core_types.services.Operation.FINISH],
        )

    def test_autoserialization_fields(self) -> None:
        # This test is designed to ensure that all fields are autoserializable
        # If some field is added or removed, this tests will warn us about it to fix the rest of the related tests
        with Environment.temporary_environment() as env:
            instance = deployment.OpenStackLiveUserService(environment=env, service=None)  # type: ignore

            self.assertTrue(
                EXPECTED_OWN_FIELDS <= set(f[0] for f in instance._autoserializable_fields()),
                'Missing fields: '
                + str(EXPECTED_OWN_FIELDS - set(f[0] for f in instance._autoserializable_fields())),
            )
