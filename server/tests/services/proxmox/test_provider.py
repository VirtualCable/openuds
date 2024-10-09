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
from uds.services.Proxmox.provider import ProxmoxProvider

from . import fixtures

from ...utils.test import UDSTransactionTestCase


class TestProxmoxProvider(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

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
        self.assertEqual(provider.start_vmid.as_int(), fixtures.PROVIDER_VALUES_DICT['start_vmid'])
        self.assertEqual(provider.macs_range.as_str(), fixtures.PROVIDER_VALUES_DICT['macs_range'])

        self.assertEqual(provider.get_macs_range(), fixtures.PROVIDER_VALUES_DICT['macs_range'])

    def test_provider_test(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            for ret_val in [True, False]:
                api.test.reset_mock()
                # Mock test_connection to return ret_val
                # Note that we must patch the class method, not the instance method
                # Because a new instance is created on test
                with mock.patch(
                    'uds.services.Proxmox.provider.ProxmoxProvider.test_connection', return_value=ret_val
                ):
                    result = ProxmoxProvider.test(
                        environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
                    )
                self.assertIsInstance(result, types.core.TestResult)
                self.assertEqual(result.success, ret_val)
                self.assertIsInstance(result.error, str)

                # Now, ensure test_connection calls api.test
                provider.test_connection()
                # Ensure test is called
                api.test.assert_called_once_with()

    def test_provider_is_available(self) -> None:
        """
        Test the provider is_available
        Thi is "specieal" because it uses cache
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)

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
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)

            self.assertEqual(provider.test_connection(), True)
            api.test.assert_called_once_with()

            self.assertEqual(provider.api.list_vms(force=True), fixtures.VMINFO_LIST)
            self.assertEqual(provider.api.list_vms(), fixtures.VMINFO_LIST)

            self.assertEqual(provider.api.get_vm_info(1), fixtures.VMINFO_LIST[0])

            self.assertEqual(provider.api.get_vm_config(1), fixtures.VMS_CONFIGURATION[0])

            self.assertEqual(
                provider.api.get_storage_info(
                    fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=True
                ),
                fixtures.STORAGES[2],
            )

    def test_provider_methods_2(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patched_provider() as provider:

            self.assertEqual(
                provider.api.get_storage_info(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node),
                fixtures.STORAGES[2],
            )

            self.assertEqual(
                provider.api.list_storages(node=fixtures.STORAGES[2].node),
                list(filter(lambda x: x.node == fixtures.STORAGES[2].node, fixtures.STORAGES)),
            )
            self.assertEqual(provider.api.list_storages(), fixtures.STORAGES)

            self.assertEqual(provider.api.list_pools(force=True), fixtures.POOLS)
            self.assertEqual(provider.api.list_pools(), fixtures.POOLS)

    def test_provider_methods3(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)

            self.assertEqual(
                provider.api.get_pool_info(fixtures.POOLS[2].id, retrieve_vm_names=True, force=True),
                fixtures.POOLS[2],
            )
            self.assertEqual(provider.api.get_pool_info(fixtures.POOLS[2].id), fixtures.POOLS[2])

            provider.api.convert_vm_to_template(1)

            self.assertEqual(
                provider.clone_vm(1, 'name', 'description', True, 'node', 'storage', 'pool', True),
                fixtures.VM_CREATION_RESULT,
            )
            api.clone_vm.assert_called_once_with(
                1, mock.ANY, 'name', 'description', True, 'node', 'storage', 'pool', True
            )

            self.assertEqual(provider.api.start_vm(1), fixtures.UPID)

            self.assertEqual(provider.api.stop_vm(1), fixtures.UPID)

            self.assertEqual(provider.api.reset_vm(1), fixtures.UPID)

            self.assertEqual(provider.api.suspend_vm(1), fixtures.UPID)

    def test_provider_methods_4(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patched_provider() as provider:
            self.assertEqual(provider.api.shutdown_vm(1), fixtures.UPID)

            self.assertEqual(provider.api.delete_vm(1), fixtures.UPID)

            self.assertEqual(provider.api.get_task_info('node', 'upid'), fixtures.TASK_STATUS)

            provider.api.enable_vm_ha(1, True, 'group')

            provider.api.set_vm_net_mac(1, 'mac')

            provider.api.disable_vm_ha(1)

            provider.api.set_vm_protection(1, node='node', protection=True)

            self.assertEqual(provider.api.list_ha_groups(), fixtures.HA_GROUPS)

    def test_provider_methods_5(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)

            self.assertEqual(provider.api.get_console_connection(1), fixtures.CONSOLE_CONNECTION_INFO)

            vmid = provider.get_new_vmid()
            for i in range(1, 128):
                self.assertEqual(provider.get_new_vmid(), vmid + i)

            self.assertEqual(provider.api.get_guest_ip_address(1), fixtures.GUEST_IP_ADDRESS)

            self.assertEqual(provider.api.supports_snapshot(1), True)

            api.list_snapshots.reset_mock()
            self.assertEqual(provider.api.get_current_vm_snapshot(1), fixtures.SNAPSHOTS_INFO[0])

            self.assertEqual(provider.api.create_snapshot(1), fixtures.UPID)

            provider.api.restore_snapshot(1, node='node', name='name')
