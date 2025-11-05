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
from tests.services.openshift import fixtures
from tests.utils.test import UDSTransactionTestCase
from uds.services.OpenShift.provider import OpenshiftProvider

PROVIDER_SERIALIZE_DATA = (
    '{'
    '"cluster_url": "https://oauth-openshift.apps-crc.testing", '
    '"api_url": "https://api.crc.testing:6443", '
    '"username": "kubeadmin", '
    '"password": "test-password", '
    '"namespace": "default", '
    '"verify_ssl": false, '
    '"concurrent_creation_limit": 1, '
    '"concurrent_removal_limit": 1, '
    '"timeout": 10'
    '}'
)

class TestOpenshiftProviderSerialization(UDSTransactionTestCase):
    # --- Serialization Tests ---
    def test_provider_methods_after_serialization(self) -> None:
        """
        Test that provider methods return correct values after serialization and deserialization.
        """
        from uds.core import environment

        provider = fixtures.create_provider()
        data = provider.serialize()

        provider2 = OpenshiftProvider(environment=environment.Environment.testing_environment())
        provider2.deserialize(data)

        self.assertEqual(str(provider2.type_name), 'Openshift Provider')
        self.assertEqual(str(provider2.type_description), 'Openshift based VMs provider')
        self.assertEqual(provider2.cluster_url.value, fixtures.PROVIDER_VALUES_DICT['cluster_url'])
        self.assertEqual(provider2.api_url.value, fixtures.PROVIDER_VALUES_DICT['api_url'])

    def test_provider_serialization(self) -> None:
        """
        Test that all provider fields are correctly serialized and deserialized.
        """
        from uds.core import environment

        provider = fixtures.create_provider()
        data = provider.serialize()  

        provider2 = OpenshiftProvider(environment=environment.Environment.testing_environment())
        provider2.deserialize(data)

        for field in fixtures.PROVIDER_VALUES_DICT:
            self.assertEqual(getattr(provider2, field).value, fixtures.PROVIDER_VALUES_DICT[field])
