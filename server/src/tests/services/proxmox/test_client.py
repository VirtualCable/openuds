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

from uds.services.Proxmox.proxmox import (
    types as prox_types,
    client as prox_client,
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

    def setUp(self) -> None:
        v = vars.get_vars('proxmox')
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
        
        for storage in self.pclient.list_storages():
            if storage.storage == v['test_storage']:
                self.storage = storage

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

    def _wait_for_task(self, node: str, upid: str, timeout: int = 16) -> None:
        while timeout > 0:
            timeout -= 1
            task_info = self.pclient.get_task_info(node, upid)
            if task_info.is_running():
                time.sleep(1)
            else:
                return
        raise Exception('Timeout waiting for task to finish')

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
        res: typing.Optional[prox_types.VmCreationResult] = None
        try:
            new_vmid = self._get_new_vmid()
            res = self.pclient.clone_vm(
                vmid=self.test_vm.id,
                new_vmid=new_vmid,
                name=f'uds-test-{new_vmid}',
                description='Test VM',
                as_linked_clone=False,  # Test VM is not a template, so cannot be linked cloned
                target_node=None,
                target_storage=self.storage.storage,
                target_pool=None,
                must_have_vgpus=None,
            )
            self.assertIsInstance(res, prox_types.VmCreationResult)
        except Exception as e:
            # Remove the vm if it was created
            self.fail(f'Exception cloning vm: {e}')
        finally:
            if res and res.vmid:
                # Wait for the task to finish
                self._wait_for_task(res.node, res.upid.upid)
                self.pclient.delete_vm(res.vmid)

    def test_list_vms(self) -> None:
        vms = self.pclient.list_vms()
        # At least, the test vm should be there :)
        self.assertTrue(len(vms) > 0)
        # Assert the test vm is there
        self.assertIn(self.test_vm, vms)

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
