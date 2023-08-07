import typing
import logging

from uds.core.environment import Environment
from uds.core.types import servers

if typing.TYPE_CHECKING:
    import uds.models

logger = logging.getLogger(__name__)

def tunnel_transport(apps, TransportType: typing.Type, serverAttr: str, name: str, comments: str, is_html_server: bool = False) -> None:
    """
    Migrates an old tunnel transport to a new one (with tunnelServer)
    """
    try:
        # Transport: 'typing.Type[uds.models.Transport]' = apps.get_model('uds', 'Transport')
        # RegisteredServerGroup: 'typing.Type[uds.models.RegisteredServerGroup]' = apps.get_model('uds', 'RegisteredServerGroup')
        # RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
        # For testing
        from uds.models import Transport, RegisteredServerGroup, RegisteredServer

        for t in Transport.objects.filter(data_type=TransportType.typeType):
            print(t)
            # Extranct data
            obj = TransportType(Environment(t.uuid), None)
            obj.deserialize(t.data)
            # Guacamole server is https://<host>:<port>
            server = getattr(obj, serverAttr).value
            print(obj, server, is_html_server)
            if is_html_server:
                if not server.startswith('https://'):
                    # Skip if not https found
                    logger.error('Skipping %s transport %s as it does not starts with https://', TransportType.__name__, t.name)
                    continue
                host, port = (server+':443').split('https://')[1].split(':')[:2]
            else:
                host, port = (server+':443')[1].split(':')[:2]
            # If no host or port, skip
            if not host or not port:
                logger.error('Skipping %s transport %s as it does not have host or port', TransportType.__name__, t.name)
                continue
            # Look for an existing tunnel server (RegisteredServerGroup)
            tunnelServer = RegisteredServerGroup.objects.filter(
                host=host, port=port, kind=servers.ServerType.TUNNEL
            ).first()
            if tunnelServer is None:
                logger.info('Creating new tunnel server for %s: %s:%s', TransportType.__name__,  host, port)
                # Create a new one, adding all tunnel servers to it
                tunnelServer = RegisteredServerGroup.objects.create(
                    name=f'{name} on {host}:{port}',
                    comments=f'{comments or name} (migration)',
                    host=host,
                    port=port,
                    kind=servers.ServerType.TUNNEL,
                )
            tunnelServer.servers.set(RegisteredServer.objects.filter(kind=servers.ServerType.TUNNEL))
            # Set tunnel server on transport
            logger.info('Setting tunnel server %s on transport %s', tunnelServer.name, t.name)
            obj.tunnelServer.value = tunnelServer.uuid
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
        # Transport: 'typing.Type[uds.models.Transport]' = apps.get_model('uds', 'Transport')
        # RegisteredServerGroup: 'typing.Type[uds.models.RegisteredServerGroup]' = apps.get_model('uds', 'RegisteredServerGroup')
        # RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
        # For testing
        from uds.models import Transport, RegisteredServerGroup, RegisteredServer

        for t in Transport.objects.filter(data_type=TransportType.typeType):
            print(t)
            # Extranct data
            obj = TransportType(Environment(t.uuid), None)
            obj.deserialize(t.data)
            # Guacamole server is https://<host>:<port>
            server = getattr(obj, serverAttr)
            tunnelServer = RegisteredServerGroup.objects.get(uuid=obj.tunnelServer.value)
            if is_html_server:
                server.value = f'https://{tunnelServer.pretty_host}'
            else:
                server.value = f'{tunnelServer.pretty_host}'
            # Save transport
            t.data = obj.serialize()
            t.save(update_fields=['data'])
    except Exception as e:  # nosec: ignore this
        print(e)
        logger.exception('Exception found while migrating BACK HTML5RDP transports')
