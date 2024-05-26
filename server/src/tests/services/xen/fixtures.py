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
# pyright: reportConstantRedefinition=false
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import contextlib
import random
import typing
import datetime

from unittest import mock
import uuid

from tests.utils import search_item_by_attr
from uds.core import environment
from uds.core.ui.user_interface import gui

from ...utils.autospec import autospec, AutoSpecMethodInfo

from uds.services.Xen import (
    deployment,
    provider,
    service_fixed,
    publication,
    deployment_fixed,
    service,
)

from uds.services.Xen.xen import types as xen_types, exceptions as xen_exceptions, client

DEF_POOL_NAME: typing.Final[str] = 'TEST_pool_NAME'
DEF_CHANGE_STATE_OPAQUE_REF: typing.Final[str] = 'OpaqueRef:12345678-cdef-abcd-1234-1234567890ab'

DEF_TASK_INFO = xen_types.TaskInfo(
    opaque_ref='OpaqueRef:12345678-1234-1234-1234-1234567890ab',
    uuid='12345678-1234-1234-1234-1234567890ab',
    name='test_task',
    description='Test task description',
    created=datetime.datetime(2024, 1, 1, 0, 0, 0),
    finished=datetime.datetime(2024, 1, 1, 0, 0, 0),
    status=xen_types.TaskStatus.SUCCESS,
    result='Test task result',
    progress=100,
)

DEF_SRS_INFO = [
    xen_types.StorageInfo(
        opaque_ref=f'OpaqueRef:12345678-1234-1234-1234-1234567890{i:02x}',
        uuid=f'12345678-1234-1234-1234-1234567890{i:02x}',
        name=f'test_sr{i:02x}',
        description=f'Test SR description {i:02x}',
        allowed_operations=[
            xen_types.StorageOperations.VDI_CREATE,
            xen_types.StorageOperations.VDI_CLONE,
            xen_types.StorageOperations.VDI_SNAPSHOT,
            xen_types.StorageOperations.VDI_DESTROY,
        ],
        VDIs=[],
        PBDs=[],
        virtual_allocation=i * 1024 * 1024,
        physical_utilisation=i * 1024 * 1024,
        physical_size=i * 1024 * 1024 * 1024,
        type='',
        content_type='',
        shared=True,
    )
    for i in range(8)
]

DEF_NETWORKS_INFO = [
    xen_types.NetworkInfo(
        opaque_ref=f'OpaqueRef:12345678-1234-1234-1234-1234567890{i:02x}',
        uuid=f'12345678-1234-1234-1234-1234567890{i:02x}',
        name=f'test_network{i:02x}',
        description=f'Test network description {i:02x}',
        managed=True,
        VIFs=[],
        PIFs=[],
        is_guest_installer_network=False,
        is_host_internal_management_network=False,
        ip_begin=f'10.0.0.{i}',
        ip_end=f'10.0.0.{i + 1}',
        netmask='255.255.0.0',
    )
    for i in range(8)
]

DEF_VMS_INFO = [
    xen_types.VMInfo(
        opaque_ref=f'OpaqueRef:12345678-1234-1234-1234-1234567890{i:02x}',
        uuid=f'12345678-1234-1234-1234-1234567890{i:02x}',
        name=f'test_vm{i:02x}',
        description=f'Test VM description {i:02x}',
        power_state=xen_types.PowerState.RUNNING,
        is_control_domain=False,
        is_a_template=False,
        snapshot_time=datetime.datetime(2024, 1, 1, 0, 0, 0),
        # For testing, snapshot refers to itself 3 times, just for testing...
        snapshots=[f'OpaqueRef:12345678-1234-1234-1234-1234567890{i:02x}'] * 3,
        allowed_operations=[
            xen_types.VMOperations.START,
            xen_types.VMOperations.CLONE,
            xen_types.VMOperations.COPY,
            xen_types.VMOperations.SNAPSHOT,
        ],
        folder=f'/test_folder_{i//4}',
    )
    for i in range(16)
]

POOL_NAME = DEF_POOL_NAME
CHANGE_STATE_OPAQUE_REF = DEF_CHANGE_STATE_OPAQUE_REF
TASK_INFO = DEF_TASK_INFO

