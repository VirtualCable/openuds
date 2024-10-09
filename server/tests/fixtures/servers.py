# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import typing

from uds import models
from uds.core import types
import datetime

from ..utils import helpers


def create_server(
    type: 'types.servers.ServerType' = types.servers.ServerType.SERVER,
    subtype: typing.Optional[str] = None,
    version: typing.Optional[str] = None,
    ip: typing.Optional[str] = None,
    listen_port: int = 0,
    data: typing.Any = None,
) -> 'models.Server':
    # Token is created by default on record creation
    return models.Server.objects.create(
        register_username=helpers.random_string(),
        register_ip=ip or '127.0.0.1',
        ip=ip or '127.0.0.1',
        hostname=helpers.random_string(),
        listen_port=listen_port,
        stamp=datetime.datetime.now(),
        type=type,
        subtype=subtype or '',
        os_type=types.os.KnownOS.WINDOWS.os_name(),
        version=version or '4.0.0',
        data=data or {},
    )


def create_server_group(
    type: 'types.servers.ServerType' = types.servers.ServerType.SERVER,
    subtype: typing.Optional[str] = None,
    version: typing.Optional[str] = None,
    ip: typing.Optional[str] = None,
    host: typing.Optional[str] = None,
    port: int = 0,
    listen_port: int = 0,
    num_servers: int = 1,
) -> models.ServerGroup:
    rsg = models.ServerGroup.objects.create(
        name=helpers.random_string(),
        comments=helpers.random_string(),
        type=type,
        subtype=subtype or '',
        host=host or '',
        port=port,
    )
    for _ in range(num_servers):
        server = create_server(type, subtype=subtype, version=version, ip=ip, listen_port=listen_port)
        rsg.servers.add(server)

    return rsg
