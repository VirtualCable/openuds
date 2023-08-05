import typing
import logging

from uds.core.ui import gui
from uds.core import transports
from uds.core.environment import Environment
from uds.core.types import servers

if typing.TYPE_CHECKING:
    import uds.models

logger = logging.getLogger(__name__)


# Copy for migration
class HTML5RDPTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeName = 'HTML5 RDP'  # Not important here, just for migrations
    typeType = 'HTML5RDPTransport'

    guacamoleServer = gui.TextField()

    useGlyptodonTunnel = gui.CheckBoxField()

    useEmptyCreds = gui.CheckBoxField()
    fixedName = gui.TextField()
    fixedPassword = gui.PasswordField()
    withoutDomain = gui.CheckBoxField()
    fixedDomain = gui.TextField()
    wallpaper = gui.CheckBoxField()
    desktopComp = gui.CheckBoxField()
    smooth = gui.CheckBoxField()
    enableAudio = gui.CheckBoxField(
        defvalue=gui.TRUE,
    )
    enableAudioInput = gui.CheckBoxField()
    enablePrinting = gui.CheckBoxField()
    enableFileSharing = gui.ChoiceField(
        defvalue='false',
    )
    enableClipboard = gui.ChoiceField(
        defvalue='enabled',
    )

    serverLayout = gui.ChoiceField(
        defvalue='-',
    )

    ticketValidity = gui.NumericField(
        defvalue='60',
    )

    forceNewWindow = gui.ChoiceField(
        defvalue=gui.FALSE,
    )
    security = gui.ChoiceField(
        defvalue='any',
    )

    rdpPort = gui.NumericField(
        defvalue='3389',
    )

    customGEPath = gui.TextField(
        defvalue='/',
    )

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnelServer = gui.ChoiceField()


def migrate_html5rdp_transport(apps, schema_editor) -> None:
    try:
        # Transport: 'typing.Type[uds.models.Transport]' = apps.get_model('uds', 'Transport')
        # RegisteredServerGroup: 'typing.Type[uds.models.RegisteredServerGroup]' = apps.get_model('uds', 'RegisteredServerGroup')
        # RegisteredServer: 'typing.Type[uds.models.RegisteredServer]' = apps.get_model('uds', 'RegisteredServer')
        # For testing
        from uds.models import Transport, RegisteredServerGroup, RegisteredServer

        for t in Transport.objects.filter(data_type=HTML5RDPTransport.typeType):
            print(t)
            # Extranct data
            obj = HTML5RDPTransport(Environment(t.uuid), None)
            obj.deserialize(t.data)
            # Guacamole server is https://<host>:<port>
            if not obj.guacamoleServer.value.startswith('https://'):
                # Skip if not https found
                logger.error('Skipping HTML5RDP transport %s as it does not starts with https://', t.name)
                continue
            host, port = (obj.guacamoleServer.value+':443').split('https://')[1].split(':')[:2]
            # Look for an existing tunnel server (RegisteredServerGroup)
            tunnelServer = RegisteredServerGroup.objects.filter(
                host=host, port=port, kind=servers.ServerType.TUNNEL
            ).first()
            if tunnelServer is None:
                logger.info('Creating new tunnel server for HTML5RDP: %s:%s', host, port)
                # Create a new one, adding all tunnel servers to it
                tunnelServer = RegisteredServerGroup.objects.create(
                    name=f'HTML5RDP Tunnel on {host}:{port}',
                    comments='Tunnel server for HTML5 RDP (migration)',
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
