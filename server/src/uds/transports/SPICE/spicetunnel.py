# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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

from uds.core import exceptions, types
from uds.core.ui import gui
from uds.core.util import fields
from uds.models import TicketStore

from .remote_viewer_file import RemoteViewerFile
from .spice_base import BaseSpiceTransport

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


class TSPICETransport(BaseSpiceTransport):
    """
    Provides access via SPICE to service.
    """
    is_base = False

    icon_file = 'spice-tunnel.png'
    type_name = _('SPICE')
    type_type = 'TSSPICETransport'
    type_description = _('SPICE Protocol. Tunneled connection.')
    protocol = types.transports.Protocol.SPICE
    group = types.transports.Grouping.TUNNELED

    tunnel = fields.tunnel_field()
    tunnel_wait = fields.tunnel_wait_time_field()

    verify_certificate = gui.CheckBoxField(
        label=_('Force SSL certificate verification'),
        order=23,
        tooltip=_(
            'If enabled, the certificate of tunnel server will be verified (recommended).'
        ),
        default=False,
        tab=types.ui.Tab.TUNNEL,
        old_field_name='verifyCertificate',
    )

    server_certificate = BaseSpiceTransport.server_certificate
    fullscreen = BaseSpiceTransport.fullscreen
    allow_usb_redirection = BaseSpiceTransport.allow_usb_redirection
    allow_usb_redirection_new_plugs = BaseSpiceTransport.allow_usb_redirection_new_plugs
    allow_smartcards = BaseSpiceTransport.allow_smartcards
    ssl_connection = BaseSpiceTransport.ssl_connection

    def initialize(self, values: 'types.core.ValuesType') -> None:
        pass

    def get_transport_script(  # pylint: disable=too-many-locals
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> types.transports.TransportScript:
        try:
            userServiceInstance = userservice.get_instance()
            con = userServiceInstance.get_console_connection()
        except Exception:
            logger.exception('Error getting console connection data')
            raise

        if not con:
            raise exceptions.transport.TransportError(
                _('No console connection data received'),
            )

        tunnelFields = fields.get_tunnel_from_field(self.tunnel)
        tunHost, tunPort = tunnelFields.host, tunnelFields.port

        # We MAY need two tickets, one for 'insecure' port an one for secure
        ticket = ''
        ticket_secure = ''

        if con.proxy:
            logger.exception('Proxied SPICE tunnels are not suppoorted')
            return super().get_transport_script(
                userservice, transport, ip, os, user, password, request
            )

        key = self.generate_key()
        if con.port:
            ticket = TicketStore.create_for_tunnel(
                userservice=userservice,
                port=int(con.port),
                validity=self.tunnel_wait.as_int() + 60,  # Ticket overtime
                key=key,
            )

        if con.secure_port:
            ticket_secure = TicketStore.create_for_tunnel(
                userservice=userservice,
                port=int(con.secure_port),
                host=con.address,
                validity=self.tunnel_wait.as_int() + 60,  # Ticket overtime
                key=key,
            )

        r = RemoteViewerFile(
            '127.0.0.1',
            '{port}',
            '{secure_port}',
            con.ticket.value,  # This is secure ticket from kvm, not UDS ticket
            con.ca or self.server_certificate.value.strip(),
            con.cert_subject,
            fullscreen=self.fullscreen.as_bool(),
        )

        r.usb_auto_share = self.allow_usb_redirection.as_bool()
        r.new_usb_auto_share = self.allow_usb_redirection_new_plugs.as_bool()
        r.smartcard = self.allow_smartcards.as_bool()
        r.ssl_connection = self.ssl_connection.as_bool()

        # if sso:  # If SSO requested, and when supported by platform
        #     userServiceInstance.desktop_login(user, password, '')

        sp = {
            'as_file': r.as_file,
            'as_file_ns': r.as_file_ns,
            'tunHost': tunHost,
            'tunPort': tunPort,
            'tunWait': self.tunnel_wait.as_int(),
            'tunChk': self.verify_certificate.as_bool(),
            'ticket': ticket,
            'ticket_secure': ticket_secure,
            'tunnel_key': key,
        }

        try:
            return self.get_script(os.os.os_name(), 'tunnel', sp)
        except Exception:
            return super().get_transport_script(
                userservice, transport, ip, os, user, password, request
            )
