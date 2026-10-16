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
# from unittest import mock


from . import fixtures
from ... import utils
from ...utils.test import UDSTestCase


class TestProxmovLinkedService(UDSTestCase):

    def test_service_linked_data(self) -> None:
        """
        Test the linked service data is loaded correctly from fixture
        """
        service = fixtures.create_linked_service()
        utils.check_userinterface_values(service, fixtures.SERVICE_VALUES_DICT)
        
        self.assertEqual(service.get_macs_range(), service.provider().get_macs_range())
        self.assertEqual(service.get_basename(), service.basename.value)
        self.assertEqual(service.get_lenname(), service.lenname.value)
        self.assertEqual(service.get_display(), service.display.value)

    def test_service_is_available(self) -> None:
        """
        Test the provider
        """
        with fixtures.patch_provider_api() as api:
            service = fixtures.create_linked_service()

            self.assertTrue(service.is_avaliable())
            api.test.assert_called_with()
            # With data cached, even if test fails, it will return True
            api.test.return_value = False
            self.assertTrue(service.is_avaliable())

            # Data is cached, so we need to reset it
            api.test.reset_mock()
            service.provider().is_available.cache_clear()  # type: ignore
            # Now should return False as we have reset the cache
            self.assertFalse(service.is_avaliable())
            api.test.assert_called_with()

    def test_verify_free_storage(self) -> None:
        with fixtures.patch_provider_api() as _api:
            service = fixtures.create_linked_service()

            storage = utils.search_item_by_attr(fixtures.STORAGES_INFO, 'id', service.datastore.value)
            # Ensure available is greater that configured on service
            old_available = storage.available  # For future tests to restore it
            try:
                storage.available = (service.reserved_storage_gb.value + 1) * 1024 * 1024 * 1024
                # Must not raise
                service.verify_free_storage()
                # Now, we will make it fail
                storage.available = (service.reserved_storage_gb.value - 1) * 1024 * 1024 * 1024
                with self.assertRaises(Exception):
                    service.verify_free_storage()
            finally:
                storage.available = old_available

    def test_sanitized_name(self) -> None:
        service = fixtures.create_linked_service()
        # Ensure that any char not in [^a-zA-Z0-9_-] is translated to an underscore (_)
        # Create a with all ascii chars + a lot utf-8 chars outside ascii
        name = 'This is a simple test 0123456789 ñoño'
        name += f'áéíóúñüE¢¢←↑→↓'
        self.assertEqual(service.sanitized_name(name), 'This_is_a_simple_test_0123456789__o_o_______E______')

    def test_make_template(self) -> None:
        with fixtures.patch_provider_api() as api:
            service = fixtures.create_linked_service()
            # Ensure that the template is created
            service.make_template(name='test', comments='test comments')
            api.create_template.assert_called_with(
                'test',
                'test comments',
                service.machine.value,
                service.cluster.value,
                service.datastore.value,
                service.display.value,
            )

    def test_deploy_from_template(self) -> None:
        with fixtures.patch_provider_api() as api:
            service = fixtures.create_linked_service()
            # Ensure that the template is deployed
            service.deploy_from_template('test', 'test comments', fixtures.TEMPLATES_INFO[0].id)
            api.deploy_from_template.assert_called_with(
                'test',
                'test comments',
                fixtures.TEMPLATES_INFO[0].id,
                service.cluster.value,
                service.display.value,
                service.usb.value,
                service.memory.value,
                service.guaranteed_memory.value,
            )

    def test_fix_usb(self) -> None:
        with fixtures.patch_provider_api() as api:
            service = fixtures.create_linked_service()
            # first, with native, should call fix_usb
            service.usb.value = 'native'
            service.fix_usb(service.machine.value)
            api.fix_usb.assert_called_with(service.machine.value)
            # Now, with "disabled" should not call fix_usb
            api.fix_usb.reset_mock()
            service.usb.value = 'disabled'
            service.fix_usb(fixtures.VMS_INFO[0].id)
            api.fix_usb.assert_not_called()

    def test_get_console_connection(self) -> None:
        with fixtures.patch_provider_api() as api:
            service = fixtures.create_linked_service()
            # Ensure that the console connection is retrieved
            service.get_console_connection(service.machine.value)
            api.get_console_connection_info.assert_called_with(service.machine.value)