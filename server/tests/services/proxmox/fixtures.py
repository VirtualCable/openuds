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
import typing
import datetime
import collections.abc
import itertools

from unittest import mock
import uuid

from uds.core import types, environment
from uds.core.ui.user_interface import gui
from uds.services.OpenNebula.on import vm

from ...utils.test import UDSTestCase
from ...utils.autospec import autospec, AutoSpecMethodInfo

from uds.services.Proxmox import (
    provider,
    client,
    service,
    service_fixed,
    publication,
    deployment,
    deployment_fixed,
)

NODES: typing.Final[list[client.types.Node]] = [
    client.types.Node(name='node0', online=True, local=True, nodeid=1, ip='0.0.0.1', level='level', id='id'),
    client.types.Node(name='node1', online=True, local=True, nodeid=2, ip='0.0.0.2', level='level', id='id'),
]

NODE_STATS: typing.Final[list[client.types.NodeStats]] = [
    client.types.NodeStats(
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
    client.types.NodeStats(
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


CLUSTER_INFO: typing.Final[client.types.ClusterInfo] = client.types.ClusterInfo(
    cluster=client.types.Cluster(name='name', version='version', id='id', nodes=2, quorate=1),
    nodes=NODES,
)

STORAGES: typing.Final[list[client.types.StorageInfo]] = [
    client.types.StorageInfo(
        node=NODES[i % len(NODES)].name,
        storage=f'storage_{i}',
        content=(f'content{i}',) * (i % 3),
        type='images',
        shared=(i < 8),  # First 8 are shared
        active=(i % 5) != 0,  # Every 5th is not active
        used=1024 * 1024 * 1024 * i * 4,
        avail=1024 * 1024 * 1024 * i * 8,
        total=1024 * 1024 * 1024 * i * 12,
        used_fraction=1.0,
    )
    for i in range(10)
]


VGPUS: typing.Final[list[client.types.VGPUInfo]] = [
    client.types.VGPUInfo(
        name='name_1',
        description='description_1',
        device='device_1',
        available=True,
        type='gpu_type_1',
    ),
    client.types.VGPUInfo(
        name='name_2',
        description='description_2',
        device='device_2',
        available=False,
        type='gpu_type_2',
    ),
    client.types.VGPUInfo(
        name='name_3',
        description='description_3',
        device='device_3',
        available=True,
        type='gpu_type_3',
    ),
]

HA_GROUPS: typing.Final[list[str]] = [
    'ha_group_1',
    'ha_group_2',
    'ha_group_3',
    'ha_group_4',
]

VMS_INFO: typing.Final[list[client.types.VMInfo]] = [
    client.types.VMInfo(
        status='status',
        vmid=i,
        node=NODES[i % len(NODES)].name,
        template=True,
        agent='agent',
        cpus=1,
        lock='lock',
        disk=1,
        maxdisk=1,
        mem=1024 * 1024 * 1024 * i,
        maxmem=1024 * 1024 * 1024 * i * 2,
        name=f'name{i}',
        pid=1000 + i,
        qmpstatus='qmpstatus',
        tags='tags',
        uptime=60 * 60 * 24 * i,
        netin=1,
        netout=1,
        diskread=1,
        diskwrite=1,
        vgpu_type=VGPUS[i % len(VGPUS)].type,
    )
    for i in range(1,16)
]

VMS_CONFIGURATION: typing.Final[list[client.types.VMConfiguration]] = [
    client.types.VMConfiguration(
        name=f'vm_name_{i}',
        vga='cirrus',
        sockets=1,
        cores=1,
        vmgenid='vmgenid',
        digest='digest',
        networks=[
            client.types.NetworkConfiguration(
                net='net', type='type', mac=f'{i:02x}:{i+1:02x}:{i+2:02x}:{i+3:02x}:{i+4:02x}:{i+5:02x}'
            )
        ],
        tpmstate0='tpmstate0',
        template=bool(i > 8),  # Last two are templates
    )
    for i in range(10)
]


UPID: typing.Final[client.types.UPID] = client.types.UPID(
    node=NODES[0].name,
    pid=1,
    pstart=1,
    starttime=datetime.datetime.now(),
    type='type',
    vmid=VMS_INFO[0].vmid,
    user='user',
    upid='upid',
)


VM_CREATION_RESULT: typing.Final[client.types.VmCreationResult] = client.types.VmCreationResult(
    node=NODES[0].name,
    vmid=VMS_INFO[0].vmid,
    upid=UPID,
)


SNAPSHOTS_INFO: typing.Final[list[client.types.SnapshotInfo]] = [
    client.types.SnapshotInfo(
        name=f'snap_name_{i}',
        description=f'snap desription{i}',
        parent=f'snap_parent_{i}',
        snaptime=int(datetime.datetime.now().timestamp()),
        vmstate=bool(i % 2),
    )
    for i in range(10)
]

TASK_STATUS = client.types.TaskStatus(
    node=NODES[0].name,
    pid=1,
    pstart=1,
    starttime=datetime.datetime.now(),
    type='type',
    status='stopped',
    exitstatus='OK',
    user='user',
    upid='upid',
    id='id',
)

POOL_MEMBERS: typing.Final[list[client.types.PoolMemberInfo]] = [
    client.types.PoolMemberInfo(
        id=f'id_{i}',
        node=NODES[i % len(NODES)].name,
        storage=STORAGES[i % len(STORAGES)].storage,
        type='type',
        vmid=VMS_INFO[i % len(VMS_INFO)].vmid,
        vmname=VMS_INFO[i % len(VMS_INFO)].name or '',
    )
    for i in range(10)
]

POOLS: typing.Final[list[client.types.PoolInfo]] = [
    client.types.PoolInfo(
        poolid=f'pool_{i}',
        comments=f'comments_{i}',
        members=POOL_MEMBERS,
    )
    for i in range(10)
]

GUEST_IP_ADDRESS: typing.Final[str] = '1.0.0.1'

CONSOLE_CONNECTION_INFO: typing.Final[types.services.ConsoleConnectionInfo] = (
    types.services.ConsoleConnectionInfo(
        type='spice',
        address=GUEST_IP_ADDRESS,
        port=5900,
        secure_port=5901,
        cert_subject='',
        ticket=types.services.ConsoleConnectionTicket(value='ticket'),
        ca='',
        proxy='',
        monitors=1,
    )
)

# Methods that returns None or "internal" methods are not tested
CLIENT_METHODS_INFO: typing.Final[list[AutoSpecMethodInfo]] = [
    # connect returns None
    # Test method
    AutoSpecMethodInfo('test', return_value=True),
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
    AutoSpecMethodInfo('list_ha_groups', return_value=HA_GROUPS),
    # enable_machine_ha return None
    # disable_machine_ha return None
    # set_protection return None
    # get_guest_ip_address
    AutoSpecMethodInfo('get_guest_ip_address', return_value=GUEST_IP_ADDRESS),
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
    # restore_snapshot
    AutoSpecMethodInfo('restore_snapshot', return_value=UPID),
    # get_task
    AutoSpecMethodInfo('get_task', return_value=TASK_STATUS),
    # list_machines
    AutoSpecMethodInfo('list_machines', return_value=VMS_INFO),
    # get_machine_pool_info
    AutoSpecMethodInfo('get_machine_pool_info', method=lambda vmid, poolid, **kwargs: VMS_INFO[vmid - 1]),
    # get_machine_info
    AutoSpecMethodInfo('get_machine_info', method=lambda vmid, *args, **kwargs: VMS_INFO[vmid - 1]),
    # get_machine_configuration
    AutoSpecMethodInfo('get_machine_configuration', method=lambda vmid, **kwargs: VMS_CONFIGURATION[vmid - 1]),
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
    AutoSpecMethodInfo(
        'get_storage',
        method=lambda storage, node, **kwargs: next(filter(lambda s: s.storage == storage, STORAGES)),
    ),
    # list_storages
    AutoSpecMethodInfo(
        'list_storages',
        method=lambda node, **kwargs: (
            (list(filter(lambda s: s.node == node, STORAGES))) if node is not None else STORAGES
        ),
    ),
    # get_node_stats
    AutoSpecMethodInfo(
        'get_node_stats', method=lambda node, **kwargs: next(filter(lambda n: n.name == node, NODE_STATS))
    ),
    # list_pools
    AutoSpecMethodInfo('list_pools', return_value=POOLS),
    # get_pool_info
    AutoSpecMethodInfo(
        'get_pool_info', method=lambda poolid, **kwargs: next(filter(lambda p: p.poolid == poolid, POOLS))
    ),
    # get_console_connection
    AutoSpecMethodInfo('get_console_connection', return_value=CONSOLE_CONNECTION_INFO),
    # journal
    AutoSpecMethodInfo('journal', return_value=['journal line 1', 'journal line 2']),
]

PROVIDER_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'host': 'host',
    'port': 8006,
    'username': 'username',
    'password': 'password',
    'concurrent_creation_limit': 1,
    'concurrent_removal_limit': 1,
    'timeout': 10,
    'start_vmid': 100,
    'macs_range': '00:00:00:00:00:00-00:00:00:ff:ff:ff',
}


SERVICE_LINKED_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'pool': POOLS[0].poolid,
    'ha': HA_GROUPS[0],
    'soft_shutdown': False,
    'machine': VMS_INFO[0].vmid,
    'datastore': STORAGES[0].storage,
    'gpu': VGPUS[0].type,
    'basename': 'base',
    'lenname': 4,
}

SERVICE_FIXED_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'pool': POOLS[0].poolid,
    'machines': [str(VMS_INFO[2].vmid), str(VMS_INFO[3].vmid), str(VMS_INFO[4].vmid)],
    'use_snapshots': True,
}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of ProxmoxClient
    """
    return autospec(client.ProxmoxClient, CLIENT_METHODS_INFO)


@contextlib.contextmanager
def patch_provider_api(
    **kwargs: typing.Any,
) -> typing.Generator[mock.Mock, None, None]:
    client = create_client_mock()
    try:
        mock.patch('uds.services.Proxmox.provider.ProxmoxProvider._api', return_value=client).start()
        yield client
    finally:
        mock.patch.stopall()


def create_provider(**kwargs: typing.Any) -> provider.ProxmoxProvider:
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider.ProxmoxProvider(
        environment=environment.Environment.private_environment(uuid), values=values, uuid=uuid_
    )


def create_service_linked(
    provider: typing.Optional[provider.ProxmoxProvider] = None, **kwargs: typing.Any
) -> service.ProxmoxServiceLinked:
    """
    Create a fixed service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_LINKED_VALUES_DICT.copy()
    values.update(kwargs)
    return service.ProxmoxServiceLinked(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )


def create_service_fixed(
    provider: typing.Optional[provider.ProxmoxProvider] = None, **kwargs: typing.Any
) -> service_fixed.ProxmoxServiceFixed:
    """
    Create a fixed service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_FIXED_VALUES_DICT.copy()
    values.update(kwargs)
    return service_fixed.ProxmoxServiceFixed(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )


def create_publication(
    service: typing.Optional[service.ProxmoxServiceLinked] = None,
    **kwargs: typing.Any,
) -> 'publication.ProxmoxPublication':
    """
    Create a publication
    """
    uuid_ = str(uuid.uuid4())
    return publication.ProxmoxPublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_linked(**kwargs),
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )
