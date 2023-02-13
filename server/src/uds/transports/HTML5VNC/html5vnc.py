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
import typing

from django.utils.translation import gettext_noop as _

from uds.core.ui import gui
from uds.core import transports, exceptions
from uds.core.util import os_detector as OsDetector
from uds.core.managers import cryptoManager
from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module
    from uds.core.util.request import ExtendedHttpRequestWithUser
    from uds.core.util.os_detector import DetectedOsInfo

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class HTML5VNCTransport(transports.Transport):
    """
    Provides access via VNC to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeName = _('HTML5 VNC Experimental')
    typeType = 'HTML5VNCTransport'
    typeDescription = _('VNC protocol using HTML5 client (EXPERIMENTAL)')
    iconFile = 'html5vnc.png'

    ownLink = True
    supportedOss = OsDetector.allOss
    protocol = transports.protocols.VNC
    group = transports.TUNNELED_GROUP

    guacamoleServer = gui.TextField(
        label=_('Tunnel Server'),
        order=1,
        tooltip=_(
            'Host of the tunnel server (use http/https & port if needed) as accesible from users'
        ),
        defvalue='https://',
        length=64,
        required=True,
        tab=gui.Tab.TUNNEL,
    )

    username = gui.TextField(
        label=_('Username'),
        order=20,
        tooltip=_('Username for VNC connection authentication.'),
        tab=gui.Tab.PARAMETERS,
    )
    password = gui.PasswordField(
        label=_('Password'),
        order=21,
        tooltip=_('Password for VNC connection authentication'),
        tab=gui.Tab.PARAMETERS,
    )

    vncPort = gui.NumericField(
        length=22,
        label=_('VNC Server port'),
        defvalue='5900',
        order=2,
        tooltip=_('Port of the VNC server.'),
        required=True,
        tab=gui.Tab.PARAMETERS,
    )

    colorDepth = gui.ChoiceField(
        order=26,
        label=_('Color depth'),
        tooltip=_('Color depth for VNC connection. Use this to control bandwidth.'),
        required=True,
        values=[
            gui.choiceItem('-', 'default'),
            gui.choiceItem('8', '8 bits'),
            gui.choiceItem('16', '16 bits'),
            gui.choiceItem('24', '24 bits'),
            gui.choiceItem('32', '33 bits'),
        ],
        defvalue='-',
        tab=gui.Tab.PARAMETERS,
    )
    swapRedBlue = gui.CheckBoxField(
        label=_('Swap red/blue'),
        order=27,
        tooltip=_(
            'Use this if your colours seems incorrect (blue appears red, ..) to swap them.'
        ),
        tab=gui.Tab.PARAMETERS,
    )
    cursor = gui.CheckBoxField(
        label=_('Remote cursor'),
        order=28,
        tooltip=_('If set, force to show remote cursor'),
        tab=gui.Tab.PARAMETERS,
    )
    readOnly = gui.CheckBoxField(
        label=_('Read only'),
        order=29,
        tooltip=_('If set, the connection will be read only'),
        tab=gui.Tab.PARAMETERS,
    )

    ticketValidity = gui.NumericField(
        length=3,
        label=_('Ticket Validity'),
        defvalue='60',
        order=90,
        tooltip=_(
            'Allowed time, in seconds, for HTML5 client to reload data from UDS Broker. The default value of 60 is recommended.'
        ),
        required=True,
        minValue=60,
        tab=gui.Tab.ADVANCED,
    )
    forceNewWindow = gui.ChoiceField(
        order=91,
        label=_('Force new HTML Window'),
        tooltip=_('Select windows behavior for new connections on HTML5'),
        required=True,
        values=[
            gui.choiceItem(
                gui.FALSE,
                _('Open every connection on the same window, but keeps UDS window.'),
            ),
            gui.choiceItem(
                gui.TRUE, _('Force every connection to be opened on a new window.')
            ),
            gui.choiceItem(
                'overwrite',
                _('Override UDS window and replace it with the connection.'),
            ),
        ],
        defvalue=gui.FALSE,
        tab=gui.Tab.ADVANCED,
    )

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return
        # Strip spaces
        # Remove trailing / (one or more) from url if it exists from "guacamoleServer" field
        self.guacamoleServer.value = self.guacamoleServer.value.strip().rstrip('/')
        if self.guacamoleServer.value[0:4] != 'http':
            raise exceptions.ValidationException(
                _('The server must be http or https')
            )

    def isAvailableFor(self, userService: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            # Check again for readyness
            if self.testServer(userService, ip, self.vncPort.value) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def getLink(
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'DetectedOsInfo',
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

        scrambler = cryptoManager().randomString(32)
        ticket = models.TicketStore.create(params, validity=self.ticketValidity.num())

        onw = ''
        if self.forceNewWindow.value == gui.TRUE:
            onw = 'o_n_w={}'
        elif self.forceNewWindow.value == 'overwrite':
            onw = 'o_s_w=yes'
        onw = onw.format(hash(transport.name))

        return str(
            "{}/guacamole/#/?data={}.{}{}".format(
                self.guacamoleServer.value, ticket, scrambler, onw
            )
        )
