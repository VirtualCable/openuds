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

    def test_provider_methods(self) -> None:
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
            
            self.assertEqual(provider.get_storage_info(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=True), fixtures.STORAGES[2])
            api.get_storage.assert_called_once_with(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=True)
            api.get_storage.reset_mock()
            self.assertEqual(provider.get_storage_info(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node), fixtures.STORAGES[2])
            api.get_storage.assert_called_once_with(fixtures.STORAGES[2].storage, fixtures.STORAGES[2].node, force=False)
            
            self.assertEqual(provider.list_storages(fixtures.STORAGES[2].node), list(filter(lambda x: x.node == fixtures.STORAGES[2].node, fixtures.STORAGES)))
            api.list_storages.assert_called_once_with(node=fixtures.STORAGES[2].node, content='images', force=False)
            api.list_storages.reset_mock()
            self.assertEqual(provider.list_storages(), fixtures.STORAGES)
            api.list_storages.assert_called_once_with(node=None, content='images', force=False)
            
            
    # def list_pools(self) -> list[client.types.PoolInfo]:
    #     return self._api().list_pools()

    # def get_pool_info(self, pool_id: str, retrieve_vm_names: bool = False) -> client.types.PoolInfo:
    #     return self._api().get_pool_info(pool_id, retrieve_vm_names=retrieve_vm_names)

    # def create_template(self, vmid: int) -> None:
    #     return self._api().convert_to_template(vmid)

    # def clone_machine(
    #     self,
    #     vmid: int,
    #     name: str,
    #     description: typing.Optional[str],
    #     as_linked_clone: bool,
    #     target_node: typing.Optional[str] = None,
    #     target_storage: typing.Optional[str] = None,
    #     target_pool: typing.Optional[str] = None,
    #     must_have_vgpus: typing.Optional[bool] = None,
    # ) -> client.types.VmCreationResult:
    #     return self._api().clone_machine(
    #         vmid,
    #         self.get_new_vmid(),
    #         name,
    #         description,
    #         as_linked_clone,
    #         target_node,
    #         target_storage,
    #         target_pool,
    #         must_have_vgpus,
    #     )

    # def start_machine(self, vmid: int) -> client.types.UPID:
    #     return self._api().start_machine(vmid)

    # def stop_machine(self, vmid: int) -> client.types.UPID:
    #     return self._api().stop_machine(vmid)

    # def reset_machine(self, vmid: int) -> client.types.UPID:
    #     return self._api().reset_machine(vmid)

    # def suspend_machine(self, vmId: int) -> client.types.UPID:
    #     return self._api().suspend_machine(vmId)

    # def shutdown_machine(self, vmid: int) -> client.types.UPID:
    #     return self._api().shutdown_machine(vmid)

    # def remove_machine(self, vmid: int) -> client.types.UPID:
    #     return self._api().remove_machine(vmid)

    # def get_task_info(self, node: str, upid: str) -> client.types.TaskStatus:
    #     return self._api().get_task(node, upid)

    # def enable_ha(self, vmid: int, started: bool = False, group: typing.Optional[str] = None) -> None:
    #     self._api().enable_machine_ha(vmid, started, group)

    # def set_machine_mac(self, vmid: int, macAddress: str) -> None:
    #     self._api().set_machine_ha(vmid, macAddress)

    # def disable_ha(self, vmid: int) -> None:
    #     self._api().disable_machine_ha(vmid)

    # def set_protection(self, vmid: int, node: typing.Optional[str] = None, protection: bool = False) -> None:
    #     self._api().set_protection(vmid, node, protection)

    # def list_ha_groups(self) -> list[str]:
    #     return self._api().list_ha_groups()

    # def get_console_connection(
    #     self,
    #     machine_id: str,
    #     node: typing.Optional[str] = None,
    # ) -> typing.Optional[types.services.ConsoleConnectionInfo]:
    #     return self._api().get_console_connection(int(machine_id), node)

    # def get_new_vmid(self) -> int:
    #     while True:  # look for an unused VmId
    #         vmid = self._vmid_generator.get(self.start_vmid.as_int(), MAX_VMID)
    #         if self._api().is_vmid_available(vmid):
    #             return vmid
    #         # All assigned vmid will be left as unusable on UDS until released by time (3 years)
    #         # This is not a problem at all, in the rare case that a machine id is released from uds db
    #         # if it exists when we try to create a new one, we will simply try to get another one

    # def get_guest_ip_address(self, vmid: int, node: typing.Optional[str] = None) -> str:
    #     return self._api().get_guest_ip_address(vmid, node)

    # def supports_snapshot(self, vmid: int, node: typing.Optional[str] = None) -> bool:
    #     return self._api().supports_snapshot(vmid, node)

    # def get_current_snapshot(
    #     self, vmid: int, node: typing.Optional[str] = None
    # ) -> typing.Optional[client.types.SnapshotInfo]:
    #     return (
    #         sorted(
    #             filter(lambda x: x.snaptime, self._api().list_snapshots(vmid, node)),
    #             key=lambda x: x.snaptime or 0,
    #             reverse=True,
    #         )
    #         + [None]
    #     )[0]

    # def create_snapshot(
    #     self,
    #     vmid: int,
    #     node: typing.Optional[str] = None,
    #     name: typing.Optional[str] = None,
    #     description: typing.Optional[str] = None,
    # ) -> client.types.UPID:
    #     return self._api().create_snapshot(vmid, node, name, description)

    # def restore_snapshot(
    #     self, vmid: int, node: typing.Optional[str] = None, name: typing.Optional[str] = None
    # ) -> client.types.UPID:
    #     """
    #     In fact snapshot is not optional, but node is and want to keep the same signature as the api
    #     """
    #     return self._api().restore_snapshot(vmid, node, name)
            