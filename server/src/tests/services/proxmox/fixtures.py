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
import copy
import functools
import typing
import datetime

from unittest import mock
import uuid

from uds.core import types, environment
from uds.core.ui.user_interface import gui
import uds.services.Proxmox.proxmox.client

from ...utils.autospec import autospec, AutoSpecMethodInfo

from uds.services.Proxmox import (
    deployment_linked,
    provider,
    service_fixed,
    publication,
    deployment_fixed,
    service_linked,
)

from uds.services.Proxmox.proxmox import types as prox_types

DEF_NODES: list[prox_types.Node] = [
    prox_types.Node(name='node0', online=True, local=True, nodeid=1, ip='0.0.0.1', level='level', id='id'),
    prox_types.Node(name='node1', online=True, local=True, nodeid=2, ip='0.0.0.2', level='level', id='id'),
]

DEF_NODE_STATS: list[prox_types.NodeStats] = [
    prox_types.NodeStats(
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
    prox_types.NodeStats(
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


DEF_CLUSTER_INFO: prox_types.ClusterInfo = prox_types.ClusterInfo(
    cluster=prox_types.Cluster(name='name', version='version', id='id', nodes=2, quorate=1),
    nodes=DEF_NODES,
)

DEF_STORAGES: list[prox_types.StorageInfo] = [
    prox_types.StorageInfo(
        node=DEF_NODES[i % len(DEF_NODES)].name,
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


DEF_VGPUS: list[prox_types.VGPUInfo] = [
    prox_types.VGPUInfo(
        name='name_1',
        description='description_1',
        device='device_1',
        available=True,
        type='gpu_type_1',
    ),
    prox_types.VGPUInfo(
        name='name_2',
        description='description_2',
        device='device_2',
        available=False,
        type='gpu_type_2',
    ),
    prox_types.VGPUInfo(
        name='name_3',
        description='description_3',
        device='device_3',
        available=True,
        type='gpu_type_3',
    ),
]

DEF_HA_GROUPS: list[str] = [
    'ha_group_1',
    'ha_group_2',
    'ha_group_3',
    'ha_group_4',
]

DEF_VMS_INFO: list[prox_types.VMInfo] = [
    prox_types.VMInfo(
        status='stopped',
        vmid=i,
        node=DEF_NODES[i % len(DEF_NODES)].name,
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
        vgpu_type=DEF_VGPUS[i % len(DEF_VGPUS)].type,
    )
    for i in range(1, 16)
]

DEF_VMS_CONFIGURATION: list[prox_types.VMConfiguration] = [
    prox_types.VMConfiguration(
        name=f'vm_name_{i}',
        vga='cirrus',
        sockets=1,
        cores=1,
        vmgenid='vmgenid',
        digest='digest',
        networks=[
            prox_types.NetworkConfiguration(
                net='net', type='type', mac=f'{i:02x}:{i+1:02x}:{i+2:02x}:{i+3:02x}:{i+4:02x}:{i+5:02x}'
            )
        ],
        tpmstate0='tpmstate0',
        template=bool(i > 8),  # Last two are templates
    )
    for i in range(10)
]


DEF_UPID: prox_types.UPID = prox_types.UPID(
    node=DEF_NODES[0].name,
    pid=1,
    pstart=1,
    starttime=datetime.datetime.now(),
    type='type',
    vmid=DEF_VMS_INFO[0].vmid,
    user='user',
    upid='upid',
)


DEF_VM_CREATION_RESULT: prox_types.VmCreationResult = prox_types.VmCreationResult(
    node=DEF_NODES[0].name,
    vmid=DEF_VMS_INFO[0].vmid,
    upid=DEF_UPID,
)


DEF_SNAPSHOTS_INFO: list[prox_types.SnapshotInfo] = [
    prox_types.SnapshotInfo(
        name=f'snap_name_{i}',
        description=f'snap desription{i}',
        parent=f'snap_parent_{i}',
        snaptime=int(datetime.datetime.now().timestamp()),
        vmstate=bool(i % 2),
    )
    for i in range(10)
]

DEF_TASK_STATUS = prox_types.TaskStatus(
    node=DEF_NODES[0].name,
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

DEF_POOL_MEMBERS: list[prox_types.PoolMemberInfo] = [
    prox_types.PoolMemberInfo(
        id=f'id_{i}',
        node=DEF_NODES[i % len(DEF_NODES)].name,
        storage=DEF_STORAGES[i % len(DEF_STORAGES)].storage,
        type='type',
        vmid=DEF_VMS_INFO[i % len(DEF_VMS_INFO)].vmid,
        vmname=DEF_VMS_INFO[i % len(DEF_VMS_INFO)].name or '',
    )
    for i in range(10)
]

DEF_POOLS: list[prox_types.PoolInfo] = [
    prox_types.PoolInfo(
        poolid=f'pool_{i}',
        comments=f'comments_{i}',
        members=DEF_POOL_MEMBERS,
    )
    for i in range(10)
]

DEF_GUEST_IP_ADDRESS: str = '1.0.0.1'

DEF_CONSOLE_CONNECTION_INFO: types.services.ConsoleConnectionInfo = types.services.ConsoleConnectionInfo(
    type='spice',
    address=DEF_GUEST_IP_ADDRESS,
    port=5900,
    secure_port=5901,
    cert_subject='',
    ticket=types.services.ConsoleConnectionTicket(value='ticket'),
    ca='',
    proxy='',
    monitors=1,
)

# clone values to avoid modifying the original ones
NODES: list[prox_types.Node] = copy.deepcopy(DEF_NODES)
NODE_STATS: list[prox_types.NodeStats] = copy.deepcopy(DEF_NODE_STATS)
CLUSTER_INFO: prox_types.ClusterInfo = copy.deepcopy(DEF_CLUSTER_INFO)
STORAGES: list[prox_types.StorageInfo] = copy.deepcopy(DEF_STORAGES)
VGPUS: list[prox_types.VGPUInfo] = copy.deepcopy(DEF_VGPUS)
HA_GROUPS: list[str] = copy.deepcopy(DEF_HA_GROUPS)
VMS_INFO: list[prox_types.VMInfo] = copy.deepcopy(DEF_VMS_INFO)
VMS_CONFIGURATION: list[prox_types.VMConfiguration] = copy.deepcopy(DEF_VMS_CONFIGURATION)
UPID: prox_types.UPID = copy.deepcopy(DEF_UPID)
VM_CREATION_RESULT: prox_types.VmCreationResult = copy.deepcopy(DEF_VM_CREATION_RESULT)
SNAPSHOTS_INFO: list[prox_types.SnapshotInfo] = copy.deepcopy(DEF_SNAPSHOTS_INFO)
TASK_STATUS: prox_types.TaskStatus = copy.deepcopy(DEF_TASK_STATUS)
POOLS: list[prox_types.PoolInfo] = copy.deepcopy(DEF_POOLS)
GUEST_IP_ADDRESS: str = copy.deepcopy(DEF_GUEST_IP_ADDRESS)
CONSOLE_CONNECTION_INFO: types.services.ConsoleConnectionInfo = copy.deepcopy(DEF_CONSOLE_CONNECTION_INFO)


def clear() -> None:
    """
    Resets all values to the default ones
    """
    global CLUSTER_INFO, UPID, VM_CREATION_RESULT, TASK_STATUS, GUEST_IP_ADDRESS, CONSOLE_CONNECTION_INFO

    NODES[:] = copy.deepcopy(DEF_NODES)
    NODE_STATS[:] = copy.deepcopy(DEF_NODE_STATS)
    CLUSTER_INFO = copy.deepcopy(DEF_CLUSTER_INFO)  # pyright: ignore
    STORAGES[:] = copy.deepcopy(DEF_STORAGES)
    STORAGES[:] = copy.deepcopy(DEF_STORAGES)
    VGPUS[:] = copy.deepcopy(DEF_VGPUS)
    HA_GROUPS[:] = copy.deepcopy(DEF_HA_GROUPS)
    VMS_INFO[:] = copy.deepcopy(DEF_VMS_INFO)
    VMS_CONFIGURATION[:] = copy.deepcopy(DEF_VMS_CONFIGURATION)
    UPID = copy.deepcopy(DEF_UPID)  # pyright: ignore
    VM_CREATION_RESULT = copy.deepcopy(DEF_VM_CREATION_RESULT)  # pyright: ignore
    SNAPSHOTS_INFO[:] = copy.deepcopy(DEF_SNAPSHOTS_INFO)
    TASK_STATUS = copy.deepcopy(DEF_TASK_STATUS)  # pyright: ignore
    POOLS[:] = copy.deepcopy(DEF_POOLS)
    GUEST_IP_ADDRESS = copy.deepcopy(DEF_GUEST_IP_ADDRESS)  # pyright: ignore
    CONSOLE_CONNECTION_INFO = copy.deepcopy(DEF_CONSOLE_CONNECTION_INFO)  # pyright: ignore


def replace_vm_info(vmid: int, **kwargs: typing.Any) -> prox_types.UPID:
    """
    Set the values of VMS_INFO[vmid - 1]
    """
    for i in range(len(VMS_INFO)):
        if VMS_INFO[i].vmid == vmid:
            for k, v in kwargs.items():
                setattr(VMS_INFO[i], k, v)
            break
    return UPID


def replacer_vm_info(**kwargs: typing.Any) -> typing.Callable[..., prox_types.UPID]:
    return functools.partial(replace_vm_info, **kwargs)


T = typing.TypeVar('T')


def returner(value: T, *args: typing.Any, **kwargs: typing.Any) -> typing.Callable[..., T]:
    def inner(*args: typing.Any, **kwargs: typing.Any) -> T:
        return value

    return inner


# Methods that returns None or "internal" methods are not tested
CLIENT_METHODS_INFO: list[AutoSpecMethodInfo] = [
    # connect returns None
    # Test method
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.test, returns=True),
    # get_cluster_info
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_cluster_info, returns=CLUSTER_INFO
    ),
    # get_next_vmid
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.get_next_vmid, returns=1),
    # is_vmid_available
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.is_vmid_available, returns=True),
    # get_node_networks, not called never (ensure it's not called by mistake)
    # list_node_gpu_devices
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.list_node_gpu_devices,
        returns=['gpu_dev_1', 'gpu_dev_2'],
    ),
    # list_node_vgpus
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.list_node_vgpus, returns=VGPUS),
    # node_has_vgpus_available
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.node_has_vgpus_available, returns=True
    ),
    # get_best_node_for_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_best_node_for_vm, returns=NODE_STATS[0]
    ),
    # clone_machine
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.clone_vm, returns=VM_CREATION_RESULT),
    # list_ha_groups
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.list_ha_groups, returns=HA_GROUPS),
    # enable_machine_ha return None
    # disable_machine_ha return None
    # set_protection return None
    # get_guest_ip_address
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_guest_ip_address, returns=GUEST_IP_ADDRESS
    ),
    # remove_machine
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.delete_vm, returns=UPID),
    # list_snapshots
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.list_snapshots, returns=SNAPSHOTS_INFO
    ),
    # supports_snapshot
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.supports_snapshot, returns=True),
    # create_snapshot
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.create_snapshot, returns=UPID),
    # remove_snapshot
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.remove_snapshot, returns=UPID),
    # restore_snapshot
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.restore_snapshot, returns=UPID),
    # get_task
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_task,
        returns=lambda *args, **kwargs: TASK_STATUS,  # pyright: ignore
    ),
    # list_machines
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.list_vms, returns=VMS_INFO),
    # get_vm_pool_info
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_vm_pool_info,
        returns=lambda vmid, poolid, **kwargs: VMS_INFO[vmid - 1],  # pyright: ignore
    ),
    # get_machine_info
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_vm_info,
        returns=lambda vmid, *args, **kwargs: VMS_INFO[vmid - 1],  # pyright: ignore
    ),
    # get_machine_configuration
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_vm_config,
        returns=lambda vmid, **kwargs: VMS_CONFIGURATION[vmid - 1],  # pyright: ignore
    ),
    # enable_machine_ha return None
    # start_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.start_vm, returns=replacer_vm_info(status='running')
    ),
    # stop_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.stop_vm, returns=replacer_vm_info(status='stopped')
    ),
    # reset_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.reset_vm, returns=replacer_vm_info(status='stopped')
    ),
    # suspend_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.suspend_vm,
        returns=replacer_vm_info(status='suspended'),
    ),
    # resume_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.resume_vm,
        returns=replacer_vm_info(status='running'),
    ),
    # shutdown_machine
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.shutdown_vm,
        returns=replacer_vm_info(status='stopped'),
    ),
    # convert_to_template
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.convert_vm_to_template,
        returns=replacer_vm_info(template=True),
    ),
    # get_storage
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_storage_info,
        returns=lambda storage, node, **kwargs: next(  # pyright: ignore
            filter(lambda s: s.storage == storage, STORAGES)  # pyright: ignore
        ),
    ),
    # list_storages
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.list_storages,
        returns=lambda node, **kwargs: (  # pyright: ignore
            (list(filter(lambda s: s.node == node, STORAGES)))  # pyright: ignore
            if node is not None
            else STORAGES  # pyright: ignore
        ),
    ),
    # get_node_stats
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_node_stats,
        returns=lambda node, **kwargs: next(  # pyright: ignore
            filter(lambda n: n.name == node, NODE_STATS)  # pyright: ignore
        ),
    ),
    # list_pools
    AutoSpecMethodInfo(uds.services.Proxmox.proxmox.client.ProxmoxClient.list_pools, returns=POOLS),
    # get_pool_info
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_pool_info,
        returns=lambda poolid, **kwargs: next(  # pyright: ignore
            filter(lambda p: p.poolid == poolid, POOLS)  # pyright: ignore
        ),
    ),
    # get_console_connection
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.get_console_connection,
        returns=CONSOLE_CONNECTION_INFO,
    ),
    # journal
    AutoSpecMethodInfo(
        uds.services.Proxmox.proxmox.client.ProxmoxClient.journal, returns=['journal line 1', 'journal line 2']
    ),
]

