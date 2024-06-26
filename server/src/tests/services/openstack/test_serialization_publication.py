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

from uds.core.environment import Environment
from uds.core import types as core_types
from uds.services.OpenStack import publication

from tests.utils.test import UDSTestCase

# We use commit/rollback


# if not data.startswith(b'v'):
#     return super().unmarshal(data)

# vals = data.decode('utf8').split('\t')
# if vals[0] == 'v1':
#     (self._name, self._reason, self._template_id, self._status, destroy_after) = vals[1:]
# else:
#     raise Exception('Invalid data')

# self._destroy_after = destroy_after == 'y'
EXPECTED_OWN_FIELDS: typing.Final[set[str]] = {
    '_name',
    '_reason',
    '_vmid',
    '_queue',
    '_is_flagged_for_destroy',
}


SERIALIZED_PUBLICATION_DATA: typing.Final[bytes] = b'v1\tname\treason\ttemplate_id\tstate\ty'


class OpenStackPublicationSerializationTest(UDSTestCase):
    def check(self, instance: publication.OpenStackLivePublication) -> None:
        self.assertEqual(instance._name, 'name')
        self.assertEqual(instance._reason, 'reason')
        self.assertEqual(instance._vmid, 'template_id')
        self.assertEqual(instance._queue, [core_types.services.Operation.CREATE, core_types.services.Operation.FINISH])
        self.assertTrue(instance._is_flagged_for_destroy)

    def test_marshaling(self) -> None:
        environment = Environment.testing_environment()

        instance = publication.OpenStackLivePublication(environment=environment, service=None)  # type: ignore
        instance.unmarshal(SERIALIZED_PUBLICATION_DATA)
        self.check(instance)
        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        marshaled_data = instance.marshal()

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'\1'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = publication.OpenStackLivePublication(environment=environment, service=None)  # type: ignore
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(instance)

    def test_autoserialization_fields(self) -> None:
        # This test is designed to ensure that all fields are autoserializable
        # If some field is added or removed, this tests will warn us about it to fix the rest of the related tests
        with Environment.temporary_environment() as env:
            instance = publication.OpenStackLivePublication(environment=env, service=None)  # type: ignore

            self.assertTrue(
                EXPECTED_OWN_FIELDS <= set(f[0] for f in instance._autoserializable_fields()),
                'Missing fields: '
                + str(EXPECTED_OWN_FIELDS - set(f[0] for f in instance._autoserializable_fields())),
            )
