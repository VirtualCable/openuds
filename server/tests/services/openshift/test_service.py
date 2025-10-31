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


class TestOpenshiftService(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    def test_service_data(self) -> None:
        """
        Test service data
        """
        service = fixtures.create_service()

        self.assertEqual(service.template.value, fixtures.SERVICE_VALUES_DICT['template'])
        self.assertEqual(service.basename.value, fixtures.SERVICE_VALUES_DICT['basename'])
        self.assertEqual(service.lenname.value, fixtures.SERVICE_VALUES_DICT['lenname'])
        self.assertEqual(service.publication_timeout.value, fixtures.SERVICE_VALUES_DICT['publication_timeout'])

    def test_service_is_available(self) -> None:
        """
        Test service availability
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service(provider=provider)

            self.assertTrue(service.is_available())
            api.test.assert_called_with()

            # Test with cached data
            api.test.return_value = False
            self.assertTrue(service.is_available())

            # Clear cache and test again
            service.provider().is_available.cache_clear()  # type: ignore
            self.assertFalse(service.is_available())
            api.test.assert_called_with()

    def test_service_methods(self) -> None:
        """
        Test service methods
        """
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service(provider=provider)

            # Test basename and lenname
            self.assertEqual(service.get_basename(), 'base')
            self.assertEqual(service.get_lenname(), 4)

            # Test sanitized name
            sanitized = service.sanitized_name('Test VM 1')
            self.assertEqual(sanitized, 'test-vm-1')

            # Test find duplicates
            duplicates = list(service.find_duplicates('vm-1', '00:11:22:33:44:55'))
            self.assertEqual(len(duplicates), 1)

    def test_vm_operations(self) -> None:
        """
        Test VM operations
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service(provider=provider)

            # Test get IP
            ip = service.get_ip(None, 'vm-1')
            self.assertEqual(ip, '192.168.1.1')

            # Test get MAC
            mac = service.get_mac(None, 'vm-1')
            self.assertEqual(mac, '00:11:22:33:44:01')

            # Test is running
            is_running = service.is_running(None, 'vm-1')
            self.assertTrue(is_running)

            # Test start/stop/shutdown
            service.start(None, 'vm-1')
            api.start_vm_instance.assert_called_with('vm-1')

            service.stop(None, 'vm-1')
            api.stop_vm_instance.assert_called_with('vm-1')

            service.shutdown(None, 'vm-1')
            api.stop_vm_instance.assert_called_with('vm-1')

    def test_vm_deletion(self) -> None:
        """
        Test VM deletion
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service(provider=provider)

            # Test execute delete
            service.execute_delete('vm-1')
            api.delete_vm_instance.assert_called_with('vm-1')

            # Test is deleted
            api.get_vm_info.return_value = None
            self.assertTrue(service.is_deleted('vm-1'))

            api.get_vm_info.return_value = fixtures.VMS[0]
            self.assertFalse(service.is_deleted('vm-1'))