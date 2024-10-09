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
import datetime
import typing
import uuid

from unittest import mock

from uds import models
from uds.core import environment, types
from uds.core.ui.user_interface import gui

from uds.services.PhysicalMachines import (
    provider,
    service_single,
    service_multi,
    deployment as deployment_single,
    deployment_multi,
)

SERVER_GROUP_IPS_MACS: typing.Final[list[tuple[str, str]]] = [
    (f'127.0.1.{x}', f'{x:02x}:22:{x*2:02x}:44:{x*4:02x}:66') for x in range(1, 32)
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


def create_server_group() -> models.ServerGroup:
    server_group = models.ServerGroup.objects.create(
        name='Test Server Group',
        type=types.servers.ServerType.UNMANAGED,
        subtype=types.servers.IP_SUBTYPE,
    )
    for ip, mac in SERVER_GROUP_IPS_MACS:
        server = models.Server.objects.create(
            register_username='test',
            register_ip='127.0.0.1',
            type=types.servers.ServerType.UNMANAGED,
            ip=ip,
            mac=mac,
            hostname=f'test-{ip}',
            stamp=datetime.datetime.now(),
        )
        server.groups.set([server_group])

    return server_group


def create_provider(**kwargs: typing.Any) -> provider.PhysicalMachinesProvider:
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    prov_instance = provider.PhysicalMachinesProvider(
        environment=environment.Environment.private_environment(uuid_), values=values, uuid=uuid_
    )
    # Create a DB provider for this
    models.Provider.objects.create(
        uuid=uuid_,
        name='Test Provider',
        data_type=prov_instance.mod_type(),
        data=prov_instance.serialize(),
    )

    return prov_instance


def create_service_single(
    prov: typing.Optional[provider.PhysicalMachinesProvider] = None, **kwargs: typing.Any
) -> service_single.IPSingleMachineService:
    """
    Create a service
    """
    values = SERVICE_SINGLE_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())

    if prov is None:
        prov = create_provider()

    service_instance = service_single.IPSingleMachineService(
        provider=prov,
        environment=environment.Environment.private_environment(uuid_),
        values=values,
        uuid=uuid_,
    )

    # Create a DB service for this
    models.Service.objects.create(
        uuid=uuid_,
        name='Test Service',
        data_type=service_instance.mod_type(),
        data=service_instance.serialize(),
        provider=prov.db_obj(),
    )

    return service_instance


def create_service_multi(
    prov: typing.Optional[provider.PhysicalMachinesProvider] = None, **kwargs: typing.Any
) -> service_multi.IPMachinesService:
    """
    Create a service
    """
    # Create a server group, and add it to the kwargs if
    server_group = create_server_group()
    if 'server_group' not in kwargs:
        kwargs['server_group'] = server_group.uuid

    values = SERVICE_MULTI_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())

    if prov is None:
        prov = create_provider()

    service_instance = service_multi.IPMachinesService(
        provider=prov,
        environment=environment.Environment.private_environment(uuid_),
        values=values,
        uuid=uuid_,
    )

    # Create a DB service for this
    models.Service.objects.create(
        uuid=uuid_,
        name='Test Service',
        data_type=service_instance.mod_type(),
        data=service_instance.serialize(),
        provider=prov.db_obj(),
    )

    return service_instance


def create_userservice_single(
    service: typing.Optional[service_single.IPSingleMachineService] = None, **kwargs: typing.Any
) -> deployment_single.IPMachineUserService:
    """
    Create a user service
    """
    uuid_ = str(uuid.uuid4())

    userservice_instance = deployment_single.IPMachineUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_single(),
        publication=None,
        uuid=uuid_,
    )

    userservice_instance.db_obj = mock.MagicMock()

    return userservice_instance


def create_userservice_multi(
    service: typing.Optional[service_single.IPSingleMachineService] = None, **kwargs: typing.Any
) -> deployment_multi.IPMachinesUserService:
    """
    Create a user service
    """
    uuid_ = str(uuid.uuid4())

    userservice_instance = deployment_multi.IPMachinesUserService(
        environment=environment.Environment.private_environment(uuid_),
        service=service or create_service_multi(),
        publication=None,
        uuid=uuid_,
    )

    userservice_instance.db_obj = mock.MagicMock()

    return userservice_instance
