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
import datetime
import typing
import uuid
import random

from unittest import mock

from uds.core import environment, types
from uds.core.ui.user_interface import gui

from tests.utils.autospec import autospec, AutoSpecMethodInfo
from tests.utils import helpers, search_item_by_attr

from uds.services.OpenStack import (
    provider,
    provider_legacy,
    service,
    publication,
    deployment,
    service_fixed,
    deployment_fixed,
)
from uds.services.OpenStack.openstack import client, types as openstack_types

AnyOpenStackProvider: typing.TypeAlias = typing.Union[
    provider.OpenStackProvider, provider_legacy.OpenStackProviderLegacy
]


DEF_GUEST_IP_ADDRESS: typing.Final[str] = '1.0.0.1'

DEF_FLAVORS_LIST: typing.Final[list[openstack_types.FlavorInfo]] = [
    openstack_types.FlavorInfo(
        id=f'fid{n}',
        name=f'Flavor name{n}',
        vcpus=n,
        ram=1024 * n,  # MiB
        disk=1024 * 1024 * n,  # GiB
        swap=0,
        is_public=n % 2 == 0,
        disabled=n % 4 == 0,  # Disabled every 4 flavors
    )
    for n in range(1, 16)
]

DEF_AVAILABILITY_ZONES_LIST: typing.Final[list[openstack_types.AvailabilityZoneInfo]] = [
    openstack_types.AvailabilityZoneInfo(
        id=f'az{n}',
        name=f'az name{n}',
        available=n % 2 == 0,
    )
    for n in range(1, 16)
]


DEF_PROJECTS_LIST: typing.Final[list[openstack_types.ProjectInfo]] = [
    openstack_types.ProjectInfo(id=f'pid{n}', name=f'project name{n}') for n in range(1, 16)
]

DEF_REGIONS_LIST: typing.Final[list[openstack_types.RegionInfo]] = [
    openstack_types.RegionInfo(id=f'rid{n}', name=f'region name{n}') for n in range(1, 16)
]

DEF_SERVERS_LIST: typing.Final[list[openstack_types.ServerInfo]] = [
    openstack_types.ServerInfo(
        id=f'sid{n}',
        name=f'server name{n}',
        href=f'https://xxxx/v2/yyyy/servers/zzzzz{n}',
        flavor=DEF_FLAVORS_LIST[(n - 1) % len(DEF_FLAVORS_LIST)].id,
        status=openstack_types.ServerStatus.ACTIVE,
        power_state=openstack_types.PowerState.SHUTDOWN,
        addresses=[
            openstack_types.ServerInfo.AddresInfo(
                version=4,
                ip='172.16.0.148',
                mac='fa:16:3e:0d:fd:91',
                type='fixed',
                network_name='724cc8a5-0ce2-4224-ab1a-f2b84501dcfd',
            )
        ],
        access_addr_ipv4='',
        access_addr_ipv6='',
        fault=None,
        admin_pass='',
    )
    for n in range(1, 32)
]

DEF_VOLUMES_TYPE_LIST: typing.Final[list[openstack_types.VolumeTypeInfo]] = [
    openstack_types.VolumeTypeInfo(
        id=f'vid{n}',
        name=f'volume type name{n}',
    )
    for n in range(1, 16)
]

DEF_VOLUMES_LIST: typing.Final[list[openstack_types.VolumeInfo]] = [
    openstack_types.VolumeInfo(
        id=f'vid{n}',
        name=f'volume name{n}',
        description=f'volume description{n}',
        size=1024 * n,  # GiB
        availability_zone=f'zone{n}',
        bootable=n % 2 == 0,
        encrypted=n % 3 == 0,
        status=openstack_types.VolumeStatus.AVAILABLE,
        created_at=datetime.datetime(2009, 12, 9, 0, 0, 0),
        updated_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
    )
    for n in range(1, 16)
]

DEF_VOLUME_SNAPSHOTS_LIST: typing.Final[list[openstack_types.SnapshotInfo]] = [
    openstack_types.SnapshotInfo(
        id=f'vsid{n}',
        volume_id=DEF_VOLUMES_LIST[(n - 1) % len(DEF_VOLUMES_LIST)].id,
        name=f'volume snapshot name{n}',
        description=f'volume snapshot description{n}',
        status=openstack_types.SnapshotStatus.AVAILABLE,
        size=128 * n,
        created_at=datetime.datetime(2009, 12, 9, 0, 0, 0),
        updated_at=datetime.datetime(2024, 1, 1, 0, 0, 0),
    )
    for n in range(1, 16)
]

