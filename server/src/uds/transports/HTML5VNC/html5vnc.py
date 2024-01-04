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


class HTML5VNCTransport(transports.Transport):
    """
    Provides access via VNC to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeName = _('HTML5 VNC')
    typeType = 'HTML5VNCTransport'
    typeDescription = _('VNC protocol using HTML5 client')
    iconFile = 'html5vnc.png'

    ownLink = True
    supportedOss = consts.os.ALL_OS_LIST
    protocol = transports.protocols.VNC
    group = transports.TUNNELED_GROUP
    experimental = True

    tunnel = fields.tunnelField()

    useGlyptodonTunnel = HTML5RDPTransport.useGlyptodonTunnel

    username = gui.TextField(
        label=_('Username'),
        order=20,
        tooltip=_('Username for VNC connection authentication.'),
        tab=types.ui.Tab.PARAMETERS,
    )
    password = gui.PasswordField(
        label=_('Password'),
        order=21,
        tooltip=_('Password for VNC connection authentication'),
        tab=types.ui.Tab.PARAMETERS,
    )

    vncPort = gui.NumericField(
        length=22,
        label=_('VNC Server port'),
        default=5900,
        order=2,
        tooltip=_('Port of the VNC server.'),
        required=True,
        tab=types.ui.Tab.PARAMETERS,
    )

    colorDepth = gui.ChoiceField(
        order=26,
        label=_('Color depth'),
        tooltip=_('Color depth for VNC connection. Use this to control bandwidth.'),
        required=True,
        choices=[
            gui.choiceItem('-', 'default'),
            gui.choiceItem('8', '8 bits'),
            gui.choiceItem('16', '16 bits'),
            gui.choiceItem('24', '24 bits'),
            gui.choiceItem('32', '33 bits'),
        ],
        default='-',
        tab=types.ui.Tab.PARAMETERS,
    )
    swapRedBlue = gui.CheckBoxField(
        label=_('Swap red/blue'),
        order=27,
        tooltip=_('Use this if your colours seems incorrect (blue appears red, ..) to swap them.'),
        tab=types.ui.Tab.PARAMETERS,
    )
    cursor = gui.CheckBoxField(
        label=_('Remote cursor'),
        order=28,
        tooltip=_('If set, force to show remote cursor'),
        tab=types.ui.Tab.PARAMETERS,
    )
    readOnly = gui.CheckBoxField(
        label=_('Read only'),
        order=29,
        tooltip=_('If set, the connection will be read only'),
        tab=types.ui.Tab.PARAMETERS,
    )

    ticketValidity = fields.tunnelTicketValidityField()

    forceNewWindow = HTML5RDPTransport.forceNewWindow
    customGEPath = HTML5RDPTransport.customGEPath

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return

    def isAvailableFor(self, userService: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            # Check again for readyness
            if self.test_connectivity(userService, ip, self.vncPort.value) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def getLink(
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> str:
        # Build params dict
        params = {
            'protocol': 'vnc',
            'hostname': ip,
            'port': str(self.vncPort.num()),
        }

        if self.username.value.strip():
            params['username'] = self.username.value.strip()

        if self.password.value.strip():
            params['password'] = self.password.value.strip()

        if self.colorDepth.value != '-':
            params['color-depth'] = self.colorDepth.value

        if self.swapRedBlue.isTrue():
            params['swap-red-blue'] = 'true'

        if self.cursor.isTrue():
            params['cursor'] = 'remote'

        if self.readOnly.isTrue():
            params['read-only'] = 'true'

        logger.debug('VNC Params: %s', params)

        scrambler = CryptoManager().random_string(32)
        ticket = models.TicketStore.create(params, validity=self.ticketValidity.num())

        onw = ''
        if self.forceNewWindow.value == 'true':
            onw = 'o_n_w={}'
        elif self.forceNewWindow.value == 'overwrite':
            onw = 'o_s_w=yes'
        onw = onw.format(hash(transport.name))

        path = self.customGEPath.value if self.useGlyptodonTunnel.isTrue() else '/guacamole'
        # Remove trailing /
        path = path.rstrip('/')

        tunnelServer = fields.getTunnelFromField(self.tunnel)
        return str(f'https://{tunnelServer.host}:{tunnelServer.port}{path}/#/?data={ticket}.{scrambler}{onw}')
