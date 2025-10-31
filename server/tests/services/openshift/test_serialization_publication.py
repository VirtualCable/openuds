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
    def setUp(self) -> None:
        fixtures.clear()

    def test_publication_serialization(self) -> None:
        """
        Test publication serialization
        """
        publication = fixtures.create_publication()
        publication._name = 'test-template'
        publication._reason = 'test-reason'
        publication._waiting_name = True

        # Serialize and deserialize
        data = pickle.dumps(publication)
        publication2 = pickle.loads(data)

        self.assertEqual(publication2._name, 'test-template')
        self.assertEqual(publication2._reason, 'test-reason')
        self.assertEqual(publication2._waiting_name, True)

    def test_publication_methods_after_serialization(self) -> None:
        """
        Test publication methods after serialization
        """
        publication = fixtures.create_publication()
        publication._name = 'test-template'

        # Serialize and deserialize
        data = pickle.dumps(publication)
        publication2 = pickle.loads(data)

        # Test methods after serialization
        self.assertEqual(publication2.get_name(), 'test-template')
        self.assertEqual(publication2.get_template_id(), 'test-template')