DEF_SUBNETS_LIST: typing.Final[list[openstack_types.SubnetInfo]] = [
    openstack_types.SubnetInfo(
        id=f'subnetid{n}',
        name=f'subnet name{n}',
        cidr=f'192.168.{n}.0/24',
        enable_dhcp=n % 2 == 0,
        gateway_ip=f'192.168.{n}.1',
        ip_version=[4, 6][n % 2],
        network_id=f'netid{n}',
    )
    for n in range(1, 16)
]

DEF_NETWORKS_LIST: typing.Final[list[openstack_types.NetworkInfo]] = [
    openstack_types.NetworkInfo(
        id=f'netid{n}',
        name=f'network name{n}',
        status=openstack_types.NetworkStatus.ACTIVE,
        shared=n % 2 == 0,
        subnets=random.sample([s.id for s in DEF_SUBNETS_LIST], 2),
        availability_zones=[
            DEF_AVAILABILITY_ZONES_LIST[(j - 1) % len(DEF_AVAILABILITY_ZONES_LIST)].id for j in range(1, 4)
        ],
    )
    for n in range(1, 16)
]

DEF_SECURITY_GROUPS_LIST: typing.Final[list[openstack_types.SecurityGroupInfo]] = [
    openstack_types.SecurityGroupInfo(
        id=f'sgid{n}',
        name=f'security group name{n}',
        description=f'security group description{n}',
    )
    for n in range(1, 16)
]

