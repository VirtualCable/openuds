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


class TestOpenshiftProviderSerialization(UDSTransactionTestCase):
    def test_provider_serialization(self) -> None:
        """
        Test provider serialization
        """
        provider = fixtures.create_provider()

        # Serialize and deserialize
        data = pickle.dumps(provider)
        provider2 = pickle.loads(data)

        self.assertEqual(provider2.cluster_url.value, fixtures.PROVIDER_VALUES_DICT['cluster_url'])
        self.assertEqual(provider2.api_url.value, fixtures.PROVIDER_VALUES_DICT['api_url'])
        self.assertEqual(provider2.username.value, fixtures.PROVIDER_VALUES_DICT['username'])
        self.assertEqual(provider2.password.value, fixtures.PROVIDER_VALUES_DICT['password'])
        self.assertEqual(provider2.namespace.value, fixtures.PROVIDER_VALUES_DICT['namespace'])
        self.assertEqual(provider2.verify_ssl.value, fixtures.PROVIDER_VALUES_DICT['verify_ssl'])

    def test_provider_methods_after_serialization(self) -> None:
        """
        Test provider methods after serialization
        """
        provider = fixtures.create_provider()

        # Serialize and deserialize
        data = pickle.dumps(provider)
        provider2 = pickle.loads(data)

        # Test methods after serialization
        self.assertEqual(provider2.get_name(), 'Openshift Provider')
        self.assertEqual(provider2.get_description(), 'Openshift Provider')
        self.assertEqual(provider2.get_cluster_url(), 'https://oauth-openshift.apps-crc.testing')
        self.assertEqual(provider2.get_api_url(), 'https://api.crc.testing:6443')