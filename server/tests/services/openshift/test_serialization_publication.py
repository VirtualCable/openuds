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
# CAUSED AND ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import pickle

from tests.services.openshift import fixtures

from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftPublicationSerialization(UDSTransactionTestCase):
    EXPECTED_FIELDS = {'_name', '_waiting_name', '_reason', '_queue', '_vmid', '_is_flagged_for_destroy'}

    def setUp(self) -> None:
        """
        Set up test environment and clear fixtures before each test.
        """
        super().setUp()
        fixtures.clear()
        
    def _make_publication(self):
        """
        Helper to create a publication with all fields set for serialization tests.
        """
        publication = fixtures.create_publication()
        publication._name = 'test-template'
        publication._reason = 'test-reason'
        publication._waiting_name = True
        return publication

    # --- Field Check Helper ---
    def check_fields(self, instance: 'fixtures.publication.OpenshiftTemplatePublication') -> None:
        """
        Helper to check expected field values in a publication instance.
        """
        self.assertEqual(instance._name, 'test-template')
        self.assertEqual(instance._reason, 'test-reason')
        self.assertTrue(instance._waiting_name)

    # --- Serialization Tests ---
    def test_autoserialization_fields(self) -> None:
        """
        Test that autoserializable fields match the expected set.
        """
        publication = fixtures.create_publication()
        fields = set(f[0] for f in publication._autoserializable_fields())
        self.assertSetEqual(fields, self.EXPECTED_FIELDS)

    def test_pickle_serialization(self) -> None:
        """
        Test that publication object is correctly serialized and deserialized using pickle.
        """
        publication = self._make_publication()
        data = pickle.dumps(publication)
        publication2 = pickle.loads(data)
        self.check_fields(publication2)

    def test_marshal_unmarshal(self) -> None:
        """
        Test that publication object is correctly marshaled and unmarshaled.
        """
        publication = self._make_publication()
        marshaled = publication.marshal()
        publication2 = fixtures.create_publication()
        publication2.unmarshal(marshaled)
        self.check_fields(publication2)

    def test_methods_after_serialization(self) -> None:
        """
        Test that publication methods return correct values after serialization and deserialization.
        """
        publication = self._make_publication()
        data = pickle.dumps(publication)
        publication2 = pickle.loads(data)
        self.assertEqual(publication2._name, 'test-template')
        self.assertEqual(publication2.get_template_id(), 'test-template')