DEF_CONSOLE_CONNECTION_INFO: typing.Final[types.services.ConsoleConnectionInfo] = (
    types.services.ConsoleConnectionInfo(
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
)


GUEST_IP_ADDRESS = DEF_GUEST_IP_ADDRESS
FLAVORS_LIST = copy.deepcopy(DEF_FLAVORS_LIST)
AVAILABILITY_ZONES_LIST = copy.deepcopy(DEF_AVAILABILITY_ZONES_LIST)
PROJECTS_LIST = copy.deepcopy(DEF_PROJECTS_LIST)
REGIONS_LIST = copy.deepcopy(DEF_REGIONS_LIST)
SERVERS_LIST = copy.deepcopy(DEF_SERVERS_LIST)
VOLUMES_TYPE_LIST = copy.deepcopy(DEF_VOLUMES_TYPE_LIST)
VOLUMES_LIST = copy.deepcopy(DEF_VOLUMES_LIST)
VOLUME_SNAPSHOTS_LIST = copy.deepcopy(DEF_VOLUME_SNAPSHOTS_LIST)
SUBNETS_LIST = copy.deepcopy(DEF_SUBNETS_LIST)
NETWORKS_LIST = copy.deepcopy(DEF_NETWORKS_LIST)
SECURITY_GROUPS_LIST = copy.deepcopy(DEF_SECURITY_GROUPS_LIST)
CONSOLE_CONNECTION_INFO = copy.deepcopy(DEF_CONSOLE_CONNECTION_INFO)


def clear() -> None:
    global GUEST_IP_ADDRESS, CONSOLE_CONNECTION_INFO
    GUEST_IP_ADDRESS = DEF_GUEST_IP_ADDRESS  # pyright: ignore[reportConstantRedefinition]

    FLAVORS_LIST[:] = copy.deepcopy(DEF_FLAVORS_LIST)
    AVAILABILITY_ZONES_LIST[:] = copy.deepcopy(DEF_AVAILABILITY_ZONES_LIST)
    PROJECTS_LIST[:] = copy.deepcopy(DEF_PROJECTS_LIST)
    REGIONS_LIST[:] = copy.deepcopy(DEF_REGIONS_LIST)
    SERVERS_LIST[:] = copy.deepcopy(DEF_SERVERS_LIST)
    VOLUMES_TYPE_LIST[:] = copy.deepcopy(DEF_VOLUMES_TYPE_LIST)
    VOLUMES_LIST[:] = copy.deepcopy(DEF_VOLUMES_LIST)
    VOLUME_SNAPSHOTS_LIST[:] = copy.deepcopy(DEF_VOLUME_SNAPSHOTS_LIST)
    SUBNETS_LIST[:] = copy.deepcopy(DEF_SUBNETS_LIST)
    NETWORKS_LIST[:] = copy.deepcopy(DEF_NETWORKS_LIST)
    SECURITY_GROUPS_LIST[:] = copy.deepcopy(DEF_SECURITY_GROUPS_LIST)
    CONSOLE_CONNECTION_INFO = copy.deepcopy(  # pyright: ignore[reportConstantRedefinition]
        DEF_CONSOLE_CONNECTION_INFO
    )


T = typing.TypeVar('T')


def set_all_vms_status(status: openstack_types.ServerStatus) -> None:
    for vm in SERVERS_LIST:
        vm.status = status


def search_id(lst: list[T], id: str, *args: typing.Any, **kwargs: typing.Any) -> T:
    return search_item_by_attr(lst, 'id', id)


def set_vm_state(id: str, state: openstack_types.PowerState, **kwargs: typing.Any) -> str:
    vm = search_id(SERVERS_LIST, id)
    vm.power_state = state
    return str(state) + '_task_uuid'


def random_element(lst: list[T], *args: typing.Any, **kwargs: typing.Any) -> T:
    return random.choice(lst)


# Methods that returns None or "internal" methods are not tested
# The idea behind this is to allow testing the provider, service and deployment classes
# without the need of a real OpenStack environment
CLIENT_METHODS_INFO: typing.Final[list[AutoSpecMethodInfo]] = [
    AutoSpecMethodInfo(client.OpenStackClient.get_project_id, returns=PROJECTS_LIST[0].id),
    AutoSpecMethodInfo(client.OpenStackClient.list_flavors, returns=FLAVORS_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_availability_zones, returns=AVAILABILITY_ZONES_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_projects, returns=PROJECTS_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_regions, returns=REGIONS_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_servers, returns=SERVERS_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_volumes, returns=VOLUMES_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_networks, returns=NETWORKS_LIST),
    AutoSpecMethodInfo(client.OpenStackClient.list_security_groups, returns=SECURITY_GROUPS_LIST),
    AutoSpecMethodInfo(
        client.OpenStackClient.get_server_info,
        returns=search_id,
        partial_args=(SERVERS_LIST,),
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.get_volume_info,
        returns=search_id,
        partial_args=(VOLUMES_LIST,),
    ),  # pyright: ignore
    AutoSpecMethodInfo(
        client.OpenStackClient.get_snapshot_info,
        returns=search_id,
        partial_args=(VOLUME_SNAPSHOTS_LIST,),
    ),  # pyright: ignore
    AutoSpecMethodInfo(
        client.OpenStackClient.create_snapshot,
        returns=random_element,
        partial_args=(VOLUME_SNAPSHOTS_LIST,),
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.create_server_from_snapshot,
        returns=random_element,
        partial_args=(SERVERS_LIST,),
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.test_connection,
        returns=True,
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.is_available,
        returns=True,
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.start_server,
        returns=set_vm_state,
        partial_kwargs={'state': openstack_types.PowerState.RUNNING},
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.stop_server,
        returns=set_vm_state,
        partial_kwargs={'state': openstack_types.PowerState.SHUTDOWN},
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.reboot_server,
        returns=set_vm_state,
        partial_kwargs={'state': openstack_types.PowerState.RUNNING},
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.suspend_server,
        returns=set_vm_state,
        partial_kwargs={'state': openstack_types.PowerState.SUSPENDED},
    ),
    AutoSpecMethodInfo(
        client.OpenStackClient.resume_server,
        returns=set_vm_state,
        partial_kwargs={'state': openstack_types.PowerState.RUNNING},
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
    'endpoint': 'https://host',
    'auth_method': 'application_credential',
    'access': 'public',
    'domain': 'domain',
    'username': 'username',
    'password': 'password',
    'concurrent_creation_limit': 1,
    'concurrent_removal_limit': 1,
    'timeout': 10,
    'project_id': '',  # No project_id allowed if using application_credential, it's implicit
    'region': 'region',
    'use_subnets_name': False,
    'https_proxy': 'https_proxy',
    'verify_ssl': False,
}

PROVIDER_LEGACY_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'host': 'host',
    'port': 5000,
    'ssl': False,
    'access': 'public',
    'domain': 'domain',
    'username': 'username',
    'password': 'password',
    'concurrent_creation_limit': 1,
    'concurrent_removal_limit': 1,
    'timeout': 10,
    'https_proxy': 'https_proxy',
}


SERVICE_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'region': random.choice(DEF_REGIONS_LIST).id,
    'project': random.choice(DEF_PROJECTS_LIST).id,
    'availability_zone': random.choice(DEF_AVAILABILITY_ZONES_LIST).id,
    'volume': random.choice(DEF_VOLUMES_LIST).id,
    'network': random.choice(DEF_NETWORKS_LIST).id,
    'flavor': random.choice(DEF_FLAVORS_LIST).id,
    'security_groups': [random.choice(DEF_SECURITY_GROUPS_LIST).id],
    'basename': 'bname',
    'lenname': 5,
    'maintain_on_error': False,
    'try_soft_shutdown': False,
    'prov_uuid': 'prov_uuid',
}

