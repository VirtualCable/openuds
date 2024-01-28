# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
# All rights reserved.
#

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import pickle
import typing

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core.util import auto_serializable
from uds.core.environment import Environment


from uds.services.Xen import deployment

# if not data.startswith(b'v'):
#     return super().unmarshal(data)

# vals = data.split(b'\1')
# logger.debug('Values: %s', vals)
# if vals[0] == b'v1':
#     self._name = vals[1].decode('utf8')
#     self._ip = vals[2].decode('utf8')
#     self._mac = vals[3].decode('utf8')
#     self._vmid = vals[4].decode('utf8')
#     self._reason = vals[5].decode('utf8')
#     self._queue = pickle.loads(vals[6])  # nosec: not insecure, we are loading our own data
#     self._task = vals[7].decode('utf8')

# self.flag_for_upgrade()  # Force upgrade

TEST_QUEUE: typing.Final[list[deployment.Operation]] = [
    deployment.Operation.START,
    deployment.Operation.STOP,
    deployment.Operation.REMOVE,
]

SERIALIZED_LINKED_DEPLOYMENT_DATA: typing.Final[typing.Mapping[str, bytes]] = {
    'v1': b'v1\x01name\x01ip\x01mac\x01vmid\x01reason\x01' + pickle.dumps(TEST_QUEUE) + b'\x01task',
}


class XendDeploymentSerializationTest(UDSTestCase):
    def check(self, version: str, instance: deployment.XenLinkedDeployment) -> None:
        self.assertEqual(instance._name, 'name')
        self.assertEqual(instance._ip, 'ip')
        self.assertEqual(instance._mac, 'mac')
        self.assertEqual(instance._vmid, 'vmid')
        self.assertEqual(instance._reason, 'reason')
        self.assertEqual(instance._queue, TEST_QUEUE)
        self.assertEqual(instance._task, 'task')

    def test_unmarshall_all_versions(self) -> None:
        for v in range(1, len(SERIALIZED_LINKED_DEPLOYMENT_DATA) + 1):
            version = f'v{v}'
            instance = deployment.XenLinkedDeployment(
                environment=Environment.get_temporary_environment(), service=None
            )
            instance.unmarshal(SERIALIZED_LINKED_DEPLOYMENT_DATA[version])

            self.assertTrue(instance.needs_upgrade())

            self.check(version, instance)

    def test_marshaling(self):
        VERSION = f'v{len(SERIALIZED_LINKED_DEPLOYMENT_DATA)}'

        instance = deployment.XenLinkedDeployment(
            environment=Environment.get_temporary_environment(), service=None
        )
        instance.unmarshal(SERIALIZED_LINKED_DEPLOYMENT_DATA[VERSION])
        marshaled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.flag_for_upgrade(False)  # reset flag

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'v'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = deployment.XenLinkedDeployment(
            environment=Environment.get_temporary_environment(), service=None
        )
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(VERSION, instance)

    def test_marshaling_queue(self) -> None:
        def _create_instance(unmarshal_data: 'bytes|None' = None) -> deployment.XenLinkedDeployment:
            instance = deployment.XenLinkedDeployment(
                environment=Environment.get_temporary_environment(), service=None
            )
            if unmarshal_data:
                instance.unmarshal(unmarshal_data)
            return instance

        instance = _create_instance()

        instance._queue = [deployment.Operation.CREATE, deployment.Operation.REMOVE]
        marshaled_data = instance.marshal()

        instance = _create_instance(marshaled_data)
        self.assertEqual(instance._queue, [deployment.Operation.CREATE, deployment.Operation.REMOVE])
        # Append something remarshall and check
        instance._queue.append(deployment.Operation.START)
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(
            instance._queue, [deployment.Operation.CREATE, deployment.Operation.REMOVE, deployment.Operation.START]
        )
        # Remove something remarshall and check
        instance._queue.pop(0)
        marshaled_data = instance.marshal()
        instance = _create_instance(marshaled_data)
        self.assertEqual(instance._queue, [deployment.Operation.REMOVE, deployment.Operation.START])
        