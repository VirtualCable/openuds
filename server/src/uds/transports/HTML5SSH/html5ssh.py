# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds import models
from uds.core import consts, transports, types
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui
from uds.core.util import fields

from ..HTML5RDP.html5rdp import HTML5RDPTransport

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.types.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class HTML5SSHTransport(transports.Transport):
    """
    Provides access via SSH to service.
    """

    type_name = _('HTML5 SSH')
    type_type = 'HTML5SSHTransport'
    type_description = _('SSH protocol using HTML5 client')
    icon_file = 'html5ssh.png'

    own_link = True
    supported_oss = consts.os.ALL_OS_LIST
    # pylint: disable=no-member  # ??? SSH is there, but pylint does not see it ???
    protocol = types.transports.Protocol.SSH
    group = types.transports.Grouping.TUNNELED

    tunnel = fields.tunnel_field()

    useGlyptodonTunnel = HTML5RDPTransport.useGlyptodonTunnel

    username = gui.TextField(
        label=_('Username'),
        order=20,
        tooltip=_('Username for SSH connection authentication.'),
        tab=types.ui.Tab.CREDENTIALS,
    )

    # password = gui.PasswordField(
    #     label=_('Password'),
    #     order=21,
    #     tooltip=_('Password for SSH connection authentication'),
    #     tab=types.ui.Tab.CREDENTIALS,
    # )
    # sshPrivateKey = gui.TextField(
    #     label=_('SSH Private Key'),
    #     order=22,
    #     lines=4,
    #     tooltip=_(
    #         'Private key for SSH authentication. If not provided, password authentication is used.'
    #     ),
    #     tab=types.ui.Tab.CREDENTIALS,
    # )
    # sshPassphrase = gui.PasswordField(
    #     label=_('SSH Private Key Passphrase'),
    #     order=23,
    #     tooltip=_(
    #         'Passphrase for SSH private key if it is required. If not provided, but it is needed, user will be prompted for it.'
    #     ),
    #     tab=types.ui.Tab.CREDENTIALS,
    # )

    sshCommand = gui.TextField(
        label=_('SSH Command'),
        order=30,
        tooltip=_(
            'Command to execute on the remote server. If not provided, an interactive shell will be executed.'
        ),
        tab=types.ui.Tab.PARAMETERS,
    )
    enableFileSharing = HTML5RDPTransport.enableFileSharing
    fileSharingRoot = gui.TextField(
        label=_('File Sharing Root'),
        order=32,
        tooltip=_('Root path for file sharing. If not provided, root directory will be used.'),
        tab=types.ui.Tab.PARAMETERS,
    )
    sshPort = gui.NumericField(
        length=40,
        label=_('SSH Server port'),
        default=22,
        order=33,
        tooltip=_('Port of the SSH server.'),
        required=True,
        tab=types.ui.Tab.PARAMETERS,
    )
    sshHostKey = gui.TextField(
        label=_('SSH Host Key'),
        order=34,
        tooltip=_('Host key of the SSH server. If not provided, no verification of host identity is done.'),
        tab=types.ui.Tab.PARAMETERS,
    )
    serverKeepAlive = gui.NumericField(
        length=3,
        label=_('Server Keep Alive'),
        default=30,
        order=35,
        tooltip=_(
            'Time in seconds between keep alive messages sent to server. If not provided, no keep alive messages are sent.'
        ),
        required=True,
        minValue=0,
        tab=types.ui.Tab.PARAMETERS,
    )

    ticketValidity = fields.tunnel_ricket_validity_field()

    forceNewWindow = HTML5RDPTransport.forceNewWindow
    customGEPath = HTML5RDPTransport.customGEPath

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return

    def is_ip_allowed(self, userService: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            # Check again for readyness
            if self.test_connectivity(userService, ip, self.sshPort.value) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def get_link(
        self,
        userService: 'models.UserService',  # pylint: disable=unused-argument
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',  # pylint: disable=unused-argument
        user: 'models.User',  # pylint: disable=unused-argument
        password: str,  # pylint: disable=unused-argument
        request: 'ExtendedHttpRequestWithUser',  # pylint: disable=unused-argument
    ) -> str:
        # Build params dict
        params = {
            'protocol': 'ssh',
            'hostname': ip,
            'port': str(self.sshPort.num()),
        }

        # Optional numeric keep alive. If less than 2, it is not sent
        if self.serverKeepAlive.num() >= 2:
            params['server-alive-interval'] = str(self.serverKeepAlive.num())

        # Add optional parameters (strings only)
        for i in (
            ('username', self.username),
            # ('password', self.password),
            # ('private-key', self.sshPrivateKey),
            # ('passphrase', self.sshPassphrase),
            ('command', self.sshCommand),
            ('host-key', self.sshHostKey),
        ):
            if i[1].value.strip():
                params[i[0]] = i[1].value.strip()

        # Filesharing using guacamole sftp
        if self.enableFileSharing.value != 'false':
            params['enable-sftp'] = 'true'

            if self.fileSharingRoot.value.strip():
                params['sftp-root-directory'] = self.fileSharingRoot.value.strip()

            if self.enableFileSharing.value not in ('down', 'true'):
                params['sftp-disable-download'] = 'true'

            if self.enableFileSharing.value not in ('up', 'true'):
                params['sftp-disable-upload'] = 'true'

        logger.debug('SSH Params: %s', params)

        scrambler = CryptoManager().random_string(32)
        ticket = models.TicketStore.create(params, validity=self.ticketValidity.num())

        onw = ''
        if self.forceNewWindow.value == 'true':
            onw = 'o_n_w={}'
        elif self.forceNewWindow.value == 'overwrite':
            onw = 'o_s_w=yes'
        onw = onw.format(hash(transport.name))

        path = self.customGEPath.value if self.useGlyptodonTunnel.as_bool() else '/guacamole'
        # Remove trailing /
        path = path.rstrip('/')

        tunnelServer = fields.get_tunnel_from_field(self.tunnel)
        return str(f'https://{tunnelServer.host}:{tunnelServer.port}{path}/#/?data={ticket}.{scrambler}{onw}')
