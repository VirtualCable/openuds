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
import enum
import typing
import uuid
import random

from unittest import mock

from uds.core import environment, types
from uds.core.ui.user_interface import gui

from ...utils.autospec import autospec, AutoSpecMethodInfo

from uds.services.OVirt import (
    provider,
    service_linked,
    publication,
    deployment_linked,
)
from uds.services.OVirt.ovirt import client, types as ov_types

T = typing.TypeVar('T')
V = typing.TypeVar('V', bound=enum.Enum)


def from_list(l: typing.List[T], index: int) -> T:
    return l[index % len(l)]


def from_enum(e: typing.Type[V], index: int = -1) -> V:
    if index == -1:
        index = random.randint(0, len(e) - 1)
    return list(e)[index % len(e)]


def get_id(iterable: typing.Iterable[T], id: str) -> T:
    try:
        return next(filter(lambda x: x.id == id, iterable))  # type: ignore
    except StopIteration:
        raise ValueError(f'Id {id} not found in iterable') from None

# Set state helper
def set_attr(obj: T, name: str, value: typing.Any) -> T:
    setattr(obj, name, value)
    return obj

GUEST_IP_ADDRESS: str = '1.0.0.1'

STORAGES_INFO: list[ov_types.StorageInfo] = [
    ov_types.StorageInfo(
        id=f'stid-{i}',
        name=f'storage-{i}',
        type=from_enum(ov_types.StorageType, i),
        available=(i + 4) * 1024 * 1024 * 1024,  # So all storages has enough space
        used=i * 1024 * 1024 * 1024 // 2,
        status=from_list([ov_types.StorageStatus.ACTIVE, ov_types.StorageStatus.INACTIVE], i),
    )
    for i in range(64)
]


DATACENTERS_INFO: list[ov_types.DatacenterInfo] = [
    ov_types.DatacenterInfo(
        name=f'datacenter-{i}',
        id=f'dcid-{i}',
        local_storage=bool(i % 2),
        description='The default Data Center',
        storage=[from_list(STORAGES_INFO, i * 2 + j) for j in range(4)],
    )
    for i in range(4)
]

