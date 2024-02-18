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

from ...utils.test import UDSTestCase
from ...utils.autospec import autospec, AutoSpecMethodInfo

from uds.services.Proxmox import provider, client as pc

NODES: typing.Final[list[pc.types.Node]] = [
    pc.types.Node(name='node0', online=True, local=True, nodeid=1, ip='0.0.0.1', level='level', id='id'),
    pc.types.Node(name='node1', online=True, local=True, nodeid=2, ip='0.0.0.2', level='level', id='id'),
]

NODE_STATS: typing.Final[list[pc.types.NodeStats]] = [
    pc.types.NodeStats(
        name='name',
        status='status',
        uptime=1,
        disk=1,
        maxdisk=1,
        level='level',
        id='id',
        mem=1,
        maxmem=1,
        cpu=1.0,
        maxcpu=1,
    ),
    pc.types.NodeStats(
        name='name',
        status='status',
        uptime=1,
        disk=1,
        maxdisk=1,
        level='level',
        id='id',
        mem=1,
        maxmem=1,
        cpu=1.0,
        maxcpu=1,
    ),
]


CLUSTER_INFO: typing.Final[pc.types.ClusterInfo] = pc.types.ClusterInfo(
    cluster=pc.types.Cluster(name='name', version='version', id='id', nodes=2, quorate=1),
    nodes=NODES,
)

STORAGES: typing.Final[list[pc.types.StorageInfo]] = [
    pc.types.StorageInfo(
        node=NODES[i%len(NODES)].name,
        storage=f'storage_{i}',
        content=(f'content{i}',) * (i % 3),
        type='type',
        shared=(i < 8),  # First 8 are shared
        active=(i % 5) != 0,  # Every 5th is not active
        used=1024*1024*1024*i*4,
        avail=1024*1024*1024*i*8,
        total=1024*1024*1024*i*12,
        used_fraction=1.0,
    ) for i in range(10)
]


VGPUS: typing.Final[list[pc.types.VGPUInfo]] = [
    pc.types.VGPUInfo(
        name='name_1',
        description='description_1',
        device='device_1',
        available=True,
        type='gpu_type_1',
    ),
    pc.types.VGPUInfo(
        name='name_2',
        description='description_2',
        device='device_2',
        available=False,
        type='gpu_type_2',
    ),
    pc.types.VGPUInfo(
        name='name_3',
        description='description_3',
        device='device_3',
        available=True,
        type='gpu_type_3',
    ),
]

VMS_INFO: typing.Final[list[pc.types.VMInfo]] = [
    pc.types.VMInfo(
        status='status',
        vmid=i,
        node=NODES[i % len(NODES)].name,
        template=True,
        agent='agent',
        cpus=1,
        lock='lock',
        disk=1,
        maxdisk=1,
        mem=1024*1024*1024*i,
        maxmem=1024*1024*1024*i*2,
        name='name',
        pid=1000+i,
        qmpstatus='qmpstatus',
        tags='tags',
        uptime=60*60*24*i,
        netin=1,
        netout=1,
        diskread=1,
        diskwrite=1,
        vgpu_type=VGPUS[i % len(VGPUS)].type,
    )
    for i in range(10)
]

VMS_CONFIGURATION: typing.Final[list[pc.types.VMConfiguration]] = [
    pc.types.VMConfiguration(
        name=f'vm_name_{i}',
        vga='cirrus',
        sockets=1,
        cores=1,
        vmgenid='vmgenid',
        digest='digest',
        networks=[pc.types.NetworkConfiguration(net='net', type='type', mac='mac')],
        tpmstate0='tpmstate0',
        template=bool(i > 8),  # Last two are templates
    )
    for i in range(10)
]


UPID: typing.Final[pc.types.UPID] = pc.types.UPID(
    node=NODES[0].name,
    pid=1,
    pstart=1,
    starttime=datetime.datetime.now(),
    type='type',
    vmid=VMS_INFO[0].vmid,
    user='user',
    upid='upid',
)


VM_CREATION_RESULT: typing.Final[pc.types.VmCreationResult] = pc.types.VmCreationResult(
    node=NODES[0].name,
    vmid=VMS_INFO[0].vmid,
    upid=UPID,
)


SNAPSHOTS_INFO: typing.Final[list[pc.types.SnapshotInfo]] = [
    pc.types.SnapshotInfo(
        name=f'snap_name_{i}',
        description=f'snap desription{i}',
        parent=f'snap_parent_{i}',
        snaptime=int(datetime.datetime.now().timestamp()),
        vmstate=bool(i % 2),
    )
    for i in range(10)
]

TASK_STATUS = pc.types.TaskStatus(
    node=NODES[0].name,
    pid=1,
    pstart=1,
    starttime=datetime.datetime.now(),
    type='type',
    status='status',
    exitstatus='exitstatus',
    user='user',
    upid='upid',
    id='id',
)

POOL_MEMBERS: typing.Final[list[pc.types.PoolMemberInfo]] = [
    pc.types.PoolMemberInfo(
        id=f'id_{i}',
        node=NODES[i % len(NODES)].name,
        storage=STORAGES[i % len(STORAGES)].storage,
        type='type',
        vmid=VMS_INFO[i%len(VMS_INFO)].vmid,
        vmname=VMS_INFO[i%len(VMS_INFO)].name or '',
    ) for i in range(10)
]   

