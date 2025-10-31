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
import random
import typing

from unittest import mock
import uuid


from uds.core import environment
from uds.core.ui.user_interface import gui
from uds.models.user import User
from unittest import mock

from uds.services.OpenShift import service, service_fixed, provider, publication, deployment, deployment_fixed
from uds.services.OpenShift.openshift import types as openshift_types, exceptions as openshift_exceptions

DEF_VMS: list[openshift_types.VM] = [
    openshift_types.VM(
        name=f'vm-{i}',
        namespace='default',
        uid=f'uid-{i}',
        status=openshift_types.VMStatus.STOPPED if i % 2 == 0 else openshift_types.VMStatus.RUNNING,
        volume_template=openshift_types.VolumeTemplate(name=f'volume-{i}', storage='10Gi'),
        disks=[openshift_types.DeviceDisk(name=f'disk-{i}', boot_order=1)],
        volumes=[openshift_types.Volume(name=f'volume-{i}', data_volume=f'dv-{i}')],
    )
    for i in range(1, 11)
]

DEF_VM_INSTANCES: list[openshift_types.VMInstance] = [
    openshift_types.VMInstance(
        name=f'vm-{i}',
        namespace='default',
        uid=f'uid-instance-{i}',
        interfaces=[
            openshift_types.Interface(
                name='eth0',
                mac_address=f'00:11:22:33:44:{i:02x}',
                ip_address=f'192.168.1.{i}',
            )
        ],
        status=openshift_types.VMStatus.STOPPED if i % 2 == 0 else openshift_types.VMStatus.RUNNING,
        phase=openshift_types.VMStatus.STOPPED if i % 2 == 0 else openshift_types.VMStatus.RUNNING,
    )
    for i in range(1, 11)
]

# clone values to avoid modifying the original ones
VMS: list[openshift_types.VM] = copy.deepcopy(DEF_VMS)
VM_INSTANCES: list[openshift_types.VMInstance] = copy.deepcopy(DEF_VM_INSTANCES)


def clear() -> None:
    """
    Resets all values to the default ones
    """
    VMS[:] = copy.deepcopy(DEF_VMS)
    VM_INSTANCES[:] = copy.deepcopy(DEF_VM_INSTANCES)


def replace_vm_info(vm_name: str, **kwargs: typing.Any) -> None:
    """
    Set the values of VMS by name
    """
    try:
        vm = next(vm for vm in VMS if vm.name == vm_name)
        for k, v in kwargs.items():
            setattr(vm, k, v)
    except Exception:
        raise openshift_exceptions.OpenshiftNotFoundError(f'VM {vm_name} not found')


def replacer_vm_info(**kwargs: typing.Any) -> typing.Callable[..., None]:
    return functools.partial(replace_vm_info, **kwargs)


T = typing.TypeVar('T')


def returner(value: T, *args: typing.Any, **kwargs: typing.Any) -> typing.Callable[..., T]:
    def inner(*args: typing.Any, **kwargs: typing.Any) -> T:
        return value

    return inner


# Provider values
PROVIDER_VALUES_DICT: gui.ValuesDictType = {
    'cluster_url': 'https://oauth-openshift.apps-crc.testing',
    'api_url': 'https://api.crc.testing:6443',
    'username': 'kubeadmin',
    'password': 'test-password',
    'namespace': 'default',
    'verify_ssl': False,
    'concurrent_creation_limit': 1,
    'concurrent_removal_limit': 1,
    'timeout': 10,
}

# Service values
SERVICE_VALUES_DICT: gui.ValuesDictType = {
    'template': VMS[0].name,
    'basename': 'base',
    'lenname': 4,
    'publication_timeout': 120,
    'prov_uuid': '',
}

