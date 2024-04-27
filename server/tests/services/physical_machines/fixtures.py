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
import uuid

from unittest import mock

from uds import models
from uds.core import types
from uds.core.ui.user_interface import gui

SERVER_GROUP_IPS = [
    f'127.0.1.{x}' for x in range(1, 32)
]
    

PROVIDER_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'config': '[wol]\n127.0.0.1/16=http://127.0.0.1:8000/test',
}


SERVICE_SINGLE_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'host': '127.0.0.1',
}


SERVICE_MULTI_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'token': 'MULTI_TOKEN',
    'server_group': '899bcad9-1b4d-59e3-90c7-bdd28b7674fa',
    'port': 1000,  # Chekcin port
    'ignore_minutes_on_failure': 1,
    'max_session_hours': 2,
    'lock_on_external_access': True,
    'randomize_host': True,
}

def create_server_group():
    server_group = models.ServerGroup.objects.create(
        name='Test Server Group',
        type=types.servers.ServerType.UNMANAGED,
        subtype=types.servers.IP_SUBTYPE,
    )
    for ip in SERVER_GROUP_IPS:
        models.Server.objects.create(
            username='test',
            name=ip,
            ip=ip,
            group=server_group,
        )
    
    

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
    return service.OpenStackLiveService(
        provider=provider,
        environment=environment.Environment.private_environment(uuid_),
        values=values,
        uuid=uuid_,
    )


def create_publication(service: service.OpenStackLiveService) -> publication.OpenStackLivePublication:
    """
    Create a publication
    """
    uuid_ = str(uuid.uuid4())
    return publication.OpenStackLivePublication(
        environment=environment.Environment.private_environment(uuid_),
        service=service,
        revision=1,
        servicepool_name='servicepool_name',
        uuid=uuid_,
    )


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
