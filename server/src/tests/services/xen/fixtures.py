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
import dataclasses
import random
import typing
import datetime

from unittest import mock
import uuid

from tests.utils import search_item_by_attr, filter_list_by_attr
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
DEF_GENERAL_OPAQUE_REF: typing.Final[str] = 'OpaqueRef:12345678-cdef-abcd-1234-1234567890ab'
DEF_GENERAL_IP: typing.Final[str] = '10.11.12.13'
DEF_GENERAL_MAC: typing.Final[str] = '02:04:06:08:0A:0C'

DEF_SRS_INFO: typing.Final[list[xen_types.StorageInfo]] = [
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
        virtual_allocation=(i + 32) * 1024,
        physical_utilisation=i * 1024,
        physical_size=(i + 32) * 1024,
        type='',
        content_type='',
        shared=True,
    )
    for i in range(8)
]

LOW_SPACE_SR_INFO: typing.Final[xen_types.StorageInfo] = xen_types.StorageInfo(
    opaque_ref='OpaqueRef:12345678-1234-1234-1234-1234567890ff',
    uuid='12345678-1234-1234-1234-1234567890ff',
    name='low_space_sr',
    description='Low space SR description',
    allowed_operations=[],
    VDIs=[],
    PBDs=[],
    virtual_allocation=32 * 1024,
    physical_utilisation=32 * 1024,
    physical_size=32 * 1024,
    type='',
    content_type='',
    shared=True,
)


DEF_NETWORKS_INFO: typing.Final[list[xen_types.NetworkInfo]] = [
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

DEF_VMS_INFO: typing.Final[list[xen_types.VMInfo]] = [
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
        folder=f'/test_folder_{i//6}',
    )
    for i in range(24)
]

DEF_TASK_INFO: typing.Final[xen_types.TaskInfo] = xen_types.TaskInfo(
    opaque_ref='OpaqueRef:12345678-1234-1234-1234-1234567890ab',
    uuid='12345678-1234-1234-1234-1234567890ab',
    name='test_task',
    description='Test task description',
    created=datetime.datetime(2024, 1, 1, 0, 0, 0),
    finished=datetime.datetime(2024, 1, 1, 0, 0, 0),
    status=xen_types.TaskStatus.SUCCESS,
    result=DEF_VMS_INFO[0].opaque_ref,
    progress=100,
)

DEF_FOLDERS: list[str] = list(set(vm.folder for vm in DEF_VMS_INFO))

POOL_NAME = DEF_POOL_NAME
GENERAL_OPAQUE_REF = DEF_GENERAL_OPAQUE_REF
TASK_INFO = dataclasses.replace(DEF_TASK_INFO)  # Copy the object
GENERAL_IP = DEF_GENERAL_IP
GENERAL_MAC = DEF_GENERAL_MAC

SRS_INFO = DEF_SRS_INFO.copy()
NETWORKS_INFO = DEF_NETWORKS_INFO.copy()
VMS_INFO = DEF_VMS_INFO.copy()
FOLDERS = DEF_FOLDERS.copy()


def clean() -> None:
    """
    Initialize default values for the module variables
    """
    # Import non local variables
    global TASK_INFO, POOL_NAME, GENERAL_OPAQUE_REF, GENERAL_IP, GENERAL_MAC

    TASK_INFO = dataclasses.replace(DEF_TASK_INFO)
    POOL_NAME = DEF_POOL_NAME
    GENERAL_OPAQUE_REF = DEF_GENERAL_OPAQUE_REF
    GENERAL_IP = DEF_GENERAL_IP
    GENERAL_MAC = DEF_GENERAL_MAC

    SRS_INFO[:] = DEF_SRS_INFO
    NETWORKS_INFO[:] = DEF_NETWORKS_INFO
    VMS_INFO[:] = DEF_VMS_INFO
    DEF_FOLDERS[:] = list(set(vm.folder for vm in DEF_VMS_INFO))


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


def set_vm_state(is_async: bool, state: xen_types.PowerState, vmid: str) -> 'str|None':
    """
    Set the power state of a VM
    """
    try:
        vm = search_item_by_attr(VMS_INFO, 'opaque_ref', vmid)
        vm.power_state = state
    except ValueError:
        raise xen_exceptions.XenNotFoundError(f'Item with opaque_ref=="{vmid}" not found in list')

    if is_async:
        return None
    return GENERAL_OPAQUE_REF


