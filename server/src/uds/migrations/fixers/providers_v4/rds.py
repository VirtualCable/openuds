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

import dns.resolver

from uds.core.ui import gui
from uds.core import transports
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
import typing
import logging

from uds.core.environment import Environment
from uds.core import types

from uds.core.ui import gui
from uds.core import services

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import uds.models

RDS_SUBTYPE: typing.Final[str] = 'rds'


# Copy for migration
class RDSProvider(services.ServiceProvider):
    typeType = 'RDSProvider'

    # Gui
    ipList = gui.EditableListField()
    serverCheck = gui.CheckBoxField(defvalue=gui.FALSE)

    # User mapping, classical
    useUserMapping = gui.CheckBoxField(defvalue=gui.FALSE)
    userMap = gui.EditableListField()
    userPass = gui.PasswordField()

    # User creating, new
    useUserCreation = gui.CheckBoxField(defvalue=gui.FALSE)
    adHost = gui.TextField()
    adPort = gui.NumericField(defvalue='636')
    adUsersDn = gui.TextField()
    adUsername = gui.TextField()
    adPassword = gui.PasswordField()
    adUserPrefix = gui.TextField(defvalue='UDS_')
    adDomain = gui.TextField()
    adGroup = gui.TextField()
    adCertificate = gui.TextField()

    # This value is the new server group that contains the "ipList"
    serverGroup = gui.ChoiceField()


def _migrate(apps, ProviderType: typing.Type, subtype: str, ipListAttr: str) -> None:
    try:
        # Provider: 'typing.Type[uds.models.Transport]' = apps.get_model('uds', 'Provider')
        # RegisteredServerGroup: 'typing.Type[uds.models.RegisteredServerGroup]' = apps.get_model('uds', 'RegisteredServerGroup')
        # RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
        # For testing
        from uds.models import Provider, RegisteredServerGroup, RegisteredServer

        for provider in Provider.objects.filter(data_type=ProviderType.typeType):
            # Extract data
            obj = ProviderType(Environment(provider.uuid), None)
            obj.deserialize(provider.data)

            servers: typing.List[str] = getattr(obj, ipListAttr).value
            # Clean up servers, removing empty ones
            servers = [s.strip() for s in servers if s.strip()]
            # Try dns lookup if servers contains hostnames
            for server in servers:
                try:
                    validators.validateIpv4OrIpv6(server)
                    # Is Pure IP, continue
                    continue
                except Exception:
                    # Not pure IP, try to resolve it and get first IP
                    try:
                        answers = dns.resolver.resolve(server, 'A')
                        servers.remove(server)
                        servers.append(str(answers[0]))
                    except Exception:
                        # Try AAAA
                        try:
                            answers = dns.resolver.resolve(server, 'AAAA')
                            servers.remove(server)
                            servers.append(str(answers[0]))
                        except Exception:
                            # Not found, continue, but do not add to servers and log it
                            logger.error('Server %s on %s not found on DNS', server, provider.name)

            registeredServerGroup = RegisteredServerGroup.objects.create(
                name=f'RDS Server Group for {provider.name}',
                comments='Migrated from {}'.format(provider.name),
                type=types.servers.ServerType.UNMANAGED,
                subtype=subtype,
            )
            # Create Registered Servers for IP (individual) and add them to the group
            registeredServers = [
                RegisteredServer.objects.create(
                    username='migration',
                    ip_from=server,
                    ip=server,
                    host=server,
                    port=3389,
                    type=types.servers.ServerType.UNMANAGED,
                    subtype=subtype,
                    parent=registeredServerGroup,
                )
                for server in servers
            ]
            registeredServerGroup.servers.set(registeredServers)
            # Set server group on provider
            logger.info('Setting server group %s on provider %s', registeredServerGroup.name, provider.name)
            obj.serverGroup.value = registeredServerGroup.uuid
            # Save provider
            provider.data = obj.serialize()
            provider.save(update_fields=['data'])

    except Exception as e:
        print(e)
        logger.exception('Exception found while migrating HTML5RDP transports')


def rollback(apps, schema_editor) -> None:
    pass
