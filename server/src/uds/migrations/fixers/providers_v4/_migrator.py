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
import typing

import dns.resolver
import dns.reversename

from uds.core import consts, types
from uds.core.environment import Environment
from uds.core.util import validators

logger = logging.getLogger(__name__)


if typing.TYPE_CHECKING:
    import uds.models
    from uds.core.serializable import Serializable

    class TypeTestingClass(Serializable):
        server_group: typing.Any
        
        def post_migrate(self, apps: typing.Any, record: typing.Any) -> None:
            pass
        
def _get_environment(record: typing.Any) -> Environment:
    """
    Returns an environment valid for the record this object represents
    """
    return Environment.environment_for_table_record(record._meta.verbose_name or record._meta.db_table, record.id)
        

def migrate(
    apps: typing.Any, model: typing.Literal['Provider', 'Service'], data_type: typing.Any, subtype: str, ip_list_attr: str,
    server_group_prefix: str,
) -> None:
    try:
        Table: type['uds.models.ManagedObjectModel'] = apps.get_model('uds', model)
        ServerGroup: 'type[uds.models.ServerGroup]' = apps.get_model(
            'uds', 'ServerGroup'
        )
        # Server: 'type[uds.models.Server]' = apps.get_model('uds', 'Server')
        # For testing
        # from uds.models import Provider, Server, ServerGroup

        for record in Table.objects.filter(data_type=data_type.type_type):  # pyright: ignore
            # Extract data
            obj: 'TypeTestingClass' = data_type(_get_environment(record), None)
            obj.deserialize(record.data)

            servers: list[str] = getattr(obj, ip_list_attr).value
            # Clean up
            getattr(obj, ip_list_attr).value = []
            # Clean up servers, removing empty ones
            servers = [s.strip() for s in servers if s.strip()]
            # Try dns lookup if servers contains hostnames
            server_ip_hostname_mac: list[tuple[str, str, str]] = []
            for server in servers:
                mac = consts.MAC_UNKNOWN
                try:
                    if ';' in server:
                        server, mac = server.split(';')[:2]
                    validators.validate_ip(server)
                    # Is Pure IP, try to get hostname
                    try:
                        answers = typing.cast(list[typing.Any], dns.resolver.resolve(dns.reversename.from_address(server), 'PTR'))
                        server_ip_hostname_mac.append((server, str(answers[0]).rstrip('.'), mac))
                    except Exception:
                        # No problem, no reverse dns, hostname is the same as IP
                        server_ip_hostname_mac.append((server, '', mac))
                except Exception:
                    # Not pure IP, try to resolve it and get first IP
                    try:
                        answers = typing.cast(list[typing.Any], dns.resolver.resolve(server, 'A'))
                        server_ip_hostname_mac.append((str(answers[0]), server, mac))
                    except Exception:
                        # Try AAAA
                        try:
                            answers = typing.cast(list[typing.Any], dns.resolver.resolve(server, 'AAAA'))
                            server_ip_hostname_mac.append((str(answers[0]), server, mac))
                        except Exception:
                            # Not found, continue, but do not add to servers and log it
                            logger.error('Server %s on %s not found on DNS', server, record.name)

            registered_server_group = ServerGroup.objects.create(
                name=f'{server_group_prefix} for {record.name}'[:64],
                comments='Migrated from {}'.format(record.name)[:255],
                type=types.servers.ServerType.UNMANAGED,
                subtype=subtype,
            )
            # Create Registered Servers for IP (individual) and add them to the group
            for ip, hostname, mac in server_ip_hostname_mac:
                registered_server_group.servers.create(
                    token=secrets.token_urlsafe(36),
                    register_username='migration',
                    register_ip='127.0.0.1',
                    ip=ip,
                    os_type=types.os.KnownOS.WINDOWS.os_name(),
                    hostname=hostname,
                    mac=mac,
                    listen_port=0,
                    type=types.servers.ServerType.UNMANAGED,
                    subtype=subtype,
                    stamp=datetime.datetime.now(),
                )
            # Set server group on provider
            logger.info('Setting server group %s on provider %s', registered_server_group.name, record.name)
            obj.server_group.value = registered_server_group.uuid
            # Now, execute post_migrate of obj
            try:
                obj.post_migrate(apps, record)
            except Exception:
                logger.exception('Exception found while executing post_migrate on %s', data_type.type_type)
                # Ignore error, but log it
            # Save record
            record.data = obj.serialize()
            record.save(update_fields=['data'])

    except Exception:
        logger.exception(f'Exception found while migrating {data_type.type_type}')

def rollback(apps: typing.Any, model: typing.Literal['Provider', 'Service'], DataType: typing.Any, subtype: str, ip_list_attr: str) -> None:
    """
    "Un-Migrates" to an old one
    """
    try:
        Table: type['uds.models.ManagedObjectModel'] = apps.get_model('uds', model)
        ServerGroup: 'type[uds.models.ServerGroup]' = apps.get_model(
            'uds', 'ServerGroup'
        )
        # For testing
        # from uds.models import Transport, ServerGroup

        for record in Table.objects.filter(data_type=DataType.type_type):  # pyright: ignore
            # Extranct data
            obj = DataType(Environment(record.uuid), None)
            obj.deserialize(record.data)
            # Guacamole server is https://<host>:<port>
            # Other tunnels are <host>:<port>
            iplist = getattr(obj, ip_list_attr)
            rsg = ServerGroup.objects.get(uuid=obj.server_group.value)
            iplist.value=[i.ip for i in rsg.servers.all()]
            # Remove registered servers
            for i in rsg.servers.all():
                i.delete()
            # Save obj
            record.data = obj.serialize()
            record.save(update_fields=['data'])
    except Exception as e:  # nosec: ignore this
        print(e)
        logger.error('Exception found while migrating HTML5RDP transports: %s', e)