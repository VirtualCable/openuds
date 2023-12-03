import typing
import collections.abc
import logging

from uds.core.environment import Environment
from uds.core.types import servers

if typing.TYPE_CHECKING:
    import uds.models

logger = logging.getLogger(__name__)

def tunnel_transport(apps, TransportType: typing.Type, serverAttr: str, is_html_server: bool = False) -> None:
    """
    Migrates an old tunnel transport to a new one (with tunnelServer)
    """
    try:
        Transport: 'type[uds.models.Transport]' = apps.get_model('uds', 'Transport')
        ServerGroup: 'type[uds.models.ServerGroup]' = apps.get_model('uds', 'ServerGroup')
        Server: 'type[uds.models.Server]' = apps.get_model('uds', 'Server')
        # For testing
        # from uds.models import Transport, ServerGroup, Server

        for t in Transport.objects.filter(data_type=TransportType.typeType):
            # Extract data
            obj = TransportType(Environment(t.uuid), None)
            obj.deserialize(t.data)

            server = getattr(obj, serverAttr).value.strip()
            # Guacamole server is https://<host>:<port>
            if is_html_server:
                if not server.startswith('https://'):
                    # Skip if not https found
                    logger.error('Skipping %s transport %s as it does not starts with https://', TransportType.__name__, t.name)
                    continue
                host, port = (server+':443').split('https://')[1].split(':')[:2]
            else:  # Other servers are <host>:<port>
                host, port = (server+':443').split(':')[:2]
            # If no host or port, skip
            if not host or not port:
                logger.error('Skipping %s transport %s as it does not have host or port', TransportType.__name__, t.name)
                continue
            # Look for an existing tunnel server (ServerGroup)
            tunnel = ServerGroup.objects.filter(
                host=host, port=port, type=servers.ServerType.TUNNEL
            ).first()
            if tunnel is None:
                logger.info('Creating new tunnel server for %s: %s:%s', TransportType.__name__,  host, port)
                # Create a new one, adding all tunnel servers to it
                tunnel = ServerGroup.objects.create(
                    name=f'Tunnel on {host}:{port}',
                    comments=f'Migrated from {t.name}',
                    host=host,
                    port=port,
                    type=servers.ServerType.TUNNEL,
                )
            else:
                # Append transport name to comments
                tunnel.comments = f'{tunnel.comments}, {t.name}'[:255]
                tunnel.save(update_fields=['comments'])
            tunnel.servers.set(Server.objects.filter(type=servers.ServerType.TUNNEL))
            # Set tunnel server on transport
            logger.info('Setting tunnel server %s on transport %s', tunnel.name, t.name)
            obj.tunnel.value = tunnel.uuid
            # Save transport
            t.data = obj.serialize()
            t.save(update_fields=['data'])
    except Exception as e:  # nosec: ignore this
        print(e)
        logger.exception('Exception found while migrating HTML5RDP transports')

def tunnel_transport_back(apps, TransportType: typing.Type, serverAttr: str, is_html_server: bool) -> None:
    """
    "Un-Migrates" an new tunnel transport to an old one (without tunnelServer)
    """
    try:
        Transport: 'type[uds.models.Transport]' = apps.get_model('uds', 'Transport')
        ServerGroup: 'type[uds.models.ServerGroup]' = apps.get_model('uds', 'ServerGroup')
        # For testing
        # from uds.models import Transport, ServerGroup

        for t in Transport.objects.filter(data_type=TransportType.typeType):
            # Extranct data
            obj = TransportType(Environment(t.uuid), None)
            obj.deserialize(t.data)
            # Guacamole server is https://<host>:<port>
            # Other tunnels are <host>:<port>
            server = getattr(obj, serverAttr)
            tunnelServer = ServerGroup.objects.get(uuid=obj.tunnel.value)
            if is_html_server:
                server.value = f'https://{tunnelServer.host}:{tunnelServer.port}'
            else:
                server.value = f'{tunnelServer.host}:{tunnelServer.port}'
            # Save transport
            t.data = obj.serialize()
            t.save(update_fields=['data'])
    except Exception as e:  # nosec: ignore this
        print(e)
        logger.error('Exception found while migrating HTML5RDP transports: %s', e)