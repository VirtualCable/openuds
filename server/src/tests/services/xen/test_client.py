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
import contextlib
import collections.abc

# import random
import logging
import time
import typing

from uds.services.Xen.xen import (
    types as xen_types,
    exceptions as xen_exceptions,
    client as xen_client,
)

from tests.utils import vars, helpers

from tests.utils.test import UDSTransactionTestCase

logger = logging.getLogger(__name__)


class TestAzureClient(UDSTransactionTestCase):
    resource_group_name: str

    xclient: xen_client.XenClient
    sr: xen_types.StorageInfo
    net: xen_types.NetworkInfo

    def setUp(self) -> None:
        """
        Note that due to the nature of the tests, we will skip them if no azure vars are found
        Also, we already made some test on every setUp:
          * connection to azure
          * resource group info
        """
        v = vars.get_vars('xen')
        if not v:
            self.skipTest('No xen vars')

        self.xclient = xen_client.XenClient(
            host=v['host'],
            host_backup='',
            port=int(v['port']),
            username=v['username'],
            password=v['password'],
            ssl=True,
        )

        # As soon as we execute one method of xclient, login will be done, so no need to do it here

        # Look for sr (by name) and ensure it exists
        sr = next(filter(lambda i: i.name == v['sr'], self.xclient.list_srs()), None)

        if 'net' in v:
            net = next(filter(lambda i: i.name == v['net'], self.xclient.list_networks()), None)
            if net is None:
                self.skipTest(f'No network found (by name) with name {v["net"]}')
            self.net = net
        else:
            # First network found that is managed
            net = next(filter(lambda i: i.managed, self.xclient.list_networks()), None)
            if net is None:
                self.skipTest('No managed network found')

        if sr is None:
            self.skipTest(f'No SR found (by name) with name {v["sr"]}')
        self.sr = sr

    @contextlib.contextmanager
    def _create_empty_disk(self, number_of_disks: int = 1) -> collections.abc.Iterator[list[str]]:
        """
        Returns VDI opaque ref list
        """
        custom_str = str(int(time.time() * 1000000) % 1000000)
        created_disks: list[str] = []
        for n in range(number_of_disks):
            VDI_RECORD: dict[str, typing.Any] = {
                'name_label': f'TEST_EMPTY_DISK_{custom_str}_{n}',
                'name_description': 'Tesging empty disk',
                'SR': self.sr.opaque_ref,
                'virtual_size': str(10 * 1024),  # 10 MB
                'type': 'user',
                'sharable': False,
                'read_only': False,
                'xenstore_data': {},
                'other_config': {},
                'sm_config': {},
                'tags': [],
            }
            # Create synchronously
            created_disks.append(self.xclient._session.xenapi.VDI.create(VDI_RECORD))
        try:
            yield created_disks
        finally:
            for disk in created_disks:
                self.xclient._session.xenapi.VDI.destroy(disk)

    def _create_vdb(self, vdi_opaque_ref: str, vm_opaque_ref: str, user_device: int) -> str:
        VBD_RECORD: dict[str, typing.Any] = {
            'VM': vm_opaque_ref,
            'VDI': vdi_opaque_ref,
            'userdevice': str(user_device),
            'bootable': False,
            'mode': 'RW',  # Read/Write
            'type': 'Disk',
            'empty': False,
            'other_config': {},
            'qos_algorithm_type': '',
            'qos_algorithm_params': {},
            'qos_supported_algorithms': [],
        }

        return self.xclient._session.xenapi.VBD.create(VBD_RECORD)

    def _create_vif(self, network_opaque_ref: str, vm_opaque_ref: str, user_device: int) -> str:
        VIF_RECORD: dict[str, typing.Any] = {
            'device': str(user_device),
            'network': network_opaque_ref,
            'VM': vm_opaque_ref,
            'MAC': '',  # Leave blank for auto-generation or specify a MAC address
            'MTU': '1500',  # Default MTU
            'other_config': {},
            'qos_algorithm_type': '',
            'qos_algorithm_params': {},
            'locking_mode': 'network_default',
            'ipv4_allowed': [],
            'ipv6_allowed': [],
        }

        return self.xclient._session.xenapi.VIF.create(VIF_RECORD)

    @contextlib.contextmanager
    def _create_vm(self, name: str, size_mb: int, vcpus: int = 1) -> collections.abc.Iterator[str]:
        size_mb = size_mb * 1024 * 1024  # Convert to bytes
        VM_RECORD: dict[str, typing.Any] = {
            'name_label': name,
            'name_description': 'Testing VM (HVM)',
            'user_version': '1',
            'is_a_template': False,
            'affinity': '',  # Use the pool master
            'memory_static_max': str(size_mb),
            'memory_dynamic_max': str(size_mb),
            'memory_dynamic_min': str(size_mb),
            'memory_static_min': str(size_mb),
            'VCPUs_params': {},
            'VCPUs_max': str(vcpus),
            'VCPUs_at_startup': str(vcpus),
            'actions_after_shutdown': 'destroy',
            'actions_after_reboot': 'restart',
            'actions_after_crash': 'restart',
            'PV_bootloader': '',
            'PV_kernel': '',
            'PV_ramdisk': '',
            'PV_args': '',
            'PV_bootloader_args': '',
            'PV_legacy_args': '',
            'HVM_boot_policy': 'BIOS order',
            'HVM_boot_params': {'order': 'cd'},
            'platform': {'acpi': 'true', 'apic': 'true', 'pae': 'true', 'viridian': 'true'},
            'PCI_bus': '',
            'other_config': {},
            'tags': [],
            'blocked_operations': {},
            'protection_policy': '',
            'bios_strings': {},
            'auto_power_on': False,
            'start_delay': 0,
            'shutdown_delay': 0,
            'order': 0,
            'ha_restart_priority': '',
            'ha_always_run': False,
            'ha_restart_priority': '',
            'recommendations': '',
        }

        vm_opaque_ref = self.xclient._session.xenapi.VM.create(VM_RECORD)
        try:
            yield vm_opaque_ref
        finally:
            # If started, stop it before destroying
            if self.xclient.get_vm_info(vm_opaque_ref).power_state.is_running():
                self.xclient.stop_vm(vm_opaque_ref)
                helpers.waiter(
                    lambda: self.xclient.get_vm_info(vm_opaque_ref, force=True).power_state.is_stopped()
                )

            self.xclient._session.xenapi.VM.destroy(vm_opaque_ref)

    @contextlib.contextmanager
    def _create_test_vm(self) -> collections.abc.Iterator[xen_types.VMInfo]:
        # Look for the smaller vm available
        # Smaller is based on disk size, so we will look for the one with the smallest disk size
        with self._create_empty_disk(4) as disks_opaque_refs:
            with self._create_vm(f'Testing VM{int(time.time()) % 1000000}', 32) as vm_opaque_ref:
                for counter, disk_opaque_ref in enumerate(disks_opaque_refs):
                    self._create_vdb(disk_opaque_ref, vm_opaque_ref, counter)

                self._create_vif(
                    vm_opaque_ref=vm_opaque_ref, network_opaque_ref=self.net.opaque_ref, user_device=0
                )

                yield self.xclient.get_vm_info(vm_opaque_ref, force=True)

    def test_has_pool(self):
        # If has pool
        pools = self.xclient.pool.get_all()
        if pools:
            name = self.xclient.pool.get_name_label(pools[0])

            self.assertTrue(self.xclient.has_pool())
            self.assertEqual(name, self.xclient._pool_name)
        else:
            self.assertFalse(self.xclient.has_pool())
            self.assertEqual(self.xclient._pool_name, '')

    def test_get_task_info(self):
        # Ensure we have at least one vm to test
        with self._create_test_vm() as vm:
            # Start VM, should be a task
            task_id = self.xclient.start_vm(vm.opaque_ref)
            task = self.xclient.get_task_info(task_id)
            self.assertIsInstance(task, xen_types.TaskInfo)
            self.assertEqual(task.opaque_ref, task_id)
            self.assertEqual(task.name, 'Async.VM.start')

    def test_list_srs(self):
        srs = self.xclient.list_srs()
        self.assertTrue(all(isinstance(typing.cast(typing.Any, i), xen_types.StorageInfo) for i in srs))
        # Must contain at least the one we are using
        self.assertIn(self.sr.opaque_ref, {i.opaque_ref for i in srs})

    def test_get_sr_info(self):
        srs = self.xclient.list_srs()
        for sr in srs:
            sr_info = self.xclient.get_sr_info(sr.opaque_ref)
            self.assertIsInstance(sr_info, xen_types.StorageInfo)
            self.assertEqual(sr_info.opaque_ref, sr.opaque_ref)

    def test_list_networks(self):
        networks = self.xclient.list_networks()
        self.assertTrue(all(isinstance(typing.cast(typing.Any, i), xen_types.NetworkInfo) for i in networks))
        # Must contain at least the one we are using
        self.assertIn(self.net.opaque_ref, {i.opaque_ref for i in networks})

    def test_get_network_info(self):
        networks = self.xclient.list_networks()
        for network in networks:
            network_info = self.xclient.get_network_info(network.opaque_ref)
            self.assertIsInstance(network_info, xen_types.NetworkInfo)
            self.assertEqual(network_info.opaque_ref, network.opaque_ref)

    def test_list_vms(self):
        # Ensure we have at least one vm to test

        # Create 3 vms
        with self._create_test_vm() as vm_0:
            with self._create_test_vm() as vm_1:
                with self._create_test_vm() as vm_2:
                    # Now, try global list. Must contain at least the vm we just got
                    vms = self.xclient.list_vms()
                    self.assertGreaterEqual(len(vms), 3)
                    self.assertTrue(all(isinstance(typing.cast(typing.Any, i), xen_types.VMInfo) for i in vms))
                    self.assertIn(vm_0.opaque_ref.upper(), {i.opaque_ref.upper() for i in vms})
                    self.assertIn(vm_1.opaque_ref.upper(), {i.opaque_ref.upper() for i in vms})
                    self.assertIn(vm_2.opaque_ref.upper(), {i.opaque_ref.upper() for i in vms})

    def test_get_vm_info(self):
        # Ensure we have at least one vm to test
        with self._create_test_vm() as vm:
            vm_info = self.xclient.get_vm_info(vm.opaque_ref)
            self.assertIsInstance(vm_info, xen_types.VMInfo)
            self.assertEqual(vm_info.opaque_ref.upper(), vm.opaque_ref.upper())
            self.assertEqual(vm_info.name, vm.name)

    def test_start_stop_reset_vm(self):

        non_existing_vm = 'OpaqueRef:non-existing-vm'
        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.start_vm(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.start_vm_sync(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.stop_vm(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.stop_vm_sync(non_existing_vm)

        with self._create_test_vm() as vm:
            # Start VM, should be a task
            task_id = self.xclient.start_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())
            # Should be running now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

            # Stop VM, should be a task
            task_id = self.xclient.stop_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())
            # Should be stopped now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_stopped())

            # Reset should be a task, and start again the vm if stopped, so it will be running
            task_id = self.xclient.reset_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())

            # Should be running now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

        # Again for sync methods
        with self._create_test_vm() as vm:
            # Start VM sync
            self.xclient.start_vm_sync(vm.opaque_ref)
            # Should be running now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

            # Stop VM sync
            self.xclient.stop_vm_sync(vm.opaque_ref)
            # Should be stopped now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_stopped())

            # Reset sync
            self.xclient.reset_vm_sync(vm.opaque_ref)
            # Should be running now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

    def test_suspend_resume_shutdown_vm(self):
        non_existing_vm = 'OpaqueRef:non-existing-vm'
        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.suspend_vm(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.suspend_vm_sync(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.resume_vm(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.resume_vm_sync(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.shutdown_vm(non_existing_vm)

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            self.xclient.shutdown_vm_sync(non_existing_vm)

        with self._create_test_vm() as vm:
            # Start VM, should be a task
            task_id = self.xclient.start_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())
            # Should be running now
            self.assertTrue(self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

            # Suspend VM, should be a task
            task_id = self.xclient.suspend_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())
            # And until it is really stopped/suspended
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_stopped())

            # Resume VM, should be a task
            task_id = self.xclient.resume_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())
            # And until it is really running
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

            # Shutdown VM, should be a task
            task_id = self.xclient.shutdown_vm(vm.opaque_ref)
            self.assertIsInstance(task_id, str)
            # Wait task to finish
            helpers.waiter(lambda: self.xclient.get_task_info(task_id).is_done())
            # And until it is really stopped/suspended
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_stopped())

        # Again for sync methods
        with self._create_test_vm() as vm:
            # Start VM sync
            self.xclient.start_vm_sync(vm.opaque_ref)
            # Wait until it is really running
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

            # Suspend VM sync
            self.xclient.suspend_vm_sync(vm.opaque_ref)
            # Wait until it is really stopped/suspended
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_stopped())

            # Resume VM sync
            self.xclient.resume_vm_sync(vm.opaque_ref)
            # Wait until it is really running
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_running())

            # Shutdown VM sync
            self.xclient.shutdown_vm_sync(vm.opaque_ref)
            # Wait until it is really stopped/suspended
            helpers.waiter(lambda: self.xclient.get_vm_info(vm.opaque_ref, force=True).power_state.is_stopped())
