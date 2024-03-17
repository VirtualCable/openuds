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

from uds.core import types, ui, environment
from uds.services.OVirt.provider import OVirtProvider

from . import fixtures

from ...utils.test import UDSTransactionTestCase


class TestOVirtProvider(UDSTransactionTestCase):
    def test_provider_data(self) -> None:
        """
        Test the provider
        """
        provider = fixtures.create_provider()  # Will not use client api, so no need to patch it

        self.assertEqual(provider.ovirt_version.as_str(), fixtures.PROVIDER_VALUES_DICT['ovirt_version'])
        self.assertEqual(provider.host.as_str(), fixtures.PROVIDER_VALUES_DICT['host'])
        self.assertEqual(provider.port.as_int(), fixtures.PROVIDER_VALUES_DICT['port'])
        self.assertEqual(provider.username.as_str(), fixtures.PROVIDER_VALUES_DICT['username'])
        self.assertEqual(provider.password.as_str(), fixtures.PROVIDER_VALUES_DICT['password'])

        if not isinstance(provider.concurrent_creation_limit, ui.gui.NumericField):
            self.fail('concurrent_creation_limit is not a NumericField')

        self.assertEqual(
            provider.concurrent_creation_limit.as_int(),
            fixtures.PROVIDER_VALUES_DICT['concurrent_creation_limit'],
        )
        # concurrent_removal_limit
        if not isinstance(provider.concurrent_removal_limit, ui.gui.NumericField):
            self.fail('concurrent_creation_limit is not a NumericField')

        self.assertEqual(
            provider.concurrent_removal_limit.as_int(),
            fixtures.PROVIDER_VALUES_DICT['concurrent_removal_limit'],
        )
        self.assertEqual(provider.timeout.as_int(), fixtures.PROVIDER_VALUES_DICT['timeout'])
        self.assertEqual(provider.macs_range.as_str(), fixtures.PROVIDER_VALUES_DICT['macs_range'])

        self.assertEqual(provider.get_macs_range(), fixtures.PROVIDER_VALUES_DICT['macs_range'])

    def test_provider_test(self) -> None:
        """
        Test the provider
        """
        with fixtures.patch_provider_api() as api:
            # Fist, true result
            result = OVirtProvider.test(
                environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
            )

            # Ensure test is called
            api.test.assert_called_once_with()

            self.assertIsInstance(result, types.core.TestResult)
            self.assertEqual(result.success, True)
            self.assertIsInstance(result.error, str)

            # Now, return false
            api.test.return_value = False
            api.test.reset_mock()

            result = OVirtProvider.test(
                environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
            )

            # Ensure test is called
            api.test.assert_called_once_with()

            self.assertIsInstance(result, types.core.TestResult)
            self.assertEqual(result.success, False)
            self.assertIsInstance(result.error, str)

    def test_provider_is_available(self) -> None:
        """
        Test the provider is_available
        """
        with fixtures.patch_provider_api() as api:
            provider = fixtures.create_provider()

            # Fist, true result
            self.assertEqual(provider.is_available(), True)
            api.test.assert_called_once_with()
            api.test.reset_mock()  # Reset counter

            # Now, even if set test to false, should return true due to cache
            api.test.return_value = False
            self.assertEqual(provider.is_available(), True)
            api.test.assert_not_called()

            # clear cache of method
            provider.is_available.cache_clear()  # type: ignore  # clear_cache is added by decorator
            self.assertEqual(provider.is_available(), False)
            api.test.assert_called_once_with()

    def test_provider_methods_1(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patch_provider_api() as _api:
            _provider = fixtures.create_provider()

            pass