CLUSTERS_INFO: list[ov_types.ClusterInfo] = [
    ov_types.ClusterInfo(
        name=f'cluster-{i}',
        id=f'clid-{i}',
        datacenter_id=from_list(DATACENTERS_INFO, i // 2).id,
    )
    for i in range(4)
]


VMS_INFO: list[ov_types.VMInfo] = [
    ov_types.VMInfo(
        name=f'vm-{i}',
        id=f'vmid-{i}',
        cluster_id=from_list(CLUSTERS_INFO, i // 6).id,
        usb_enabled=True,
        status=ov_types.VMStatus.DOWN,
    )
    for i in range(32)
]

TEMPLATES_INFO: list[ov_types.TemplateInfo] = [
    ov_types.TemplateInfo(
        id=f'teid-{i}',
        name=f'template-{i}',
        description=f'Template {i} description',
        cluster_id=from_list(CLUSTERS_INFO, i // 8).id,
        status=from_list([ov_types.TemplateStatus.OK, ov_types.TemplateStatus.UNKNOWN], i // 2),
    )
    for i in range(16)
]

SNAPSHOTS_INFO: list[ov_types.SnapshotInfo] = [
    ov_types.SnapshotInfo(
        id=f'snid-{i}',
        name=f'snapshot-{i}',
        description='Active VM',
        status=ov_types.SnapshotStatus.OK,
        type=ov_types.SnapshotType.ACTIVE,
    )
    for i in range(8)
]

CONSOLE_CONNECTION_INFO: types.services.ConsoleConnectionInfo = types.services.ConsoleConnectionInfo(
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


# Methods that returns None or "internal" methods are not tested
# The idea behind this is to allow testing the provider, service and deployment classes
# without the need of a real OpenStack environment
# all methods that returns None are provided by the auto spec mock
CLIENT_METHODS_INFO: typing.Final[list[AutoSpecMethodInfo]] = [
    AutoSpecMethodInfo(client.Client.test, returns=True),
    AutoSpecMethodInfo(client.Client.list_machines, returns=VMS_INFO),
    AutoSpecMethodInfo(
        client.Client.get_machine_info,
        returns=lambda vmid, **kwargs: get_id(VMS_INFO, vmid),  # pyright: ignore
    ),
    AutoSpecMethodInfo(client.Client.list_clusters, returns=CLUSTERS_INFO),
    AutoSpecMethodInfo(
        client.Client.get_cluster_info,
        returns=lambda cluster_id, **kwargs: get_id(CLUSTERS_INFO, cluster_id),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.get_datacenter_info,
        returns=lambda datacenter_id, **kwargs: get_id(  # pyright: ignore
            DATACENTERS_INFO,
            datacenter_id,  # pyright: ignore
        ),
    ),
    AutoSpecMethodInfo(
        client.Client.get_storage_info,
        returns=lambda storage_id, **kwargs: get_id(STORAGES_INFO, storage_id),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.create_template,
        returns=lambda *args, **kwargs: random.choice(TEMPLATES_INFO),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.get_template_info,
        returns=lambda template_id, **kwargs: get_id(TEMPLATES_INFO, template_id),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.deploy_from_template,
        returns=lambda *args, **kwargs: random.choice(VMS_INFO),  # pyright: ignore
    ),
    AutoSpecMethodInfo(client.Client.list_snapshots, returns=SNAPSHOTS_INFO),
    AutoSpecMethodInfo(
        client.Client.get_snapshot_info,
        returns=lambda snapshot_id, **kwargs: get_id(SNAPSHOTS_INFO, snapshot_id),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.get_console_connection_info,
        returns=CONSOLE_CONNECTION_INFO,
    ),
    AutoSpecMethodInfo(
        client.Client.create_snapshot,
        returns=lambda *args, **kwargs: random.choice(SNAPSHOTS_INFO),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.start_machine,
        returns=lambda vmid, **kwargs: set_attr(get_id(VMS_INFO, vmid), 'status', ov_types.VMStatus.UP),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.stop_machine,
        returns=lambda vmid, **kwargs: set_attr(get_id(VMS_INFO, vmid), 'status', ov_types.VMStatus.DOWN),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.shutdown_machine,
        returns=lambda vmid, **kwargs: set_attr(get_id(VMS_INFO, vmid), 'status', ov_types.VMStatus.DOWN),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.remove_machine,
        returns=lambda vmid, **kwargs: set_attr(get_id(VMS_INFO, vmid), 'status', ov_types.VMStatus.UNKNOWN),  # pyright: ignore
    ),
    AutoSpecMethodInfo(
        client.Client.suspend_machine,
        returns=lambda vmid, **kwargs: set_attr(get_id(VMS_INFO, vmid), 'status', ov_types.VMStatus.SUSPENDED),  # pyright: ignore
    ),    
    # connect returns None
    # Test method
    # AutoSpecMethodInfo(client.Client.list_projects, returns=True),
    # AutoSpecMethodInfo(
    #    client.ProxmoxClient.get_node_stats,
    #    returns=lambda node, **kwargs: next(filter(lambda n: n.name == node, NODE_STATS)),  # pyright: ignore
    # ),
]

PROVIDER_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'ovirt_version': '4',
    'host': 'host.example.com',
    'port': 443,  # '443' is the default value
    'username': 'admin@ovirt@internalsso',
    'password': 'the_testing_pass',
    'concurrent_creation_limit': 33,
    'concurrent_removal_limit': 13,
    'timeout': 176,
    'macs_range': '52:54:00:F0:F0:00-52:54:00:F0:FF:FF',
}

SERVICE_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'cluster': CLUSTERS_INFO[0].id,
    'datastore': STORAGES_INFO[0].id,
    'reserved_storage_gb': 2,
    'machine': VMS_INFO[0].id,
    'memory': 256,
    'guaranteed_memory': 256,
    'usb': 'native',
    'display': 'spice',
    'basename': 'noso',
    'lenname': 5,
    'prov_uuid': '',
}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of ProxmoxClient
    """
    return autospec(client.Client, CLIENT_METHODS_INFO)


@contextlib.contextmanager
def patch_provider_api(
    **kwargs: typing.Any,
) -> typing.Generator[mock.Mock, None, None]:
    client = create_client_mock()
    # api is a property, patch it correctly
    with mock.patch(
        'uds.services.OVirt.provider.OVirtProvider.api', new_callable=mock.PropertyMock, **kwargs
    ) as api:
        api.return_value = client
        yield client


def create_provider(**kwargs: typing.Any) -> 'provider.OVirtProvider':
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider.OVirtProvider(
        environment=environment.Environment.private_environment(uuid), values=values, uuid=uuid_
    )


def create_linked_service(
    provider: typing.Optional[provider.OVirtProvider] = None, **kwargs: typing.Any
) -> 'service_linked.OVirtLinkedService':
    """
    Create a service
    """
    values = SERVICE_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return service_linked.OVirtLinkedService(
        provider=provider or create_provider(),
        environment=environment.Environment.private_environment(uuid),
        values=values,
        uuid=uuid_,
    )


def create_publication(service: 'service_linked.OVirtLinkedService') -> publication.OVirtPublication:
    """
    Create a publication
    """
    uuid_ = str(uuid.uuid4())
    pub = publication.OVirtPublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service,
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )
    pub._template_id = random.choice(TEMPLATES_INFO).id
    return pub


def create_linked_userservice(
    service: typing.Optional['service_linked.OVirtLinkedService'] = None,
    publication: typing.Optional[publication.OVirtPublication] = None,
) -> 'deployment_linked.OVirtLinkedUserService':
    """
    Create a linked user service
    """
    uuid_ = str(uuid.uuid4())
    service = service or create_linked_service()
    return deployment_linked.OVirtLinkedUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service,
        publication=publication or create_publication(service),
        uuid=uuid_,
    )