SRS_INFO = DEF_SRS_INFO.copy()
NETWORKS_INFO = DEF_NETWORKS_INFO.copy()
VMS_INFO = DEF_VMS_INFO.copy()


def reset_data() -> None:
    """
    Initialize default values for the module variables
    """
    # Import non local variables
    global TASK_INFO, POOL_NAME, CHANGE_STATE_OPAQUE_REF

    TASK_INFO = DEF_TASK_INFO
    POOL_NAME = DEF_POOL_NAME
    CHANGE_STATE_OPAQUE_REF = DEF_CHANGE_STATE_OPAQUE_REF
    
    SRS_INFO[:] = DEF_SRS_INFO
    NETWORKS_INFO[:] = DEF_NETWORKS_INFO
    VMS_INFO[:] = DEF_VMS_INFO


T = typing.TypeVar('T')


def random_from_list(lst: list[T], *args: typing.Any, **kwargs: typing.Any) -> T:
    """
    Returns a random VM
    """
    return random.choice(lst)


# def set_vm_attr_by_id(attr: str, value: typing.Any, vmid: str) -> None:
#     try:
#         next(filter(lambda x: x.id == vmid, VMS)).__setattr__(attr, value)
#     except StopIteration:
#         raise az_exceptions.AzureNotFoundException(f'Item with id=="{vmid}" not found in list')


# def set_vm_attr(attr: str, value: typing.Any, _resource_group_name: str, name: str) -> None:
#     try:
#         next(filter(lambda x: x.name == name, VMS)).__setattr__(attr, value)
#     except StopIteration:
#         raise az_exceptions.AzureNotFoundException(f'Item with name=="{name}" not found in list')


def search_by_attr(lst: list[T], attribute: str, value: typing.Any, **kwargs: typing.Any) -> T:
    """
    Returns an item from a list of items
    """
    try:
        return search_item_by_attr(lst, attribute, value)
    except ValueError:
        raise xen_exceptions.XenNotFoundError(f'Item with {attribute}=="{value}" not found in list')


# Methods that returns None or "internal" methods are not tested
CLIENT_METHODS_INFO: typing.Final[list[AutoSpecMethodInfo]] = [
    AutoSpecMethodInfo(
        client.XenClient.has_pool,
        returns=True,
    ),
    AutoSpecMethodInfo(
        client.XenClient.get_pool_name,
        returns=POOL_NAME,
    ),
    # Default login and logout, skip them
    AutoSpecMethodInfo(
        client.XenClient.check_login,
        returns=True,
    ),
    # Default test, skip it
    AutoSpecMethodInfo(
        client.XenClient.get_task_info,
        returns=TASK_INFO,
    ),
    AutoSpecMethodInfo(
        client.XenClient.list_srs,
        returns=SRS_INFO,
    ),
    AutoSpecMethodInfo(
        client.XenClient.get_sr_info,
        returns=search_by_attr,
        partial_args=(SRS_INFO, 'opaque_ref'),
    ),
    AutoSpecMethodInfo(
        client.XenClient.list_networks,
        returns=NETWORKS_INFO,
    ),
    AutoSpecMethodInfo(
        client.XenClient.get_network_info,
        returns=search_by_attr,
        partial_args=(NETWORKS_INFO, 'opaque_ref'),
    ),
    AutoSpecMethodInfo(
        client.XenClient.list_vms,
        returns=VMS_INFO,
    ),
    AutoSpecMethodInfo(
        client.XenClient.get_vm_info,
        returns=search_by_attr,
        partial_args=(VMS_INFO, 'opaque_ref'),
    ),
    AutoSpecMethodInfo(
        client.XenClient.start_vm,
        returns=CHANGE_STATE_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.start_vm_sync,
        returns=None,
    ),
    AutoSpecMethodInfo(
        client.XenClient.stop_vm,
        returns=CHANGE_STATE_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.stop_vm_sync,
        returns=None,
    ),
    AutoSpecMethodInfo(
        client.XenClient.reset_vm,
        returns=CHANGE_STATE_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.reset_vm_sync,
        returns=None,
    ),
    AutoSpecMethodInfo(
        client.XenClient.suspend_vm,
        returns=CHANGE_STATE_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.suspend_vm_sync,
        returns=None,
    ),
    AutoSpecMethodInfo(
        client.XenClient.resume_vm,
        returns=CHANGE_STATE_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.resume_vm_sync,
        returns=None,
    ),
    AutoSpecMethodInfo(
        client.XenClient.shutdown_vm,
        returns=CHANGE_STATE_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.shutdown_vm_sync,
        returns=None,
    ),
    
    
]

