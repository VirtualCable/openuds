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

from tests.services.openshift import fixtures

from tests.utils.test import UDSTransactionTestCase



class TestOpenshiftServiceFixed(UDSTransactionTestCase):
    def _create_service_fixed_with_provider(self):
        """
        Helper to create a fixed service with a patched provider.
        """
        provider_ctx = fixtures.patched_provider()
        provider = provider_ctx.__enter__()
        service = fixtures.create_service_fixed(provider=provider)
        return service, provider, provider_ctx
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    # --- Availability ---
    def test_service_is_available(self) -> None:
        """
        Test provider availability and cache logic.
        """
        service, provider, provider_ctx = self._create_service_fixed_with_provider()
        api = typing.cast(mock.MagicMock, provider.api)
        self.assertTrue(service.is_available())
        api.test.assert_called_with()
        # With cached data, even if test fails, it will return True
        api.test.return_value = False
        self.assertTrue(service.is_available())
        # Clear cache and test again
        service.provider().is_available.cache_clear()  # type: ignore
        self.assertFalse(service.is_available())
        api.test.assert_called_with()
        provider_ctx.__exit__(None, None, None)

    # --- Service methods ---
    def test_service_methods(self) -> None:
        """
        Test service methods: enumerate_assignables, get_name, get_ip, get_mac, sanitized_name.
        """
        service, _, provider_ctx = self._create_service_fixed_with_provider()
        # Enumerate assignables
        machines = list(service.enumerate_assignables())
        self.assertEqual(len(machines), 3)
        self.assertEqual(machines[0].id, 'vm-3')
        self.assertEqual(machines[1].id, 'vm-4')
        self.assertEqual(machines[2].id, 'vm-5')
        # Get machine name
        machine_name = service.get_name('uid-3')
        self.assertEqual(machine_name, 'vm-3')
        # Get IP
        ip = service.get_ip('uid-3')
        self.assertTrue(ip.startswith('192.168.1.'))
        # Get MAC
        mac = service.get_mac('uid-3')
        self.assertTrue(mac.startswith('00:11:22:33:44:'))
        # Sanitized name
        sanitized = service.sanitized_name('Test VM 1')
        self.assertIsInstance(sanitized, str)
        provider_ctx.__exit__(None, None, None)

    # --- Assignment logic ---
    def test_get_and_assign(self) -> None:
        """
        Test get_and_assign logic for fixed service.
        """
        service, _, provider_ctx = self._create_service_fixed_with_provider()
        vmid = service.get_and_assign()
        self.assertIn(vmid, ['vm-3', 'vm-4', 'vm-5'])
        # Should not assign the same again
        with service._assigned_access() as assigned:
            self.assertIn(vmid, assigned)
        provider_ctx.__exit__(None, None, None)

    def test_remove_and_free(self) -> None:
        """
        Test remove_and_free logic for fixed service.
        """
        service, _, provider_ctx = self._create_service_fixed_with_provider()
        vmid = service.get_and_assign()
        result = service.remove_and_free(vmid)
        self.assertEqual(result.name, 'FINISHED')
        with service._assigned_access() as assigned:
            self.assertNotIn(vmid, assigned)
        provider_ctx.__exit__(None, None, None)
