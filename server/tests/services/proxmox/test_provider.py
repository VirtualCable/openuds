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
import datetime
import collections.abc
import itertools
from unittest import mock

from uds.core import ui, environment
from uds.services.Proxmox.provider import ProxmoxProvider

from . import fixtures

from ...utils.test import UDSTestCase


class TestProxmovProvider(UDSTestCase):
    def test_provider_data(self) -> None:
        """
        Test the provider
        """
        provider = fixtures.create_provider()  # Will not use client api, so no need to patch it

        self.assertEqual(provider.host.as_str(), fixtures.PROVIDER_VALUES_DICT['host'])
        self.assertEqual(provider.port.as_int(), fixtures.PROVIDER_VALUES_DICT['port'])
        self.assertEqual(provider.username.as_str(), fixtures.PROVIDER_VALUES_DICT['username'])
        self.assertEqual(provider.password.as_str(), fixtures.PROVIDER_VALUES_DICT['password'])
        self.assertEqual(
            typing.cast(ui.gui.NumericField, provider.concurrent_creation_limit).as_int(),
            fixtures.PROVIDER_VALUES_DICT['concurrent_creation_limit'],
        )
        # concurrent_removal_limit
        self.assertEqual(
            typing.cast(ui.gui.NumericField, provider.concurrent_removal_limit).as_int(),
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
        with fixtures.patch_provider_api() as api:
            # Fist, true result
            result = ProxmoxProvider.test(
                environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
            )

            # Ensure test is called
            api.test.assert_called_once_with()

            self.assertIsInstance(result, collections.abc.Sequence)
            self.assertEqual(result[0], True)
            self.assertIsInstance(result[1], str)

            # Now, return false
            api.test.return_value = False
            api.test.reset_mock()

            result = ProxmoxProvider.test(
                environment.Environment.temporary_environment(), fixtures.PROVIDER_VALUES_DICT
            )

            # Ensure test is called
            api.test.assert_called_once_with()

            self.assertIsInstance(result, collections.abc.Sequence)
            self.assertEqual(result[0], False)
            self.assertIsInstance(result[1], str)

    def test_provider_is_available(self) -> None:
        """
        Test the provider is_available
        Thi is "specieal" because it uses cache
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
        with fixtures.patch_provider_api() as api:
            provider = fixtures.create_provider()

            self.assertEqual(provider.test_connection(), True)
            api.test.assert_called_once_with()

            self.assertEqual(provider.list_machines(force=True), fixtures.VMS_INFO)
            api.list_machines.assert_called_once_with(force=True)
            api.list_machines.reset_mock()
            self.assertEqual(provider.list_machines(), fixtures.VMS_INFO)
            api.list_machines.assert_called_once_with(force=False)

            self.assertEqual(provider.get_machine_info(1), fixtures.VMS_INFO[0])
            api.get_machine_pool_info.assert_called_once_with(1, None, force=True)

            self.assertEqual(provider.get_machine_configuration(1), fixtures.VMS_CONFIGURATION[0])
            api.get_machine_configuration.assert_called_once_with(1, force=True)

            self.assertEqual(
                provider.get_storage_info(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=True),
                fixtures.STORAGES[2],
            )
            api.get_storage.assert_called_once_with(
                fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=True
            )

    def test_provider_methods_2(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patch_provider_api() as api:
            provider = fixtures.create_provider()
            self.assertEqual(
                provider.get_storage_info(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node),
                fixtures.STORAGES[2],
            )
            api.get_storage.assert_called_once_with(
                fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=False
            )

            self.assertEqual(
                provider.list_storages(fixtures.STORAGES[2].node),
                list(filter(lambda x: x.node == fixtures.STORAGES[2].node, fixtures.STORAGES)),
            )
            api.list_storages.assert_called_once_with(
                node=fixtures.STORAGES[2].node, content='images', force=False
            )
            api.list_storages.reset_mock()
            self.assertEqual(provider.list_storages(), fixtures.STORAGES)
            api.list_storages.assert_called_once_with(node=None, content='images', force=False)

            self.assertEqual(provider.list_pools(force=True), fixtures.POOLS)
            api.list_pools.assert_called_once_with(force=True)
            api.list_pools.reset_mock()
            self.assertEqual(provider.list_pools(), fixtures.POOLS)
            api.list_pools.assert_called_once_with(force=False)

    def test_provider_methods3(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patch_provider_api() as api:
            provider = fixtures.create_provider()
            self.assertEqual(
                provider.get_pool_info(fixtures.POOLS[2].poolid, retrieve_vm_names=True, force=True),
                fixtures.POOLS[2],
            )
            api.get_pool_info.assert_called_once_with(
                fixtures.POOLS[2].poolid, retrieve_vm_names=True, force=True
            )
            api.get_pool_info.reset_mock()
            self.assertEqual(provider.get_pool_info(fixtures.POOLS[2].poolid), fixtures.POOLS[2])
            api.get_pool_info.assert_called_once_with(
                fixtures.POOLS[2].poolid, retrieve_vm_names=False, force=False
            )

            provider.create_template(1)
            api.convert_to_template.assert_called_once_with(1)

            self.assertEqual(
                provider.clone_machine(1, 'name', 'description', True, 'node', 'storage', 'pool', True),
                fixtures.VM_CREATION_RESULT,
            )
            api.clone_machine.assert_called_once_with(
                1, mock.ANY, 'name', 'description', True, 'node', 'storage', 'pool', True
            )

            self.assertEqual(provider.start_machine(1), fixtures.UPID)
            api.start_machine.assert_called_once_with(1)

            self.assertEqual(provider.stop_machine(1), fixtures.UPID)
            api.stop_machine.assert_called_once_with(1)

            self.assertEqual(provider.reset_machine(1), fixtures.UPID)
            api.reset_machine.assert_called_once_with(1)

            self.assertEqual(provider.suspend_machine(1), fixtures.UPID)
            api.suspend_machine.assert_called_once_with(1)

    def test_provider_methods_4(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patch_provider_api() as api:
            provider = fixtures.create_provider()
            self.assertEqual(provider.shutdown_machine(1), fixtures.UPID)
            api.shutdown_machine.assert_called_once_with(1)

            self.assertEqual(provider.remove_machine(1), fixtures.UPID)
            api.remove_machine.assert_called_once_with(1)

            self.assertEqual(provider.get_task_info('node', 'upid'), fixtures.TASK_STATUS)
            api.get_task.assert_called_once_with('node', 'upid')

            provider.enable_ha(1, True, 'group')
            api.enable_machine_ha.assert_called_once_with(1, True, 'group')

            provider.set_machine_mac(1, 'mac')
            api.set_machine_ha.assert_called_once_with(1, 'mac')

            provider.disable_ha(1)
            api.disable_machine_ha.assert_called_once_with(1)

            provider.set_protection(1, 'node', True)
            api.set_protection.assert_called_once_with(1, 'node', True)

            self.assertEqual(provider.list_ha_groups(), fixtures.HA_GROUPS)
            api.list_ha_groups.assert_called_once_with()

    def test_provider_methods_5(self) -> None:
        """
        Test the provider methods
        """
        with fixtures.patch_provider_api() as api:
            provider = fixtures.create_provider()

            self.assertEqual(provider.get_console_connection('1'), fixtures.CONSOLE_CONNECTION)
            api.get_console_connection.assert_called_once_with(1, None)

            vmid = provider.get_new_vmid()
            for i in range(1, 128):
                self.assertEqual(provider.get_new_vmid(), vmid + i)

            self.assertEqual(provider.get_guest_ip_address(1), fixtures.GUEST_IP_ADDRESS)
            api.get_guest_ip_address.assert_called_once_with(1, None)

            self.assertEqual(provider.supports_snapshot(1), True)
            api.supports_snapshot.assert_called_once_with(1, None)

            api.list_snapshots.reset_mock()
            self.assertEqual(provider.get_current_snapshot(1), fixtures.SNAPSHOTS_INFO[0])
            api.list_snapshots.assert_called_once_with(1, None)

            self.assertEqual(provider.create_snapshot(1), fixtures.UPID)
            api.create_snapshot.assert_called_once_with(1, None, None, None)

            provider.restore_snapshot(1, 'node', 'name')
            api.restore_snapshot.assert_called_once_with(1, 'node', 'name')