PROVIDER_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'host': 'test.example.com',
    'port': 443,
    'username': 'root',
    'password': 'some_test_password',
    'concurrent_creation_limit': 18,
    'concurrent_removal_limit': 7,
    'macs_range': '02:99:00:00:00:00-02:AA:00:FF:FF:FF',
    'verify_ssl': True,
    'timeout': 30,
    'host_backup': 'test_backup.example.com',
}


SERVICE_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'datastore': 'OpaqueRef:b2143f92-e234-445c-ad3a-8582f8b893b6',
    'min_space_gb': 32,
    'machine': 'OpaqueRef:dd22df22-f243-4ec4-8b6f-6f31942f4c58',
    'network': 'OpaqueRef:e623a082-01b7-4d4f-a777-6689387e6fd9',
    'memory': 256,
    'shadow': 4,
    'remove_duplicates': True,
    'maintain_on_error': False,
    'try_soft_shutdown': False,
    'basename': 'xcpng8',
    'lenname': 5,
}


SERVICE_FIXED_VALUES_DICT: gui.ValuesDictType = {
    'token': 'TEST_TOKEN_XEN',
    'folder': '/Fixed Pool',
    'machines': [
        'OpaqueRef:f2fa4939-9953-4d65-b5d0-153f867dad32',
        'OpaqueRef:812d6b43-dadb-4b18-a749-aba6f2122d75',
    ],
    'use_snapshots': True,
    'randomize': True,
    'prov_uuid': '',
}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of ProxmoxClient
    """
    return autospec(client.XenClient, CLIENT_METHODS_INFO)


@contextlib.contextmanager
def patched_provider(
    **kwargs: typing.Any,
) -> typing.Generator[provider.XenProvider, None, None]:
    client = create_client_mock()
    provider = create_provider(**kwargs)
    provider._cached_api = client
    yield provider


def create_provider(**kwargs: typing.Any) -> provider.XenProvider:
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider.XenProvider(
        environment=environment.Environment.private_environment(uuid), values=values, uuid=uuid_
    )


def create_service_linked(
    provider: typing.Optional[provider.XenProvider] = None, **kwargs: typing.Any
) -> service.XenLinkedService:
    """
    Create a fixed service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_VALUES_DICT.copy()
    values.update(kwargs)
    return service.XenLinkedService(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )


def create_service_fixed(
    provider: typing.Optional[provider.XenProvider] = None, **kwargs: typing.Any
) -> service_fixed.XenFixedService:
    """
    Create a fixed service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_FIXED_VALUES_DICT.copy()
    values.update(kwargs)
    return service_fixed.XenFixedService(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )


def create_publication(
    service: typing.Optional[service.XenLinkedService] = None,
    **kwargs: typing.Any,
) -> 'publication.XenPublication':
    """
    Create a publication
    """
    uuid_ = str(uuid.uuid4())
    return publication.XenPublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_linked(**kwargs),
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )


def create_userservice_fixed(
    service: typing.Optional[service_fixed.XenFixedService] = None,
) -> deployment_fixed.XenFixedUserService:
    """
    Create a fixed user service, has no publication
    """
    uuid_ = str(uuid.uuid4().hex)
    return deployment_fixed.XenFixedUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_fixed(),
        publication=None,
        uuid=uuid_,
    )


def create_userservice_linked(
    service: typing.Optional[service.XenLinkedService] = None,
    publication: typing.Optional['publication.XenPublication'] = None,
) -> deployment.XenLinkedUserService:
    """
    Create a linked user service
    """
    uuid_ = str(uuid.uuid4())
    return deployment.XenLinkedUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_linked(),
        publication=publication or create_publication(),
        uuid=uuid_,
    )
