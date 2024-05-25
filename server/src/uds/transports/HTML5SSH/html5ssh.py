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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds import models
from uds.core import consts, transports, types
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui
from uds.core.util import fields

from ..HTML5RDP.html5rdp import HTML5RDPTransport

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

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

    use_glyptodon = HTML5RDPTransport.use_glyptodon

    username = gui.TextField(
        label=_('Username'),
        order=20,
        tooltip=_('Username for SSH connection authentication.'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='username'
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

    ssh_command = gui.TextField(
        label=_('SSH Command'),
        order=30,
        tooltip=_(
            'Command to execute on the remote server. If not provided, an interactive shell will be executed.'
        ),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='sshCommand'
    )
    enable_file_sharing = HTML5RDPTransport.enable_file_sharing
    filesharing_root = gui.TextField(
        label=_('File Sharing Root'),
        order=32,
        tooltip=_('Root path for file sharing. If not provided, root directory will be used.'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='fileSharingRoot'
    )
    ssh_port = gui.NumericField(
        length=40,
        label=_('SSH Server port'),
        default=22,
        order=33,
        tooltip=_('Port of the SSH server.'),
        required=True,
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='sshPort'
    )
    ssh_host_key = gui.TextField(
        label=_('SSH Host Key'),
        length=512,
        order=34,
        tooltip=_('Host key of the SSH server. If not provided, no verification of host identity is done. (as the line in known_hosts file)'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='sshHostKey'
    )
    server_keep_alive = gui.NumericField(
        length=3,
        label=_('Server Keep Alive'),
        default=30,
        order=35,
        tooltip=_(
            'Time in seconds between keep alive messages sent to server. If not provided, no keep alive messages are sent.'
        ),
        required=True,
        min_value=0,
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='serverKeepAlive'
    )

    ticket_validity = fields.tunnel_ticket_validity_field()

    force_new_window = HTML5RDPTransport.force_new_window
    custom_glyptodon_path = HTML5RDPTransport.custom_glyptodon_path


    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            # Check again for readyness
            if self.test_connectivity(userservice, ip, self.ssh_port.value) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def get_link(
        self,
        userservice: 'models.UserService',  # pylint: disable=unused-argument
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
            'port': str(self.ssh_port.as_int()),
        }

        # Optional numeric keep alive. If less than 2, it is not sent
        if self.server_keep_alive.as_int() >= 2:
            params['server-alive-interval'] = str(self.server_keep_alive.as_int())

        # Add optional parameters (strings only)
        for i in (
            ('username', self.username),
            # ('password', self.password),
            # ('private-key', self.sshPrivateKey),
            # ('passphrase', self.sshPassphrase),
            ('command', self.ssh_command),
            ('host-key', self.ssh_host_key),
        ):
            if i[1].value.strip():
                params[i[0]] = i[1].value.strip()

        # Filesharing using guacamole sftp
        if self.enable_file_sharing.value != 'false':
            params['enable-sftp'] = 'true'

            if self.filesharing_root.value.strip():
                params['sftp-root-directory'] = self.filesharing_root.value.strip()

            if self.enable_file_sharing.value not in ('down', 'true'):
                params['sftp-disable-download'] = 'true'

            if self.enable_file_sharing.value not in ('up', 'true'):
                params['sftp-disable-upload'] = 'true'

        logger.debug('SSH Params: %s', params)

        scrambler = CryptoManager().random_string(32)
        ticket = models.TicketStore.create(params, validity=self.ticket_validity.as_int())

        onw = f'&{consts.transports.ON_NEW_WINDOW_VAR}={transport.uuid}'
        if self.force_new_window.value == consts.TRUE_STR:
            onw = f'&{consts.transports.ON_NEW_WINDOW_VAR}={userservice.deployed_service.uuid}'
        elif self.force_new_window.value == 'overwrite':
            onw = f'&{consts.transports.ON_SAME_WINDOW_VAR}=yes'
        path = self.custom_glyptodon_path.value if self.use_glyptodon.as_bool() else '/guacamole'
        # Remove trailing /
        path = path.rstrip('/')

        tunnel_server = fields.get_tunnel_from_field(self.tunnel)
        return f'https://{tunnel_server.host}:{tunnel_server.port}{path}/#/?data={ticket}.{scrambler}{onw}'
