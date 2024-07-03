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


from . import fixtures

from ...utils.test import UDSTestCase


class TestProxmovLinkedService(UDSTestCase):
    def test_service_data(self) -> None:
        service = fixtures.create_service_linked()

        self.assertEqual(service.pool.value, fixtures.SERVICE_LINKED_VALUES_DICT['pool'])
        self.assertEqual(service.ha.value, fixtures.SERVICE_LINKED_VALUES_DICT['ha'])
        self.assertEqual(service.try_soft_shutdown.value, fixtures.SERVICE_LINKED_VALUES_DICT['try_soft_shutdown'])
        self.assertEqual(service.machine.as_int(), fixtures.SERVICE_LINKED_VALUES_DICT['machine'])
        self.assertEqual(service.datastore.value, fixtures.SERVICE_LINKED_VALUES_DICT['datastore'])
        self.assertEqual(service.gpu.value, fixtures.SERVICE_LINKED_VALUES_DICT['gpu'])
        self.assertEqual(service.basename.value, fixtures.SERVICE_LINKED_VALUES_DICT['basename'])
        self.assertEqual(service.lenname.value, fixtures.SERVICE_LINKED_VALUES_DICT['lenname'])

    def test_service_is_available(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)

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

    def test_service_methods_1(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)

            # Sanitized name
            self.assertEqual(service.sanitized_name('a.b.c$m1%233 2'), 'a-b-c-m1-233-2')

            # Clone machine
            self.assertEqual(service.clone_machine('name', 'description', 1), fixtures.VM_CREATION_RESULT)
            api.clone_machine.assert_called_with(
                1,
                mock.ANY,
                'name',
                'description',
                True,
                None,
                service.datastore.value,
                service.pool.value,
                None,
            )
            # Clone machine, for template
            self.assertEqual(service.clone_machine('name', 'description'), fixtures.VM_CREATION_RESULT)
            api.clone_machine.assert_called_with(
                service.machine.as_int(),
                mock.ANY,
                'name',
                'description',
                False,
                None,
                service.datastore.value,
                service.pool.value,
                None,
            )

            # Get machine info
            self.assertEqual(service.get_vm_info(1), fixtures.VMS_INFO[0])
            api.get_machine_pool_info.assert_called_with(1, service.pool.value, force=True)

            # Get nic mac
            self.assertEqual(service.get_nic_mac(1), '00:01:02:03:04:05')

            # remove machine, but this is from provider
            self.assertEqual(service.provider().remove_machine(1), fixtures.UPID)

            # Enable HA
            service.enable_vm_ha(1, True)
            api.enable_machine_ha.assert_called_with(1, True, service.ha.value)

    def test_service_methods_2(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)

            # Disable HA
            service.disable_vm_ha(1)
            api.disable_machine_ha.assert_called_with(1)

            # Get basename
            self.assertEqual(service.get_basename(), service.basename.value)

            # Get lenname
            self.assertEqual(service.get_lenname(), service.lenname.value)

            # Get macs range
            self.assertEqual(service.get_macs_range(), service.provider().get_macs_range())

            # Is HA enabled
            self.assertEqual(service.is_ha_enabled(), service.is_ha_enabled())

            # Try graceful shutdown
            self.assertEqual(service.should_try_soft_shutdown(), service.try_soft_shutdown.value)

            # Get console connection
            self.assertEqual(service.get_console_connection('1'), fixtures.CONSOLE_CONNECTION_INFO)

            # Is available
            self.assertTrue(service.is_avaliable())