PROVIDER_VALUES_DICT: gui.ValuesDictType = {
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


SERVICE_LINKED_VALUES_DICT: gui.ValuesDictType = {
    'pool': POOLS[0].poolid,
    'ha': HA_GROUPS[0],
    'try_soft_shutdown': False,
    'machine': VMS_INFO[0].vmid,
    'datastore': STORAGES[0].storage,
    'gpu': VGPUS[0].type,
    'basename': 'base',
    'lenname': 4,
    'prov_uuid': '',
}


SERVICE_FIXED_VALUES_DICT: gui.ValuesDictType = {
    'token': '',
    'pool': POOLS[0].poolid,
    'machines': [str(VMS_INFO[2].vmid), str(VMS_INFO[3].vmid), str(VMS_INFO[4].vmid)],
    'use_snapshots': True,
    'prov_uuid': '',
}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of ProxmoxClient
    """
    return autospec(uds.services.Proxmox.proxmox.client.ProxmoxClient, CLIENT_METHODS_INFO)


@contextlib.contextmanager
def patched_provider(
    **kwargs: typing.Any,
) -> typing.Generator[provider.ProxmoxProvider, None, None]:
    client = create_client_mock()
    provider = create_provider(**kwargs)
    with mock.patch.object(provider, 'api') as api:
        api.return_value = client
        yield provider


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
) -> service_linked.ProxmoxServiceLinked:
    """
    Create a fixed service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_LINKED_VALUES_DICT.copy()
    values.update(kwargs)
    srvc = service_linked.ProxmoxServiceLinked(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )
    service_db_mock = mock.MagicMock()
    service_db_mock.uuid = uuid_
    service_db_mock.name = 'ServiceName'
    srvc.db_obj = mock.MagicMock()
    srvc.db_obj.return_value = service_db_mock
    return srvc


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
    service: typing.Optional[service_linked.ProxmoxServiceLinked] = None,
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


def create_userservice_fixed(
    service: typing.Optional[service_fixed.ProxmoxServiceFixed] = None,
) -> deployment_fixed.ProxmoxUserServiceFixed:
    """
    Create a fixed user service, has no publication
    """
    # def __init__(
    #     self,
    #     environment: 'Environment',
    #     service: 'services.Service',
    #     publication: typing.Optional['services.Publication'] = None,
    #     osmanager: typing.Optional['osmanagers.OSManager'] = None,
    #     uuid: str = '',
    # ):

    uuid_ = str(uuid.uuid4().hex)
    return deployment_fixed.ProxmoxUserServiceFixed(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_fixed(),
        publication=None,
        uuid=uuid_,
    )


def create_userservice_linked(
    service: typing.Optional[service_linked.ProxmoxServiceLinked] = None,
    publication: typing.Optional['publication.ProxmoxPublication'] = None,
) -> deployment_linked.ProxmoxUserserviceLinked:
    """
    Create a linked user service
    """
    uuid_ = str(uuid.uuid4())
    return deployment_linked.ProxmoxUserserviceLinked(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_linked(),
        publication=publication or create_publication(),
        uuid=uuid_,
    )


# Other helpers
def set_all_vm_state(state: str) -> None:
    # Set machine state for fixture to stopped
    for i in VMS_INFO:
        i.status = state
