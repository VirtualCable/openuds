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

from uds.core import environment, types
from uds.core.ui.user_interface import gui

from ...utils.autospec import autospec, AutoSpecMethodInfo

from uds.services.OpenStack import provider, provider_legacy, openstack as client


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
# The idea behind this is to allow testing the provider, service and deployment classes
# without the need of a real OpenStack environment
CLIENT_METHODS_INFO: typing.Final[list[AutoSpecMethodInfo]] = [
    # connect returns None
    # Test method
    # AutoSpecMethodInfo(client.Client.list_projects, return_value=True),
    # AutoSpecMethodInfo(
    #    client.ProxmoxClient.get_node_stats,
    #    method=lambda node, **kwargs: next(filter(lambda n: n.name == node, NODE_STATS)),  # pyright: ignore
    # ),
]

PROVIDER_VALUES_DICT: typing.Final[gui.ValuesDictType] = {
    'endpoint': 'host',
    'access': 'public',
    'domain': 'domain',
    'username': 'username',
    'password': 'password',
    'concurrent_creation_limit': 1,
    'concurrent_removal_limit': 1,
    'timeout': 10,
    'tenant': 'tenant',
    'region': 'region',
    'use_subnets_name': False,
    'https_proxy': 'https_proxy',
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


SERVICE_VALUES_DICT: typing.Final[gui.ValuesDictType] = {}


def create_client_mock() -> mock.Mock:
    """
    Create a mock of ProxmoxClient
    """
    return autospec(client.Client, CLIENT_METHODS_INFO)


@contextlib.contextmanager
def patch_provider_api(
    legacy: bool = False,
    **kwargs: typing.Any,
) -> typing.Generator[mock.Mock, None, None]:
    client = create_client_mock()
    path = (
        'uds.services.OpenStack.provider_legacy.OpenStackProviderLegacy'
        if legacy
        else 'uds.services.OpenStack.provider.OpenStackProvider'
    )
    try:
        mock.patch(path + 'api', return_value=client).start()
        yield client
    finally:
        mock.patch.stopall()


def create_provider(**kwargs: typing.Any) -> provider.OpenStackProvider:
    """
    Create a provider
    """
    values = PROVIDER_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider.OpenStackProvider(
        environment=environment.Environment.private_environment(uuid), values=values, uuid=uuid_
    )


def create_provider_legacy(**kwargs: typing.Any) -> provider_legacy.OpenStackProviderLegacy:
    """
    Create a provider legacy
    """
    values = PROVIDER_LEGACY_VALUES_DICT.copy()
    values.update(kwargs)

    uuid_ = str(uuid.uuid4())
    return provider_legacy.OpenStackProviderLegacy(
        environment=environment.Environment.private_environment(uuid), values=values, uuid=uuid_
    )
