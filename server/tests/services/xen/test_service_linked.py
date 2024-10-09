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
import random
import typing
from unittest import mock

from uds.core.util import net

from . import fixtures

from ...utils.test import UDSTestCase

from uds.services.Xen.xen import types as xen_types


class TestXenLinkedService(UDSTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clean()

    def test_service_data(self) -> None:
        service = fixtures.create_service_linked()

        self.assertEqual(service.datastore.value, fixtures.SERVICE_VALUES_DICT['datastore'])
        self.assertEqual(service.min_space_gb.value, fixtures.SERVICE_VALUES_DICT['min_space_gb'])
        self.assertEqual(service.machine.value, fixtures.SERVICE_VALUES_DICT['machine'])
        self.assertEqual(service.network.value, fixtures.SERVICE_VALUES_DICT['network'])
        self.assertEqual(service.memory.value, fixtures.SERVICE_VALUES_DICT['memory'])
        self.assertEqual(service.shadow.value, fixtures.SERVICE_VALUES_DICT['shadow'])
        self.assertEqual(service.remove_duplicates.value, fixtures.SERVICE_VALUES_DICT['remove_duplicates'])
        self.assertEqual(service.maintain_on_error.value, fixtures.SERVICE_VALUES_DICT['maintain_on_error'])
        self.assertEqual(service.basename.value, fixtures.SERVICE_VALUES_DICT['basename'])
        self.assertEqual(service.lenname.value, fixtures.SERVICE_VALUES_DICT['lenname'])

    def test_has_datastore_space(self) -> None:
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_linked(provider=provider)
            api = typing.cast(mock.MagicMock, provider.api)

            # Should not raise any exception
            service.has_datastore_space()
            api.get_sr_info.assert_called_with(service.datastore.value)
            api.get_sr_info.return_value = fixtures.LOW_SPACE_SR_INFO
            api.get_sr_info.side_effect = None  # Reset side effect
            # Should raise an exception
            with self.assertRaises(Exception):
                service.has_datastore_space()

    def test_service_is_available(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            self.assertTrue(service.is_avaliable())
            api.test.assert_called_with()
            # With data cached, even if test fails, it will return True
            api.test.side_effect = Exception('Testing exception')
            self.assertTrue(service.is_avaliable())

            # Data is cached, so we need to reset it
            api.test.reset_mock()
            service.provider().is_available.cache_clear()  # type: ignore
            # Now should return False as we have reset the cache
            self.assertFalse(service.is_avaliable())
            api.test.assert_called_with()

    def test_start_deploy_of_template(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            service.start_deploy_of_template('name', 'comments')
            # Ensure has space
            api.get_sr_info.assert_called_with(service.datastore.value)
            api.clone_vm.assert_called_with(service.machine.value, 'name', service.datastore.value)

    def test_convert_to_template(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            service.convert_to_template('vm_opaque_ref')
            api.convert_to_template.assert_called_with('vm_opaque_ref', service.shadow.value)

    def test_start_deploy_from_template(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            service.deploy_from_template('template_opaque_ref', name='name', comments='comments')
            api.deploy_from_template.assert_called_with('template_opaque_ref', 'name')

    def test_delete_template(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            service.delete_template('template_opaque_ref')
            api.delete_template.assert_called_once_with('template_opaque_ref')

    def test_configure_machine(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            service.configure_vm('vm_opaque_ref', '00:01:02:03:04:05')
            api.configure_vm.assert_called_once_with(
                'vm_opaque_ref',
                mac_info={'network': service.network.value, 'mac': '00:01:02:03:04:05'},
                memory=service.memory.value,
            )

    def test_get_mac(self) -> None:
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_linked(provider=provider)

            for _ in range(10):
                mac = service.get_mac(mock.MagicMock(), 'vm_opaque_ref')
                self.assertTrue(net.is_valid_mac(mac))

    def test_is_running(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)

            VM = random.choice(fixtures.VMS_INFO)

            for state in xen_types.PowerState:
                VM.power_state = state
                api.reset_mock()
                # Only RUNNING state is considered as running
                self.assertEqual(
                    service.is_running(mock.MagicMock(), VM.opaque_ref), state == xen_types.PowerState.RUNNING
                )
                api.get_vm_info.assert_called_with(VM.opaque_ref)

    def test_start_stop_shutdown(self) -> None:
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_linked(provider=provider)

            VM = random.choice(fixtures.VMS_INFO)
            VM.power_state = xen_types.PowerState.HALTED
            service.start(mock.MagicMock(), VM.opaque_ref)
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)

            service.stop(mock.MagicMock(), VM.opaque_ref)
            self.assertEqual(VM.power_state, xen_types.PowerState.HALTED)

            VM.power_state = xen_types.PowerState.RUNNING
            service.shutdown(mock.MagicMock(), VM.opaque_ref)
            self.assertEqual(VM.power_state, xen_types.PowerState.HALTED)

    def test_delete(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            for state in [xen_types.PowerState.HALTED, xen_types.PowerState.RUNNING]:
                for soft_shutdown in [True, False]:
                    service.should_try_soft_shutdown = mock.MagicMock(return_value=soft_shutdown)
                    VM = random.choice(fixtures.VMS_INFO)
                    VM.power_state = state
                    service.delete(mock.MagicMock(), VM.opaque_ref)
                    if state == xen_types.PowerState.RUNNING:
                        if soft_shutdown:
                            api.shutdown_vm.assert_called_with(VM.opaque_ref)
                        else:
                            api.stop_vm.assert_called_with(VM.opaque_ref)
                    else:
                        api.delete_vm.assert_called_with(VM.opaque_ref)
