# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import random
import string
import typing


from django.utils.translation import ugettext_noop as _
from uds.core.ui import gui
from uds.core import transports
from uds.core.util import os_detector as OsDetector
from uds.models import TicketStore

from .spice_base import BaseSpiceTransport
from .remote_viewer_file import RemoteViewerFile

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import Module
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports

logger = logging.getLogger(__name__)


class TSPICETransport(BaseSpiceTransport):
    """
    Provides access via SPICE to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """
    typeName = _('SPICE')
    typeType = 'TSSPICETransport'
    typeDescription = _('SPICE Protocol. Tunneled connection.')
    protocol = transports.protocols.SPICE
    group: typing.ClassVar[str] = transports.TUNNELED_GROUP

    tunnelServer = gui.TextField(label=_('Tunnel server'), order=1, tooltip=_('IP or Hostname of tunnel server sent to client device ("public" ip) and port. (use HOST:PORT format)'), tab=gui.TUNNEL_TAB)

    serverCertificate = BaseSpiceTransport.serverCertificate
    fullScreen = BaseSpiceTransport.fullScreen
    usbShare = BaseSpiceTransport.usbShare
    autoNewUsbShare = BaseSpiceTransport.autoNewUsbShare
    smartCardRedirect = BaseSpiceTransport.smartCardRedirect

    def initialize(self, values: 'Module.ValuesType'):
        if values:
            if values['tunnelServer'].count(':') != 1:
                raise transports.Transport.ValidationException(_('Must use HOST:PORT in Tunnel Server Field'))

    def getUDSTransportScript(  # pylint: disable=too-many-locals
            self,
            userService: 'models.UserService',
            transport: 'models.Transport',
            ip: str,
            os: typing.Dict[str, str],
            user: 'models.User',
            password: str,
            request: 'HttpRequest'
        ) -> typing.Tuple[str, str, typing.Dict[str, typing.Any]]:
        userServiceInstance: typing.Any = userService.getInstance()

        # Spice connection
        con = userServiceInstance.getConsoleConnection()
        port: str = con['port'] or '-1'
        secure_port: str = con['secure_port'] or '-1'

        # Ticket
        tunpass = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _i in range(12))
        tunuser = TicketStore.create(tunpass)

        sshHost, sshPort = self.tunnelServer.value.split(':')

        r = RemoteViewerFile(
            '127.0.0.1', '{port}', '{secure_port}', con['ticket']['value'],
            self.serverCertificate.value.strip(), con['cert_subject'], fullscreen=self.fullScreen.isTrue()
        )
        r.usb_auto_share = self.usbShare.isTrue()
        r.new_usb_auto_share = self.autoNewUsbShare.isTrue()
        r.smartcard = self.smartCardRedirect.isTrue()

        osName = {
            OsDetector.Windows: 'windows',
            OsDetector.Linux: 'linux',
            OsDetector.Macintosh: 'macosx'
        }.get(os['OS'])

        if osName is None:
            return super().getUDSTransportScript(userService, transport, ip, os, user, password, request)

        # if sso:  # If SSO requested, and when supported by platform
        #     userServiceInstance.desktopLogin(user, password, '')

        sp = {
            'as_file': r.as_file,
            'as_file_ns': r.as_file_ns,
            'tunUser': tunuser,
            'tunPass': tunpass,
            'tunHost': sshHost,
            'tunPort': sshPort,
            'ip': con['address'],
            'port': port,
            'secure_port': secure_port
        }

        return self.getScript('scripts/{}/tunnel.py', osName, sp)
