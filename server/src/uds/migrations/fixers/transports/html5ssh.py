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


class HTML5SSHTransport(transports.Transport):
    """
    Provides access via SSH to service.
    """

    typeName = 'HTML5 SSH migration'
    typeType = 'HTML5SSHTransport'

    guacamoleServer = gui.TextField(
        defvalue='https://',
    )

    username = gui.TextField(
    )
    sshCommand = gui.TextField(
    )
    enableFileSharing = gui.ChoiceField(
        defvalue='false',
    )
    fileSharingRoot = gui.TextField(
    )
    sshPort = gui.NumericField(
        defvalue='22',
    )
    sshHostKey = gui.TextField(
    )
    serverKeepAlive = gui.NumericField(
        defvalue='30',
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
    migrator.tunnel_transport(apps, HTML5SSHTransport, 'guacamoleServer', 'HTML5 SSH', 'Tunnel for HTML SSH', is_html_server=True)
