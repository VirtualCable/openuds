import typing
import logging

from uds.core.ui import gui
from uds.core import transports
from uds.core.environment import Environment
from uds.core.types import servers

from . import migrator

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


def migrate(apps, schema_editor) -> None:
    migrator.tunnel_transport(apps, HTML5RDPTransport, 'guacamoleServer', 'HTML5 RDP', 'Tunnel for HTML RDP', is_html_server=True)

def migrate_back(apps, schema_editor) -> None:
    migrator.tunnel_transport_back(apps, HTML5RDPTransport, 'guacamoleServer', is_html_server=True)
