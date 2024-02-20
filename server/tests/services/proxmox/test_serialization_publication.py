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

from tests.utils.test import UDSTestCase
from uds.core.environment import Environment
from uds.core.util import autoserializable

from uds.services.Proxmox.publication import ProxmoxPublication as Publication


# if not data.startswith(b'v'):
#     return super().unmarshal(data)

# logger.debug('Data: %s', data)
# vals = data.decode('utf8').split('\t')
# if vals[0] == 'v1':
#     (
#         self._name,
#         self._vm,
#         self._task,
#         self._state,
#         self._operation,
#         destroy_after,
#         self._reason,
#     ) = vals[1:]
# else:
#     raise ValueError('Invalid data format')
    
# self._destroy_after = destroy_after != ''
EXPECTED_FIELDS: typing.Final[set[str]] = {
    '_name',
    '_vm',
    '_task',
    '_state',
    '_operation',
    '_destroy_after',
    '_reason',
}


SERIALIZED_PUBLICATION_DATA: typing.Final[bytes] = b'v1\tname\tvm\ttask\tstate\toperation\ty\treason'


class ProxmoxPublicationSerializationTest(UDSTestCase):
    def check(self, instance: Publication) -> None:
        self.assertEqual(instance._name, 'name')
        self.assertEqual(instance._vmid, 'vm')
        self.assertEqual(instance._task, 'task')
        self.assertEqual(instance._state, 'state')
        self.assertEqual(instance._operation, 'operation')
        self.assertTrue(instance._destroy_after)
        self.assertEqual(instance._reason, 'reason')

    def test_marshaling(self) -> None:
        environment = Environment.testing_environment()

        instance = Publication(environment=environment, service=None)
        instance.unmarshal(SERIALIZED_PUBLICATION_DATA)
        self.check(instance)
        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        marshaled_data = instance.marshal()

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'\1'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = Publication(environment=environment, service=None)
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(instance)

    def test_autoserialization_fields(self) -> None:
        # This test is designed to ensure that all fields are autoserializable
        # If some field is added or removed, this tests will warn us about it to fix the rest of the related tests
        with Environment.temporary_environment() as env:
            instance = Publication(environment=env, service=None)
            self.assertSetEqual(set(f[0] for f in instance._autoserializable_fields()), EXPECTED_FIELDS)
