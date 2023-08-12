# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import secrets

import dns.resolver

from uds.core import transports
from uds.core.ui import gui
from uds.core.util import validators

logger = logging.getLogger(__name__)


# Copy for migration
# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core import services, types
from uds.core.environment import Environment
from uds.core.ui import gui

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import uds.models

def migrate(apps, model: typing.Literal['Provider', 'Service'],  DataType: typing.Type, subtype: str, ipListAttr: str) -> None:
    try:
        Table: typing.Type['uds.models.ManagedObjectModel'] = apps.get_model('uds', model)
        RegisteredServerGroup: 'typing.Type[uds.models.RegisteredServerGroup]' = apps.get_model(
            'uds', 'RegisteredServerGroup'
        )
        RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
        # For testing
        # from uds.models import Provider, RegisteredServer, RegisteredServerGroup

        for record in Table.objects.filter(data_type=DataType.typeType):
            # Extract data
            obj = DataType(Environment(record.uuid), None)
            obj.deserialize(record.data)

            servers: typing.List[str] = getattr(obj, ipListAttr).value
            # Clean up servers, removing empty ones
            servers = [s.strip() for s in servers if s.strip()]
            # Try dns lookup if servers contains hostnames
            server_ip_hostname: typing.List[typing.Tuple[str, str]] = []
            for server in servers:
                try:
                    validators.validateIpv4OrIpv6(server)
                    # Is Pure IP, try to get hostname
                    try:
                        answers = dns.resolver.resolve(server, 'PTR')
                        server_ip_hostname.append((server, str(answers[0])))
                    except Exception:
                        # No problem, no reverse dns, hostname is the same as IP
                        server_ip_hostname.append((server, server))
                except Exception:
                    # Not pure IP, try to resolve it and get first IP
                    try:
                        answers = dns.resolver.resolve(server, 'A')
                        server_ip_hostname.append((str(answers[0]), server))
                    except Exception:
                        # Try AAAA
                        try:
                            answers = dns.resolver.resolve(server, 'AAAA')
                            server_ip_hostname.append((str(answers[0]), server))
                        except Exception:
                            # Not found, continue, but do not add to servers and log it
                            logger.error('Server %s on %s not found on DNS', server, record.name)

            registeredServerGroup = RegisteredServerGroup.objects.create(
                name=f'RDS Server Group for {record.name}',
                comments='Migrated from {}'.format(record.name),
                type=types.servers.ServerType.UNMANAGED,
                subtype=subtype,
            )
            # Create Registered Servers for IP (individual) and add them to the group
            registeredServers = [
                RegisteredServer.objects.create(
                    token=secrets.token_urlsafe(36),
                    username='migration',
                    ip_from=server[0],
                    ip=server[0],
                    hostname=server[1],
                    listen_port=0,
                    type=types.servers.ServerType.UNMANAGED,
                    subtype=subtype,
                    stamp=datetime.datetime.now(),
                )
                for server in server_ip_hostname
            ]
            registeredServerGroup.servers.set(registeredServers)
            # Set server group on provider
            logger.info('Setting server group %s on provider %s', registeredServerGroup.name, record.name)
            obj.serverGroup.value = registeredServerGroup.uuid
            # Save provider
            record.data = obj.serialize()
            record.save(update_fields=['data'])

    except Exception as e:
        print(e)
        logger.exception('Exception found while migrating HTML5RDP transports')

