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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing


from django.utils.translation import gettext_noop as _
from uds.core.ui import gui
from uds.core import transports, exceptions
from uds.core.util import validators
from uds.models import TicketStore

from .spice_base import BaseSpiceTransport
from .remote_viewer_file import RemoteViewerFile

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.module import Module
    from uds.core.util.request import ExtendedHttpRequestWithUser
    from uds.core.util import os_detector

logger = logging.getLogger(__name__)


class TSPICETransport(BaseSpiceTransport):
    """
    Provides access via SPICE to service.
    """
    isBase = False

    iconFile = 'spice-tunnel.png'
    typeName = _('SPICE')
    typeType = 'TSSPICETransport'
    typeDescription = _('SPICE Protocol. Tunneled connection.')
    protocol = transports.protocols.SPICE
    group: typing.ClassVar[str] = transports.TUNNELED_GROUP

    tunnelServer = gui.TextField(
        label=_('Tunnel server'),
        order=1,
        tooltip=_(
            'IP or Hostname of tunnel server sent to client device ("public" ip) and port. (use HOST:PORT format)'
        ),
        tab=gui.Tab.TUNNEL,
    )

    tunnelWait = gui.NumericField(
        length=3,
        label=_('Tunnel wait time'),
        defvalue='30',
        minValue=5,
        maxValue=65536,
        order=2,
        tooltip=_('Maximum time to wait before closing the tunnel listener'),
        required=True,
        tab=gui.Tab.TUNNEL,
    )

    verifyCertificate = gui.CheckBoxField(
        label=_('Force SSL certificate verification'),
        order=23,
        tooltip=_(
            'If enabled, the certificate of tunnel server will be verified (recommended).'
        ),
        defvalue=gui.FALSE,
        tab=gui.Tab.TUNNEL,
    )

    serverCertificate = BaseSpiceTransport.serverCertificate
    fullScreen = BaseSpiceTransport.fullScreen
    usbShare = BaseSpiceTransport.usbShare
    autoNewUsbShare = BaseSpiceTransport.autoNewUsbShare
    smartCardRedirect = BaseSpiceTransport.smartCardRedirect
    sslConnection = BaseSpiceTransport.SSLConnection

    def initialize(self, values: 'Module.ValuesType'):
        if values:
            validators.validateHostPortPair(values.get('tunnelServer', ''))

    def getUDSTransportScript(  # pylint: disable=too-many-locals
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'os_detector.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> transports.TransportScript:
        try:
            userServiceInstance = userService.getInstance()
            con = userServiceInstance.getConsoleConnection()
        except Exception:
            logger.exception('Error getting console connection data')
            raise

        if not con:
            raise exceptions.TransportError(
                _('No console connection data received'),
            )

        tunHost, tunPort = self.tunnelServer.value.split(':')

        # We MAY need two tickets, one for 'insecure' port an one for secure
        ticket = ''
        ticket_secure = ''

        if 'proxy' in con:
            logger.exception('Proxied SPICE tunnels are not suppoorted')
            return super().getUDSTransportScript(
                userService, transport, ip, os, user, password, request
            )

        if con['port']:
            ticket = TicketStore.create_for_tunnel(
                userService=userService,
                port=int(con['port']),
                validity=self.tunnelWait.num() + 60,  # Ticket overtime
            )

        if con['secure_port']:
            ticket_secure = TicketStore.create_for_tunnel(
                userService=userService,
                port=int(con['secure_port']),
                host=con['address'],
                validity=self.tunnelWait.num() + 60,  # Ticket overtime
            )

        r = RemoteViewerFile(
            '127.0.0.1',
            '{port}',
            '{secure_port}',
            con['ticket']['value'],  # This is secure ticket from kvm, not UDS ticket
            con.get('ca', self.serverCertificate.value.strip()),
            con['cert_subject'],
            fullscreen=self.fullScreen.isTrue(),
        )

        r.usb_auto_share = self.usbShare.isTrue()
        r.new_usb_auto_share = self.autoNewUsbShare.isTrue()
        r.smartcard = self.smartCardRedirect.isTrue()
        r.ssl_connection = self.sslConnection.isTrue()

        # if sso:  # If SSO requested, and when supported by platform
        #     userServiceInstance.desktopLogin(user, password, '')

        sp = {
            'as_file': r.as_file,
            'as_file_ns': r.as_file_ns,
            'tunHost': tunHost,
            'tunPort': tunPort,
            'tunWait': self.tunnelWait.num(),
            'tunChk': self.verifyCertificate.isTrue(),
            'ticket': ticket,
            'ticket_secure': ticket_secure,
        }

        try:
            return self.getScript(os.os.os_name(), 'tunnel', sp)
        except Exception:
            return super().getUDSTransportScript(
                userService, transport, ip, os, user, password, request
            )
