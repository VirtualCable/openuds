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

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core.environment import Environment


from uds.services.OpenGnsys import publication
EXPECTED_FIELDS: typing.Final[set[str]] = set()

SERIALIZED_PUBLICATION_DATA: typing.Final[bytes] = b''


class OpenGnsysPublicationSerializationTest(UDSTestCase):
    def check(self, instance: publication.OpenGnsysPublication) -> None:
        # No data currently, all is fine
        pass

    def test_marshaling(self) -> None:
        environment = Environment.testing_environment()

        instance = publication.OpenGnsysPublication(environment=environment, service=None)  # type: ignore
        #instance.unmarshal(SERIALIZED_PUBLICATION_DATA)
        self.check(instance)
        # Ensure remarshalled flag is set
        #self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        marshaled_data = instance.marshal()

        # Ensure fields has been marshalled using new format
        self.assertFalse(marshaled_data.startswith(b'\1'))
        # Reunmarshall again and check that remarshalled flag is not set
        instance = publication.OpenGnsysPublication(environment=environment, service=None)  # type: ignore
        #instance.unmarshal(marshaled_data)
        #self.assertFalse(instance.needs_upgrade())

        # Check that data is correct
        self.check(instance)

    def test_autoserialization_fields(self) -> None:
        # This test is designed to ensure that all fields are autoserializable
        # If some field is added or removed, this tests will warn us about it to fix the rest of the related tests
        with Environment.temporary_environment() as env:
            instance = publication.OpenGnsysPublication(environment=env, service=None)  # type: ignore

            instance_fields = set(f[0] for f in instance._autoserializable_fields())
            self.assertSetEqual(instance_fields, EXPECTED_FIELDS)