# Service fixed values
SERVICE_FIXED_VALUES_DICT: gui.ValuesDictType = {
    'token': '',
    'machines': [VMS[2].name, VMS[3].name, VMS[4].name],
    'on_logout': 'no',
    'randomize': False,
    'maintain_on_error': False,
    'prov_uuid': '',
}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of OpenshiftClient
    """
    client = mock.MagicMock()

    vms = copy.deepcopy(DEF_VMS)
    vm_instances = copy.deepcopy(DEF_VM_INSTANCES)

    # Setup client methods
    client.test.return_value = True
    client.list_vms.return_value = vms
    client.get_vm_info.return_value = lambda vm_name: next((vm for vm in vms if vm.name == vm_name), None)  # type: ignore[arg-type]
    client.get_vm_instance_info.return_value = lambda vm_name: next((vmi for vmi in vm_instances if vmi.name == vm_name), None)  # type: ignore[arg-type]
    client.start_vm_instance.return_value = True
    client.stop_vm_instance.return_value = True
    client.delete_vm_instance.return_value = True
    client.get_datavolume_phase.return_value = 'Succeeded'
    client.get_vm_pvc_or_dv_name.return_value = ('test-pvc', 'pvc')
    client.get_pvc_size.return_value = '10Gi'
    client.create_vm_from_pvc.return_value = True
    client.wait_for_datavolume_clone_progress.return_value = True

    return client


@contextlib.contextmanager
def patched_provider(
    **kwargs: typing.Any,
) -> typing.Generator[provider.OpenshiftProvider, None, None]:
    client = create_client_mock()
    prov = create_provider(**kwargs)
    prov._cached_api = client
    yield prov


def create_provider(**kwargs: typing.Any) -> provider.OpenshiftProvider:
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider.OpenshiftProvider(
        environment=environment.Environment.private_environment(uuid_), values=values, uuid=uuid_
    )


def create_service(
    provider: typing.Optional[provider.OpenshiftProvider] = None, **kwargs: typing.Any
) -> service.OpenshiftService:
    """
    Create a dynamic service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_VALUES_DICT.copy()
    values.update(kwargs)
    srvc = service.OpenshiftService(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )
    return srvc


def create_service_fixed(
    provider: typing.Optional[provider.OpenshiftProvider] = None, **kwargs: typing.Any
) -> service_fixed.OpenshiftServiceFixed:
    """
    Create a fixed service
    """
    uuid_ = str(uuid.uuid4())
    values = SERVICE_FIXED_VALUES_DICT.copy()
    values.update(kwargs)
    return service_fixed.OpenshiftServiceFixed(
        environment=environment.Environment.private_environment(uuid_),
        provider=provider or create_provider(),
        values=values,
        uuid=uuid_,
    )


def create_publication(
    service: typing.Optional[service.OpenshiftService] = None,
    **kwargs: typing.Any,
) -> publication.OpenshiftTemplatePublication:
    """
    Create a publication
    """
    uuid_ = str(uuid.uuid4())
    pub = publication.OpenshiftTemplatePublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service(**kwargs),
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )
    pub._name = f"pub-{random.randint(1000, 9999)}"
    return pub


def create_userservice(
    service: typing.Optional[service.OpenshiftService] = None,
    publication: typing.Optional[publication.OpenshiftTemplatePublication] = None,
) -> deployment.OpenshiftUserService:
    """
    Create a dynamic user service
    """
    uuid_ = str(uuid.uuid4())
    return deployment.OpenshiftUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service(),
        publication=publication or create_publication(),
        uuid=uuid_,
    )


def create_userservice_fixed(
    service: typing.Optional[service_fixed.OpenshiftServiceFixed] = None,
) -> deployment_fixed.OpenshiftUserServiceFixed:
    """
    Create a fixed user service
    """
    uuid_ = str(uuid.uuid4().hex)
    return deployment_fixed.OpenshiftUserServiceFixed(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_fixed(),
        publication=None,
        uuid=uuid_,
    )


def create_user(
    name: str = "testuser",
    real_name: str = "Test User",
    is_admin: bool = False,
    state: str = 'A',
    password: str = 'password',
    mfa_data: str = '',
    staff_member: bool = False,
    last_access: typing.Optional[str] = None,
    parent: typing.Optional[User] = None,
    created: typing.Optional[str] = None,
    comments: str = '',
) -> User:
    """
    Creates a mock User instance for testing purposes.
    """
    user = mock.Mock(spec=User)
    user.name = name
    user.real_name = real_name
    user.is_admin = is_admin
    user.state = state
    user.password = password
    user.mfa_data = mfa_data
    user.staff_member = staff_member
    user.last_access = last_access
    user.parent = parent
    user.created = created
    user.comments = comments
    return user
