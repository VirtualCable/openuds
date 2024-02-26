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

# We use storage, so we need transactional tests
from tests.utils.test import UDSTransactionTestCase
from uds.core.util import autoserializable
from uds.core.environment import Environment


from uds.services.OpenGnsys import deployment as deployment

# if not data.startswith(b'v'):
#     return super().unmarshal(data)

# vals = data.split(b'\1')
# if vals[0] == b'v1':
#     self._name = vals[1].decode('utf8')
#     self._ip = vals[2].decode('utf8')
#     self._mac = vals[3].decode('utf8')
#     self._machineId = vals[4].decode('utf8')
#     self._reason = vals[5].decode('utf8')
#     self._stamp = int(vals[6].decode('utf8'))
#     self._queue = pickle.loads(
#         vals[7]
#     )  # nosec: not insecure, we are loading our own data
    
# self.flag_for_upgrade()  # Flag so manager can save it again with new format
EXPECTED_FIELDS: typing.Final[set[str]] = {
    '_name',
    '_ip',
    '_mac',
    '_machine_id',
    '_reason',
    '_stamp',
    '_queue',
}

TEST_QUEUE: typing.Final[list[deployment.Operation]] = [
    deployment.Operation.CREATE,
    deployment.Operation.REMOVE,
    deployment.Operation.RETRY,
]

SERIALIZED_DEPLOYMENT_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\x01name\x01ip\x01mac\x01machine_id\x01reason\x011234567\x01' + pickle.dumps(TEST_QUEUE),
}
LAST_VERSION: typing.Final[str] = sorted(SERIALIZED_DEPLOYMENT_DATA.keys(), reverse=True)[0]

class OpenGnsysDeploymentSerializationTest(UDSTransactionTestCase):
    def check(self, instance: deployment.OpenGnsysUserService) -> None:
        self.assertEqual(instance._name, 'name')
        self.assertEqual(instance._ip, 'ip')
        self.assertEqual(instance._mac, 'mac')
        self.assertEqual(instance._machine_id, 'machine_id')
        self.assertEqual(instance._reason, 'reason')
        self.assertEqual(instance._stamp, 1234567)
        self.assertEqual(instance._queue, TEST_QUEUE)

    def test_marshaling(self) -> None:
        # queue is kept on "storage", so we need always same environment
        environment = Environment.testing_environment()

        def _create_instance(unmarshal_data: 'bytes|None' = None) -> deployment.OpenGnsysUserService:
            instance = deployment.OpenGnsysUserService(environment=environment, service=None)   # type: ignore
            if unmarshal_data:
                instance.unmarshal(unmarshal_data)
            return instance
        
        for v in range(1, len(SERIALIZED_DEPLOYMENT_DATA) + 1):
            version = f'v{v}'
            instance = _create_instance(SERIALIZED_DEPLOYMENT_DATA[version])
            self.check(instance)
            # Ensure remarshalled flag is set
            self.assertTrue(instance.needs_upgrade())
            instance.mark_for_upgrade(False)  # reset flag
            
            marshaled_data = instance.marshal()
            self.assertFalse(marshaled_data.startswith(b'\v'))  # Ensure fields has been marshalled using new format
            
            instance = _create_instance(marshaled_data)
            self.assertFalse(instance.needs_upgrade())  # Reunmarshall again and check that remarshalled flag is not set
            self.check(instance)

    def test_marshaling_queue(self) -> None:
        # queue is kept on "storage", so we need always same environment
        environment = Environment.testing_environment()
        # Store queue
        environment.storage.put_pickle('queue', TEST_QUEUE)

        def _create_instance(unmarshal_data: 'bytes|None' = None) -> deployment.OpenGnsysUserService:
            instance = deployment.OpenGnsysUserService(environment=environment, service=None)  # type: ignore
            if unmarshal_data:
                instance.unmarshal(unmarshal_data)
            return instance

        instance = _create_instance(SERIALIZED_DEPLOYMENT_DATA[LAST_VERSION])
        self.assertEqual(instance._queue, TEST_QUEUE)

        instance._queue = [
            deployment.Operation.CREATE,
            deployment.Operation.FINISH,
        ]
        marshaled_data = instance.marshal()

        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [deployment.Operation.CREATE, deployment.Operation.FINISH],
        )
        # Append something remarshall and check
        instance._queue.insert(0, deployment.Operation.RETRY)
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [
                deployment.Operation.RETRY,
                deployment.Operation.CREATE,
                deployment.Operation.FINISH,
            ],
        )
        # Remove something remarshall and check
        instance._pop_current_op()
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [deployment.Operation.CREATE, deployment.Operation.FINISH],
        )

    def test_autoserialization_fields(self) -> None:
        # This test is designed to ensure that all fields are autoserializable
        # If some field is added or removed, this tests will warn us about it to fix the rest of the related tests
        with Environment.temporary_environment() as env:
            instance = deployment.OpenGnsysUserService(environment=env, service=None)  # type: ignore

            instance_fields = set(f[0] for f in instance._autoserializable_fields())
            self.assertSetEqual(instance_fields, EXPECTED_FIELDS)
