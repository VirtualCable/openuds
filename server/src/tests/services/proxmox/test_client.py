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
import time
import typing
import logging
import contextlib

from uds.core import types as core_types

from uds.services.Proxmox.proxmox import (
    types as prox_types,
    client as prox_client,
    exceptions as prox_exceptions,
)

from tests.utils import vars

from tests.utils.test import UDSTransactionTestCase

logger = logging.getLogger(__name__)


class TestProxmoxClient(UDSTransactionTestCase):
    resource_group_name: str

    pclient: prox_client.ProxmoxClient

    test_vm: prox_types.VMInfo = prox_types.VMInfo.null()
    pool: prox_types.PoolInfo = prox_types.PoolInfo.null()
    storage: prox_types.StorageInfo = prox_types.StorageInfo.null()
    hagroup: str = ''

    def setUp(self) -> None:
        v = vars.get_vars('proxmox_cluster')
        if not v:
            self.skipTest('No proxmox vars')

        self.pclient = prox_client.ProxmoxClient(
            host=v['host'],
            port=int(v['port']),
            username=v['username'],
            password=v['password'],
            use_api_token=v['use_api_token'] == 'true',
            verify_ssl=False,
        )

        for vm in self.pclient.list_vms():
            if vm.name == v['test_vm']:
                self.test_vm = self.pclient.get_vm_info(vm.id)  # To ensure we have all the info

        if self.test_vm.is_null():
            self.skipTest('No test vm found')

        for pool in self.pclient.list_pools():
            if pool.id == v['test_pool']:  # id is the pool name in proxmox
                self.pool = pool

        if self.pool.is_null():
            self.skipTest('No valid pool found')

        for storage in self.pclient.list_storages():
            if storage.storage == v['test_storage']:
                self.storage = storage

        if self.storage.is_null():
            self.skipTest('No valid storage found')

        self.hagroup = v['test_ha_group']
        # Ensure we have a valid pool, storage and ha group
        if self.hagroup not in self.pclient.list_ha_groups():
            self.skipTest('No valid ha group found')

    def _get_new_vmid(self) -> int:
        MAX_RETRIES: typing.Final[int] = 512  # So we don't loop forever, just in case...
        vmid = 0
        for _ in range(MAX_RETRIES):
            vmid = 1000000 + random.randint(0, 899999)  # Get a reasonable vmid
            if self.pclient.is_vmid_available(vmid):
                return vmid
            # All assigned vmid will be left as unusable on UDS until released by time (3 years)
            # This is not a problem at all, in the rare case that a machine id is released from uds db
            # if it exists when we try to create a new one, we will simply try to get another one
        self.fail(f'Could not get a new vmid!!: last tried {vmid}')

    def _wait_for_task(self, exec_result: prox_types.ExecResult, timeout: int = 16) -> None:
        while timeout > 0:
            timeout -= 1
            task_info = self.pclient.get_task_info(exec_result.node, exec_result.upid)
            if task_info.is_running():
                time.sleep(1)
            else:
                return
        raise Exception('Timeout waiting for task to finish')

    @contextlib.contextmanager
    def _create_test_vm(
        self,
        vmid: typing.Optional[int] = None,
        as_linked_clone: bool = False,
        target_node: typing.Optional[str] = None,
        target_storage: typing.Optional[str] = None,
        target_pool: typing.Optional[str] = None,
        must_have_vgpus: typing.Optional[bool] = None,
    ) -> typing.Iterator[prox_types.VMInfo]:
        new_vmid = self._get_new_vmid()
        res: typing.Optional[prox_types.VmCreationResult] = None
        try:
            res = self.pclient.clone_vm(
                vmid=vmid or self.test_vm.id,
                new_vmid=new_vmid,
                name=f'uds-test-{new_vmid}',
                description=f'UDS Test VM {new_vmid} (cloned from {self.test_vm.id})',
                as_linked_clone=as_linked_clone,  # Test VM is not a template, so cannot be linked cloned
                target_node=target_node,
                target_storage=target_storage or self.storage.storage,
                target_pool=target_pool,
                must_have_vgpus=must_have_vgpus,
            )
            # Wait for the task to finish
            self._wait_for_task(res.exec_result)
            yield self.pclient.get_vm_info(res.vmid)
        finally:
            if res:
                # If vm is running, stop it and delete it
                if res.vmid:
                    try:
                        vminfo = self.pclient.get_vm_info(res.vmid)
                        if vminfo.status == prox_types.VMStatus.RUNNING:
                            exec_result = self.pclient.stop_vm(res.vmid)
                            self._wait_for_task(exec_result)
                    except prox_exceptions.ProxmoxError:
                        pass
                self.pclient.delete_vm(res.vmid)

    # Connect is not needed, because setUp will do the connection so if it fails, the test will throw an exception

    def test_get_cluster_info(self) -> None:
        cluster_info = self.pclient.get_cluster_info()
        self.assertIsInstance(cluster_info, prox_types.ClusterInfo)
        # May be no part of a cluster, so cluster_info.cluster can be None
        self.assertIsNotNone(cluster_info.nodes)

    def test_get_cluster_resources(self) -> None:
        res1 = self.pclient.get_cluster_resources('vm')
        res2 = self.pclient.get_cluster_resources('storage')
        res3 = self.pclient.get_cluster_resources('node')
        res4 = self.pclient.get_cluster_resources('sdn')

        self.assertIsInstance(res1, list)
        # ensure can convert to vm info
        for r in res1:
            prox_types.VMInfo.from_dict(r)  # Should not raise

        self.assertIsInstance(res2, list)
        # ensure can convert to storage info
        for r in res2:
            prox_types.StorageInfo.from_dict(r)

        self.assertIsInstance(res3, list)
        # Ensure can convert to node stats
        for r in res3:
            prox_types.NodeStats.from_dict(r)

        self.assertIsInstance(res4, list)

    def test_get_node_networks(self) -> None:
        networks = self.pclient.get_node_networks(self.test_vm.node)
        self.assertIsInstance(networks, list)

    def test_list_node_gpu_devices(self) -> None:
        gpus = self.pclient.list_node_gpu_devices(self.test_vm.node)
        self.assertIsInstance(gpus, list)

    def test_list_node_vgpus(self) -> None:
        vgpues = self.pclient.list_node_vgpus(self.test_vm.node)
        self.assertIsInstance(vgpues, list)
        for vgpu in vgpues:
            self.assertIsInstance(vgpu, prox_types.VGPUInfo)

    def test_node_has_vgpus_available(self) -> None:
        # if no vgpu available, it should return False
        # But here, we only test that the method does not raise an exception
        self.pclient.node_has_vgpus_available(self.test_vm.node, None)

    def test_get_best_node_for_vm(self) -> None:
        node = self.pclient.get_best_node_for_vm()
        # Node should be a NodeStats, and must be part of the nodes got from get_cluster_resources
        if node is None:
            self.fail('No node found')
        self.assertIsInstance(node, prox_types.NodeStats)
        self.assertIn(node.name, [n['node'] for n in self.pclient.get_cluster_resources('node')])

    def test_clone_vm_ok(self) -> None:
        # In fact, use the context manager to test this
        # because it's the same code
        with self._create_test_vm():
            pass  # Just test that it does not raise

    def test_clone_vm_fail_invalid_vmid(self) -> None:
        with self.assertRaises(prox_exceptions.ProxmoxNotFound):
            with self._create_test_vm(vmid=-1):
                pass

    def test_clone_vm_fail_invalid_node(self) -> None:
        with self.assertRaises(prox_exceptions.ProxmoxDoesNotExists):
            with self._create_test_vm(target_node='invalid-node'):
                pass

    def test_clone_vm_fail_invalid_pool(self) -> None:
        with self.assertRaises(prox_exceptions.ProxmoxDoesNotExists):
            with self._create_test_vm(target_pool='invalid-pool'):
                pass

    def test_clone_vm_fail_invalid_storage(self) -> None:
        with self.assertRaises(prox_exceptions.ProxmoxDoesNotExists):
            with self._create_test_vm(target_storage='invalid-storage'):
                pass

    def test_clone_vm_fail_no_vgpus(self) -> None:
        with self.assertRaises(prox_exceptions.ProxmoxError):
            with self._create_test_vm(must_have_vgpus=True):
                pass

    def test_list_ha_groups(self) -> None:
        groups = self.pclient.list_ha_groups()
        self.assertIsInstance(groups, list)
        for group in groups:
            self.assertIsInstance(group, str)

        self.assertIn(self.hagroup, groups)

    def test_enable_disable_vm_ha(self) -> None:
        with self._create_test_vm() as vm:
            self.pclient.enable_vm_ha(vm.id, started=False, group=self.hagroup)
            # Ensure it's enabled
            vminfo = self.pclient.get_vm_info(vm.id, force=True)
            self.assertEqual(vminfo.ha.group, self.hagroup)
            # Disable it
            self.pclient.disable_vm_ha(vm.id)
            vminfo = self.pclient.get_vm_info(vm.id, force=True)
            self.assertEqual(vminfo.ha.group, '')

    def test_set_vm_protection(self) -> None:
        with self._create_test_vm() as vm:
            self.pclient.set_vm_protection(vm.id, protection=True)
            vmconfig = self.pclient.get_vm_config(vm.id, force=True)
            self.assertTrue(vmconfig.protection)
            self.pclient.set_vm_protection(vm.id, protection=False)
            vmconfig = self.pclient.get_vm_config(vm.id, force=True)
            self.assertFalse(vmconfig.protection)

    def test_get_guest_ip_address(self) -> None:
        # Should raise an exception, because the test vm is not running
        with self.assertRaises(prox_exceptions.ProxmoxError):
            self.pclient.get_guest_ip_address(self.test_vm.id)

    # delete_vm should work, because the vm is created and deleted in the context manager

    def test_snapshots(self) -> None:
        with self._create_test_vm() as vm:
            # Create snapshot for the vm
            task = self.pclient.create_snapshot(vm.id, name='test-snapshot')
            self._wait_for_task(task)
            snapshots = self.pclient.list_snapshots(vm.id)
            self.assertIsInstance(snapshots, list)
            # should have TWO snapshots, the one created by us and "current"
            self.assertTrue(len(snapshots) == 2)
            for snapshot in snapshots:
                self.assertIsInstance(snapshot, prox_types.SnapshotInfo)

            # test-snapshot should be there
            self.assertIn('test-snapshot', [s.name for s in snapshots])

            # Restore the snapshot
            task = self.pclient.restore_snapshot(vm.id, name='test-snapshot')
            self._wait_for_task(task)

            # Delete the snapshot
            task = self.pclient.delete_snapshot(vm.id, name='test-snapshot')
            self._wait_for_task(task)

            snapshots = self.pclient.list_snapshots(vm.id)
            self.assertTrue(len(snapshots) == 1)

    # get_task_info should work, because we wait for the task to finish in _wait_for_task

    def test_list_vms(self) -> None:
        vms = self.pclient.list_vms()
        # At least, the test vm should be there :)
        self.assertTrue(len(vms) > 0)
        # Assert the test vm is there
        self.assertIn(self.test_vm.id, [i.id for i in vms])

        self.assertTrue(self.test_vm.id > 0)
        self.assertTrue(self.test_vm.status in prox_types.VMStatus)
        self.assertTrue(self.test_vm.node)
        self.assertTrue(self.test_vm.template in (True, False))

        self.assertIsInstance(self.test_vm.agent, (str, type(None)))
        self.assertIsInstance(self.test_vm.cpus, (int, type(None)))
        self.assertIsInstance(self.test_vm.lock, (str, type(None)))
        self.assertIsInstance(self.test_vm.disk, (int, type(None)))
        self.assertIsInstance(self.test_vm.maxdisk, (int, type(None)))
        self.assertIsInstance(self.test_vm.mem, (int, type(None)))
        self.assertIsInstance(self.test_vm.maxmem, (int, type(None)))
        self.assertIsInstance(self.test_vm.name, (str, type(None)))
        self.assertIsInstance(self.test_vm.pid, (int, type(None)))
        self.assertIsInstance(self.test_vm.qmpstatus, (str, type(None)))
        self.assertIsInstance(self.test_vm.tags, (str, type(None)))
        self.assertIsInstance(self.test_vm.uptime, (int, type(None)))
        self.assertIsInstance(self.test_vm.netin, (int, type(None)))
        self.assertIsInstance(self.test_vm.netout, (int, type(None)))
        self.assertIsInstance(self.test_vm.diskread, (int, type(None)))
        self.assertIsInstance(self.test_vm.diskwrite, (int, type(None)))
        self.assertIsInstance(self.test_vm.vgpu_type, (str, type(None)))

    def test_get_vm_pool_info(self) -> None:
        with self._create_test_vm(target_pool=self.pool.id) as vm:
            vminfo = self.pclient.get_vm_pool_info(vmid=vm.id, poolid=self.pool.id)
            self.assertIsInstance(vminfo, prox_types.VMInfo)
            self.assertEqual(vminfo.id, vm.id)

    # get_vm_info should work, because we get the info of the test vm in setUp

    def test_get_vm_config(self) -> None:
        vmconfig = self.pclient.get_vm_config(self.test_vm.id)
        self.assertIsInstance(vmconfig, prox_types.VMConfiguration)
        self.assertEqual(vmconfig.name, self.test_vm.name)

    def test_set_vm_net_mac(self) -> None:
        with self._create_test_vm() as vm:
            mac = '00:11:22:33:44:55'
            self.pclient.set_vm_net_mac(vm.id, mac)
            vmconfig = self.pclient.get_vm_config(vm.id)
            self.assertEqual(vmconfig.networks[0].macaddr, mac)

    def test_start_stop_vm(self) -> None:
        with self._create_test_vm() as vm:
            task_info = self.pclient.start_vm(vm.id)
            self._wait_for_task(task_info)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.RUNNING)

            task_info = self.pclient.stop_vm(vm.id)
            self._wait_for_task(task_info)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.STOPPED)

    def test_shutdown_vm(self) -> None:
        with self._create_test_vm() as vm:
            task_info = self.pclient.start_vm(vm.id)
            self._wait_for_task(task_info)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.RUNNING)

            start_time = time.time()
            # The VM has no SO, so it will not shutdown gracefully but in 2 seconds will be stopped
            task_info = self.pclient.shutdown_vm(vm.id, timeout=2)
            self._wait_for_task(task_info)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.STOPPED)
            end_time = time.time()
            self.assertGreaterEqual(end_time - start_time, 2)

    def test_suspend_resume_vm(self) -> None:
        with self._create_test_vm() as vm:
            result = self.pclient.start_vm(vm.id)
            self._wait_for_task(result)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.RUNNING)

            result = self.pclient.suspend_vm(vm.id)
            self._wait_for_task(result)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.STOPPED)

            result = self.pclient.resume_vm(vm.id)
            self._wait_for_task(result)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.RUNNING)

    def test_convert_vm_to_template_and_clone(self) -> None:
        with self._create_test_vm() as vm:
            result = self.pclient.convert_vm_to_template(vm.id)
            self._wait_for_task(result)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).template)

            with self._create_test_vm(vmid=vm.id, as_linked_clone=True):
                pass

    def test_get_storage_info(self) -> None:
        storage_info = self.pclient.get_storage_info(self.storage.node, self.storage.storage)
        self.assertIsInstance(storage_info, prox_types.StorageInfo)
        self.assertEqual(storage_info.storage, self.storage.storage)

    def test_list_storages(self) -> None:
        storages = self.pclient.list_storages()
        self.assertIsInstance(storages, list)
        for storage in storages:
            self.assertIsInstance(storage, prox_types.StorageInfo)

        self.assertTrue(len(storages) > 0)
        self.assertIn(self.storage.storage, [s.storage for s in storages])

    def test_get_nodes_stats(self) -> None:
        stats = self.pclient.get_nodes_stats()
        self.assertIsInstance(stats, list)
        for stat in stats:
            self.assertIsInstance(stat, prox_types.NodeStats)

        self.assertGreater(len(stats), 0)
        self.assertIn(self.test_vm.node, [s.name for s in stats])

    def test_list_pools(self) -> None:
        pools = self.pclient.list_pools()
        self.assertIsInstance(pools, list)
        for pool in pools:
            self.assertIsInstance(pool, prox_types.PoolInfo)

        self.assertTrue(len(pools) > 0)
        self.assertIn(self.pool.id, [p.id for p in pools])

    def test_get_pool_info(self) -> None:
        pool_info = self.pclient.get_pool_info(self.pool.id)
        self.assertIsInstance(pool_info, prox_types.PoolInfo)
        self.assertEqual(pool_info.id, self.pool.id)

    def test_get_console_connection(self) -> None:
        # Create an vm and start it
        with self._create_test_vm() as vm:
            result = self.pclient.start_vm(vm.id)
            self._wait_for_task(result)
            self.assertTrue(self.pclient.get_vm_info(vm.id, force=True).status == prox_types.VMStatus.RUNNING)

            # Get the console connection
            console_info = self.pclient.get_console_connection(vm.id)
            self.assertIsInstance(console_info, core_types.services.ConsoleConnectionInfo)