POOLS: typing.Final[list[pc.types.PoolInfo]] = [
    pc.types.PoolInfo(
        poolid=f'pool_{i}',
        comments=f'comments_{i}',
        members=POOL_MEMBERS,
    ) for i in range(10)
]         

# Methods that returns None or "internal" methods are not tested
CLIENT_METHODS_INFO: typing.Final[list[AutoSpecMethodInfo]] = [
    # connect returns None
    # Test method
    AutoSpecMethodInfo('test', method=mock.Mock(return_value=True)),
    # get_cluster_info
    AutoSpecMethodInfo('get_cluster_info', return_value=CLUSTER_INFO),
    # get_next_vmid
    AutoSpecMethodInfo('get_next_vmid', return_value=1),
    # is_vmid_available
    AutoSpecMethodInfo('is_vmid_available', return_value=True),
    # get_node_networks, not called never (ensure it's not called by mistake)
    # list_node_gpu_devices
    AutoSpecMethodInfo('list_node_gpu_devices', return_value=['gpu_dev_1', 'gpu_dev_2']),
    # list_node_vgpus
    AutoSpecMethodInfo('list_node_vgpus', return_value=VGPUS),
    # node_has_vgpus_available
    AutoSpecMethodInfo('node_has_vgpus_available', return_value=True),
    # get_best_node_for_machine
    AutoSpecMethodInfo('get_best_node_for_machine', return_value=NODE_STATS[0]),
    # clone_machine
    AutoSpecMethodInfo('clone_machine', return_value=VM_CREATION_RESULT),
    # list_ha_groups
    AutoSpecMethodInfo('list_ha_groups', return_value=['ha_group_1', 'ha_group_2']),
    # enable_machine_ha return None
    # disable_machine_ha return None
    # set_protection return None
    # get_guest_ip_address
    AutoSpecMethodInfo('get_guest_ip_address', return_value='1.0.0.1'),
    # remove_machine
    AutoSpecMethodInfo('remove_machine', return_value=UPID),
    # list_snapshots
    AutoSpecMethodInfo('list_snapshots', return_value=SNAPSHOTS_INFO),
    # supports_snapshot
    AutoSpecMethodInfo('supports_snapshot', return_value=True),
    # create_snapshot
    AutoSpecMethodInfo('create_snapshot', return_value=UPID),
    # remove_snapshot
    AutoSpecMethodInfo('remove_snapshot', return_value=UPID),
    # get_current_snapshot
    AutoSpecMethodInfo('get_current_snapshot', return_value=SNAPSHOTS_INFO[0].name),
    # restore_snapshot
    AutoSpecMethodInfo('restore_snapshot', return_value=UPID),
    # get_task
    AutoSpecMethodInfo('get_task', return_value=TASK_STATUS),
    # list_machines
    AutoSpecMethodInfo('list_machines', return_value=VMS_INFO),
    # get_machines_pool_info
    AutoSpecMethodInfo('get_machines_pool_info', return_value=VMS_INFO[0]),
    # get_machine_info
    AutoSpecMethodInfo('get_machine_info', return_value=VMS_INFO[0]),
    # get_machine_configuration
    AutoSpecMethodInfo('get_machine_configuration', method=lambda vmid: VMS_CONFIGURATION[vmid - 1]),
    # set_machine_ha return None
    # start_machine
    AutoSpecMethodInfo('start_machine', return_value=UPID),
    # stop_machine
    AutoSpecMethodInfo('stop_machine', return_value=UPID),
    # reset_machine
    AutoSpecMethodInfo('reset_machine', return_value=UPID),
    # suspend_machine
    AutoSpecMethodInfo('suspend_machine', return_value=UPID),
    # resume_machine
    AutoSpecMethodInfo('resume_machine', return_value=UPID),
    # shutdown_machine
    AutoSpecMethodInfo('shutdown_machine', return_value=UPID),
    # convert_to_template
    AutoSpecMethodInfo('convert_to_template', return_value=UPID),
    # get_storage
    AutoSpecMethodInfo('get_storage', method=lambda storage, node: next(filter(lambda s: s.storage == storage, STORAGES))),
    # list_storages
    AutoSpecMethodInfo('list_storages', return_value=STORAGES),
    # get_node_stats
    AutoSpecMethodInfo('get_node_stats', method=lambda node: next(filter(lambda n: n.name == node, NODE_STATS))),
    # list_pools
    AutoSpecMethodInfo('list_pools', return_value=POOLS),
]


class TestProxmovProvider(UDSTestCase):
    def test_provider(self) -> None:
        """
        Test the provider
        """
        client = autospec(pc.ProxmoxClient, CLIENT_METHODS_INFO)
        assert client.test() is True
        assert client.get_cluster_info() == CLUSTER_INFO
        assert client.get_next_vmid() == 1
        assert client.is_vmid_available(1) is True
        assert client.get_machine_configuration(1) == VMS_CONFIGURATION[0]
