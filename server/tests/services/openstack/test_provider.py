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
from unittest import mock

from uds.core import types, environment

from . import fixtures

from ...utils.test import UDSTransactionTestCase

from uds.services.OpenStack.provider import OpenStackProvider
from uds.services.OpenStack.provider_legacy import OpenStackProviderLegacy


class TestOpenstackProvider(UDSTransactionTestCase):
    def test_provider(self) -> None:
        """
        Test the provider
        """
        with fixtures.patch_provider_api() as client:
            provider = fixtures.create_provider()  # Will not use client api, so no need to patch it

            self.assertEqual(provider.test_connection(), types.core.TestResult(True, mock.ANY))
            # Ensure test_connection is called
            client.test_connection.assert_called_once()
            
            self.assertEqual(provider.is_available(), True)
            client.is_available.assert_called_once()

            # Clear mock calls
            client.reset_mock()
            OpenStackProvider.test(env=environment.Environment.testing_environment(), data=fixtures.PROVIDER_VALUES_DICT)

    def test_provider_legacy(self) -> None:
        """
        Test the provider
        """
        with fixtures.patch_provider_api(legacy=True) as client:
            provider = fixtures.create_provider_legacy()  # Will not use client api, so no need to patch it

            self.assertEqual(provider.test_connection(), types.core.TestResult(True, mock.ANY))
            # Ensure test_connection is called
            client.test_connection.assert_called_once()
            
            self.assertEqual(provider.is_available(), True)
            client.is_available.assert_called_once()

            # Clear mock calls
            client.reset_mock()
            OpenStackProviderLegacy.test(env=environment.Environment.testing_environment(), data=fixtures.PROVIDER_VALUES_DICT)
                        