def set_all_vm_state(state: xen_types.PowerState) -> None:
    """
    Set the power state of all VMs
    """
    for vm in VMS_INFO:
        vm.power_state = state

def task_info(*args: typing.Any, **kwargs: typing.Any) -> xen_types.TaskInfo:
    return TASK_INFO

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
        returns=task_info,
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
        returns=set_vm_state,
        partial_args=(False, xen_types.PowerState.RUNNING),
    ),
    AutoSpecMethodInfo(
        client.XenClient.start_vm_sync,
        returns=set_vm_state,
        partial_args=(True, xen_types.PowerState.RUNNING),
    ),
    AutoSpecMethodInfo(
        client.XenClient.stop_vm,
        returns=set_vm_state,
        partial_args=(False, xen_types.PowerState.HALTED),
    ),
    AutoSpecMethodInfo(
        client.XenClient.stop_vm_sync,
        returns=set_vm_state,
        partial_args=(True, xen_types.PowerState.HALTED),
    ),
    AutoSpecMethodInfo(
        client.XenClient.reset_vm,
        returns=GENERAL_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.reset_vm_sync,
        returns=None,
    ),
    AutoSpecMethodInfo(
        client.XenClient.suspend_vm,
        returns=set_vm_state,
        partial_args=(False, xen_types.PowerState.SUSPENDED),
    ),
    AutoSpecMethodInfo(
        client.XenClient.suspend_vm_sync,
        returns=set_vm_state,
        partial_args=(True, xen_types.PowerState.SUSPENDED),
    ),
    AutoSpecMethodInfo(
        client.XenClient.resume_vm,
        returns=set_vm_state,
        partial_args=(False, xen_types.PowerState.RUNNING),
    ),
    AutoSpecMethodInfo(
        client.XenClient.resume_vm_sync,
        returns=set_vm_state,
        partial_args=(True, xen_types.PowerState.RUNNING),
    ),
    AutoSpecMethodInfo(
        client.XenClient.shutdown_vm,
        returns=set_vm_state,
        partial_args=(False, xen_types.PowerState.HALTED),
    ),
    AutoSpecMethodInfo(
        client.XenClient.shutdown_vm_sync,
        returns=set_vm_state,
        partial_args=(True, xen_types.PowerState.HALTED),
    ),
    AutoSpecMethodInfo(
        client.XenClient.clone_vm,
        returns=GENERAL_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.get_first_ip,
        returns=GENERAL_IP,
    ),
    AutoSpecMethodInfo(
        client.XenClient.get_first_mac,
        returns=GENERAL_MAC,
    ),
    AutoSpecMethodInfo(
        client.XenClient.provision_vm,
        returns=GENERAL_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.create_snapshot,
        returns=GENERAL_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.delete_snapshot,
        returns=GENERAL_OPAQUE_REF,
    ),
    AutoSpecMethodInfo(
        client.XenClient.restore_snapshot,
        returns=GENERAL_OPAQUE_REF,
    ),
    # Returns vms as snapshots. As we are not going to really use them, we can return the same as VMS_INFO
    AutoSpecMethodInfo(client.XenClient.list_snapshots, returns=VMS_INFO),
    AutoSpecMethodInfo(
        client.XenClient.list_folders,
        returns=FOLDERS,
    ),
    AutoSpecMethodInfo(
        client.XenClient.list_vms_in_folder,
        returns=filter_list_by_attr,
        partial_args=(VMS_INFO, 'folder'),
    ),
    AutoSpecMethodInfo(
        client.XenClient.start_deploy_from_template,
        returns=GENERAL_OPAQUE_REF,
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
    'datastore': random.choice(SRS_INFO).opaque_ref,
    'min_space_gb': 32,
    'machine': random.choice(VMS_INFO).opaque_ref,
    'network': random.choice(NETWORKS_INFO).opaque_ref,
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
    'folder': FOLDERS[0],
    'machines': random.sample([i.opaque_ref for i in VMS_INFO if i.folder == FOLDERS[0]], 2),
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
    with mock.patch('uds.services.Xen.provider.XenProvider._api', new_callable=mock.PropertyMock) as api:
        api.return_value = client
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