SERVICES_FIXED_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'token': 'token',
    'region': random.choice(DEF_REGIONS_LIST).id,
    'project': random.choice(DEF_PROJECTS_LIST).id,
    'machines': [i.id for i in random.sample(DEF_SERVERS_LIST, 10)],
    # 'prov_uuid': str(uuid.uuid4()),  # Not stored on db, so not needed
}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of ProxmoxClient
    """
    return autospec(client.OpenStackClient, CLIENT_METHODS_INFO)


@contextlib.contextmanager
def patched_provider(
    **kwargs: typing.Any,
) -> typing.Generator[provider.OpenStackProvider, None, None]:
    client = create_client_mock()
    provider = create_provider(**kwargs)
    with mock.patch.object(provider, 'api') as api:
        provider.do_log = mock.MagicMock()  # Avoid logging
        api.return_value = client
        yield provider


@contextlib.contextmanager
def patched_provider_legacy(
    **kwargs: typing.Any,
) -> typing.Generator[provider_legacy.OpenStackProviderLegacy, None, None]:
    client = create_client_mock()
    provider = create_provider_legacy(**kwargs)
    with mock.patch.object(provider, 'api') as api:
        api.return_value = client
        yield provider


def create_provider(**kwargs: typing.Any) -> provider.OpenStackProvider:
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider.OpenStackProvider(
        environment=environment.Environment.private_environment(uuid_), values=values, uuid=uuid_
    )


def create_provider_legacy(**kwargs: typing.Any) -> provider_legacy.OpenStackProviderLegacy:
    """
    Create a provider legacy
    """
    values = PROVIDER_LEGACY_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider_legacy.OpenStackProviderLegacy(
        environment=environment.Environment.private_environment(uuid_), values=values, uuid=uuid_
    )


def create_live_service(provider: AnyOpenStackProvider, **kwargs: typing.Any) -> service.OpenStackLiveService:
    """
    Create a service
    """
    values = SERVICE_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    srvc = service.OpenStackLiveService(
        provider=provider,
        environment=environment.Environment.private_environment(uuid_),
        values=values,
        uuid=uuid_,
    )
    service_db_mock = mock.MagicMock()
    service_db_mock.uuid = uuid_
    service_db_mock.name = 'ServiceName'
    srvc.db_obj = mock.MagicMock()
    srvc.db_obj.return_value = service_db_mock
    return srvc


def create_publication(service: service.OpenStackLiveService) -> publication.OpenStackLivePublication:
    """
    Create a publication
    """
    uuid_ = str(uuid.uuid4())
    pub = publication.OpenStackLivePublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service,
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )
    pub._vmid = helpers.random_string(8)
    return pub


def create_live_userservice(
    service: service.OpenStackLiveService,
    publication: typing.Optional[publication.OpenStackLivePublication] = None,
) -> deployment.OpenStackLiveUserService:
    """
    Create a linked user service
    """
    uuid_ = str(uuid.uuid4())
    return deployment.OpenStackLiveUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service,
        publication=publication or create_publication(service),
        uuid=uuid_,
    )


def create_fixed_service(
    provider: AnyOpenStackProvider, **kwargs: typing.Any
) -> service_fixed.OpenStackServiceFixed:
    """
    Create a fixed service
    """
    values = SERVICES_FIXED_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return service_fixed.OpenStackServiceFixed(
        provider=provider,
        environment=environment.Environment.private_environment(uuid_),
        values=values,
        uuid=uuid_,
    )


# Fixed has no publications


def create_fixed_userservice(
    service: service_fixed.OpenStackServiceFixed,
) -> deployment_fixed.OpenStackUserServiceFixed:
    """
    Create a linked user service
    """
    uuid_ = str(uuid.uuid4())
    return deployment_fixed.OpenStackUserServiceFixed(
        environment=environment.Environment.private_environment(uuid_),
        service=service,
        uuid=uuid_,
    )
