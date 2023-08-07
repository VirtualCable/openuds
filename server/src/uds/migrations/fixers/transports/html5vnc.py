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
class HTML5VNCTransport(transports.Transport):
    """
    Provides access via VNC to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeName = 'HTML5 VNC Experimental'
    typeType = 'HTML5VNCTransport'
    guacamoleServer = gui.TextField(
        defvalue='https://',
    )

    username = gui.TextField(
    )
    password = gui.PasswordField(
    )

    vncPort = gui.NumericField(
        defvalue='5900',
    )

    colorDepth = gui.ChoiceField(
        defvalue='-',
    )
    swapRedBlue = gui.CheckBoxField(
    )
    cursor = gui.CheckBoxField(
    )
    readOnly = gui.CheckBoxField(
    )

    ticketValidity = gui.NumericField(
        defvalue='60',
    )
    forceNewWindow = gui.ChoiceField(
        defvalue=gui.FALSE,
    )

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnelServer = gui.ChoiceField()


def migrate(apps, schema_editor) -> None:
    migrator.tunnel_transport(apps, HTML5VNCTransport, 'guacamoleServer', 'HTML5 VNC', 'Tunnel for HTML VNC', is_html_server=True)
