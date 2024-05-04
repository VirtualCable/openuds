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

from uds.core import environment, types
from uds.services.Proxmox.deployment_linked import (
    OldOperation as OldOperation,
    ProxmoxUserserviceLinked as Deployment,
)


# We use storage, so we need transactional tests
from ...utils.test import UDSTransactionTestCase
from ...utils import fake
from . import fixtures


# if not data.startswith(b'v'):
#     return super().unmarshal(data)

# vals = data.split(b'\1')
# if vals[0] == b'v1':
#     self._name = vals[1].decode('utf8')
#     self._ip = vals[2].decode('utf8')
#     self._mac = vals[3].decode('utf8')
#     self._task = vals[4].decode('utf8')
#     self._vmid = vals[5].decode('utf8')
#     self._reason = vals[6].decode('utf8')
#     self._queue = [OldOperation.from_int(i) for i in pickle.loads(vals[7])]  # nosec: controled data

# self.flag_for_upgrade()  # Flag so manager can save it again with new format

# Note that new implementation can hold more fields than ours, so we need to check only the ones we need
EXPECTED_OWN_FIELDS: typing.Final[set[str]] = {
    '_name',
    '_ip',
    '_mac',
    '_task',
    '_vmid',
    '_reason',
    '_queue',
}

# Old queue content and format
TEST_QUEUE: typing.Final[list[OldOperation]] = [
    OldOperation.CREATE,
    OldOperation.REMOVE,
    OldOperation.RETRY,
]

TEST_QUEUE_NEW: typing.Final[list[types.services.Operation]] = [i.to_operation() for i in TEST_QUEUE]

SERIALIZED_DEPLOYMENT_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\x01name\x01ip\x01mac\x01task\x01vmid\x01reason\x01' + pickle.dumps(TEST_QUEUE, protocol=0),
}

LAST_VERSION: typing.Final[str] = sorted(SERIALIZED_DEPLOYMENT_DATA.keys(), reverse=True)[0]


class ProxmoxDeploymentSerializationTest(UDSTransactionTestCase):
    def check(self, version: str, instance: Deployment) -> None:
        self.assertEqual(instance._name, 'name')
        self.assertEqual(instance._ip, 'ip')
        self.assertEqual(instance._mac, 'mac')
        self.assertEqual(instance._task, 'task')
        self.assertEqual(instance._vmid, 'vmid')
        self.assertEqual(instance._reason, 'reason')
        self.assertEqual(instance._queue, TEST_QUEUE_NEW)

    def test_marshaling(self) -> None:
        def _create_instance(unmarshal_data: 'bytes|None' = None) -> Deployment:
            instance = fixtures.create_userservice_linked()
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
        def _create_instance(unmarshal_data: 'bytes|None' = None) -> Deployment:
            instance = fixtures.create_userservice_linked()
            instance.env.storage.save_pickled('queue', TEST_QUEUE)
            if unmarshal_data:
                instance.unmarshal(unmarshal_data)
            return instance

        instance = _create_instance(SERIALIZED_DEPLOYMENT_DATA[LAST_VERSION])
        self.assertEqual(instance._queue, TEST_QUEUE_NEW)

        # Now, access current operation, that will trigger the upgrade
        instance._current_op()

        # And essure quee is as new format should be
        self.assertEqual(instance._queue, TEST_QUEUE_NEW)

        # Marshal and check again
        marshaled_data = instance.marshal()

        # Now, format is new, so we can't check it with old format
        self.assertEqual(marshaled_data.startswith(b'v'), False)

        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            TEST_QUEUE_NEW,
        )

        # Append something remarshall and check
        instance._queue.insert(0, types.services.Operation.RESET)
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue,
            [types.services.Operation.RESET] + TEST_QUEUE_NEW,
        )

    def test_autoserialization_fields(self) -> None:
        # This test is designed to ensure that all fields are autoserializable
        # If some field is added or removed, this tests will warn us about it to fix the rest of the related tests
        with environment.Environment.temporary_environment() as env:
            instance = Deployment(environment=env, service=fake.fake_service())

            self.assertTrue(
                EXPECTED_OWN_FIELDS <= set(f[0] for f in instance._autoserializable_fields()),
                'Missing fields: '
                + str(EXPECTED_OWN_FIELDS - set(f[0] for f in instance._autoserializable_fields())),
            )
