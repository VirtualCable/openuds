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

from uds.core import types, ui, environment
from uds.services.Xen.provider import XenProvider
from uds.services.Xen.xen import types as xen_types

from . import fixtures

from ...utils.test import UDSTransactionTestCase


class TestXenProvider(UDSTransactionTestCase):
    def test_provider_data(self) -> None:
        """
        Test the provider
        """
        provider = fixtures.create_provider()  # Will not use client api, so no need to patch it

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

        self.assertEqual(provider.host_backup.as_str(), fixtures.PROVIDER_VALUES_DICT['host_backup'])

    def test_provider_is_available(self) -> None:
        """
        Test the provider is_available
        Thi is "specieal" because it uses cache
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api)

            # Fist, true result
            api.test.return_value = True
            self.assertEqual(provider.is_available(), True)
            api.test.assert_called_once_with()
            api.test.reset_mock()  # Reset counter

            # Now, even if set test to false, should return true due to cache
            # To fail, make test mock raise an exception
            api.test.side_effect = Exception('Testing exception')
            self.assertEqual(provider.is_available(), True)
            api.test.assert_not_called()

            # clear cache of method
            provider.is_available.cache_clear()  # type: ignore  # clear_cache is added by decorator
            self.assertEqual(provider.is_available(), False)
            api.test.assert_called_once_with()

    def test_provider_get_connection(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api)

            with provider.get_connection() as conn:
                self.assertEqual(conn, api)

    def test_provider_test(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api)
            for ret_val in [True, False]:
                api.test.reset_mock()
                # Mock test_connection to return ret_val
                # Mock test_connection to return ret_val
                # Note that we must patch the class method, not the instance method
                # Because a new instance is created on test
                with mock.patch(
                    'uds.services.Xen.provider.XenProvider.test_connection',
                    side_effect=Exception('Testing exception') if not ret_val else None,
                ):
                    result = XenProvider.test(
                        environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
                    )
                self.assertIsInstance(result, types.core.TestResult)
                self.assertEqual(result.success, ret_val)
                self.assertIsInstance(result.error, str)

                # Now, ensure test_connection calls api.test
                provider.test_connection()
                # Ensure test is called
                api.test.assert_called_once_with()

    def test_api_methods(self) -> None:
        """
        Test the provider
        """
        fixtures.clean()

        with fixtures.patched_provider() as provider:
            api = provider._api  # typing.cast(mock.MagicMock, provider._api)

            self.assertEqual(api.has_pool(), True)
            self.assertEqual(api.get_pool_name(), fixtures.POOL_NAME)
            self.assertEqual(api.check_login(), True)
            self.assertEqual(api.get_task_info('task_id'), fixtures.TASK_INFO)
            self.assertEqual(api.list_srs(), fixtures.SRS_INFO)
            SR = random.choice(fixtures.SRS_INFO)
            self.assertEqual(api.get_sr_info(SR.opaque_ref), SR)

            self.assertEqual(api.list_networks(), fixtures.NETWORKS_INFO)
            NETWORK = random.choice(fixtures.NETWORKS_INFO)
            self.assertEqual(api.get_network_info(NETWORK.opaque_ref), NETWORK)

            self.assertEqual(api.list_vms(), fixtures.VMS_INFO)
            VM = random.choice(fixtures.VMS_INFO)
            self.assertEqual(api.get_vm_info(VM.opaque_ref), VM)

            # Test power state changers, start_vm, start_vm_sync, ...
            VM.power_state = xen_types.PowerState.HALTED
            self.assertEqual(api.start_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)
            VM.power_state = xen_types.PowerState.HALTED
            self.assertIsNone(api.start_vm_sync(VM.opaque_ref))
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)
            
            VM.power_state = xen_types.PowerState.RUNNING
            self.assertEqual(api.stop_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(VM.power_state, xen_types.PowerState.HALTED)
            VM.power_state = xen_types.PowerState.RUNNING
            self.assertIsNone(api.stop_vm_sync(VM.opaque_ref))
            self.assertEqual(VM.power_state, xen_types.PowerState.HALTED)

            VM.power_state = xen_types.PowerState.RUNNING            
            self.assertEqual(api.suspend_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(VM.power_state, xen_types.PowerState.SUSPENDED)
            VM.power_state = xen_types.PowerState.RUNNING
            self.assertIsNone(api.suspend_vm_sync(VM.opaque_ref))
            self.assertEqual(VM.power_state, xen_types.PowerState.SUSPENDED)

            # VM.power_state = xen_types.PowerState.SUSPENDED
            self.assertEqual(api.resume_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)
            VM.power_state = xen_types.PowerState.SUSPENDED
            self.assertIsNone(api.resume_vm_sync(VM.opaque_ref))
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)

            VM.power_state = xen_types.PowerState.RUNNING
            self.assertEqual(api.reset_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)
            self.assertIsNone(api.reset_vm_sync(VM.opaque_ref))
            self.assertEqual(VM.power_state, xen_types.PowerState.RUNNING)

            #VM.power_state = xen_types.PowerState.RUNNING
            self.assertEqual(api.shutdown_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(VM.power_state, xen_types.PowerState.HALTED)
            VM.power_state = xen_types.PowerState.RUNNING
            self.assertIsNone(api.shutdown_vm_sync(VM.opaque_ref))
            self.assertEqual(VM.power_state, xen_types.PowerState.HALTED)
            
            self.assertEqual(api.clone_vm(VM.opaque_ref, 'new_name'), fixtures.GENERAL_OPAQUE_REF)
            
            # delete_vm is default, so no need to test it
            # configure_vm is default, so no need to test it
            
            self.assertEqual(api.get_first_ip(VM.opaque_ref), fixtures.GENERAL_IP)
            self.assertEqual(api.get_first_mac(VM.opaque_ref), fixtures.GENERAL_MAC)
            self.assertEqual(api.provision_vm(VM.opaque_ref), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(api.create_snapshot(VM.opaque_ref, 'snapshot_name'), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(api.delete_snapshot('snapshot_id'), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(api.restore_snapshot('snapshot_id'), fixtures.GENERAL_OPAQUE_REF)
            self.assertEqual(api.list_snapshots(VM.opaque_ref), fixtures.VMS_INFO)
            self.assertEqual(api.list_folders(), fixtures.FOLDERS)
            
            FOLDER = VM.folder
            VMS_IN_FOLDER = [vm for vm in fixtures.VMS_INFO if vm.folder == FOLDER]
            self.assertEqual(api.list_vms_in_folder(FOLDER), VMS_IN_FOLDER)
            self.assertEqual(api.deploy_from_template(VM.opaque_ref, 'new-name'), fixtures.GENERAL_OPAQUE_REF)