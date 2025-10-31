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
from unittest import mock

from uds.core import types, ui, environment
from uds.services.OpenShift.provider import OpenshiftProvider

from . import fixtures

from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftProvider(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    def test_provider_data(self) -> None:
        """
        Test the provider data
        """
        provider = fixtures.create_provider()

        self.assertEqual(provider.cluster_url.value, fixtures.PROVIDER_VALUES_DICT['cluster_url'])
        self.assertEqual(provider.api_url.value, fixtures.PROVIDER_VALUES_DICT['api_url'])
        self.assertEqual(provider.username.value, fixtures.PROVIDER_VALUES_DICT['username'])
        self.assertEqual(provider.password.value, fixtures.PROVIDER_VALUES_DICT['password'])
        self.assertEqual(provider.namespace.value, fixtures.PROVIDER_VALUES_DICT['namespace'])
        self.assertEqual(provider.verify_ssl.value, fixtures.PROVIDER_VALUES_DICT['verify_ssl'])

        if not isinstance(provider.concurrent_creation_limit, ui.gui.NumericField):
            self.fail('concurrent_creation_limit is not a NumericField')

        self.assertEqual(
            provider.concurrent_creation_limit.as_int(),
            fixtures.PROVIDER_VALUES_DICT['concurrent_creation_limit'],
        )
        
        if not isinstance(provider.concurrent_removal_limit, ui.gui.NumericField):
            self.fail('concurrent_removal_limit is not a NumericField')

        self.assertEqual(
            provider.concurrent_removal_limit.as_int(),
            fixtures.PROVIDER_VALUES_DICT['concurrent_removal_limit'],
        )
        
        self.assertEqual(provider.timeout.as_int(), fixtures.PROVIDER_VALUES_DICT['timeout'])

    def test_provider_test(self) -> None:
        """
        Test the provider test method
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            
            for ret_val in [True, False]:
                api.test.reset_mock()
                api.test.return_value = ret_val
                
                result = OpenshiftProvider.test(
                    environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
                )
                
                self.assertIsInstance(result, types.core.TestResult)
                self.assertEqual(result.success, ret_val)
                self.assertIsInstance(result.error, str)

    def test_provider_is_available(self) -> None:
        """
        Test the provider is_available method
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)

            # First, true result
            self.assertEqual(provider.is_available(), True)
            api.test.assert_called_once_with()
            api.test.reset_mock()

            # Now, even if set test to false, should return true due to cache
            api.test.return_value = False
            self.assertEqual(provider.is_available(), True)
            api.test.assert_not_called()

            # clear cache of method
            provider.is_available.cache_clear()  # type: ignore
            self.assertEqual(provider.is_available(), False)
            api.test.assert_called_once_with()

    def test_provider_api_methods(self) -> None:
        """
        Test provider API methods
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)

            self.assertEqual(provider.test_connection(), True)
            api.test.assert_called_once_with()

            self.assertEqual(provider.api.list_vms(), fixtures.VMS)
            self.assertEqual(provider.api.get_vm_info('vm-1'), fixtures.VMS[0])
            self.assertEqual(provider.api.get_vm_instance_info('vm-1'), fixtures.VM_INSTANCES[0])

            self.assertTrue(provider.api.start_vm_instance('vm-1'))
            self.assertTrue(provider.api.stop_vm_instance('vm-1'))
            self.assertTrue(provider.api.delete_vm_instance('vm-1'))

    def test_sanitized_name(self) -> None:
        """
        Test name sanitization
        """
        provider = fixtures.create_provider()
        
        test_cases = [
            ('Test-VM-1', 'test-vm-1'),
            ('Test_VM@2', 'test-vm-2'),
            ('My Test VM!!!', 'my-test-vm'),
            ('a' * 100, 'a' * 63),  # Test truncation
        ]
        
        for input_name, expected in test_cases:
            self.assertEqual(provider.sanitized_name(input_name), expected)