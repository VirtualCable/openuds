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

from django.utils.translation import ugettext_noop as _
from django.urls import reverse
from django.http import HttpResponseRedirect

from uds.core.ui import gui

from uds.core import transports

from uds.core.util import os_detector as OsDetector
from uds.core.managers import cryptoManager
from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports

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

    guacamoleServer = gui.TextField(label=_('Tunnel Server'), order=1, tooltip=_('Host of the tunnel server (use http/https & port if needed) as accesible from users'), defvalue='https://', length=64, required=True, tab=gui.TUNNEL_TAB)

    username = gui.TextField(label=_('Username'), order=20, tooltip=_('Username for VNC connection authentication.'), tab=gui.PARAMETERS_TAB)
    password = gui.PasswordField(label=_('Password'), order=21, tooltip=_('Password for VNC connection authentication'), tab=gui.PARAMETERS_TAB)

    vncPort = gui.NumericField(
        length=22,
        label=_('VNC Server port'),
        defvalue='5900',
        order=2,
        tooltip=_('Port of the VNC server.'),
        required=True,
        tab=gui.PARAMETERS_TAB
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
        tab=gui.PARAMETERS_TAB
    )
    swapRedBlue = gui.CheckBoxField(label=_('Swap red/blue'), order=27, tooltip=_('Use this if your colours seems incorrect (blue appears red, ..) to swap them.'), tab=gui.PARAMETERS_TAB)
    cursor = gui.CheckBoxField(label=_('Remote cursor'), order=28, tooltip=_('If set, force to show remote cursor'), tab=gui.PARAMETERS_TAB)
    readOnly = gui.CheckBoxField(label=_('Read only'), order=29, tooltip=_('If set, the connection will be read only'), tab=gui.PARAMETERS_TAB)
        
    ticketValidity = gui.NumericField(
        length=3,
        label=_('Ticket Validity'),
        defvalue='60',
        order=90,
        tooltip=_('Allowed time, in seconds, for HTML5 client to reload data from UDS Broker. The default value of 60 is recommended.'),
        required=True,
        minValue=60,
        tab=gui.ADVANCED_TAB
    )
    forceNewWindow = gui.CheckBoxField(
        label=_('Force new HTML Window'),
        order=91,
        tooltip=_('If checked, every connection will try to open its own window instead of reusing the "global" one.'),
        defvalue=gui.FALSE,
        tab=gui.ADVANCED_TAB
    )

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return
        # Strip spaces
        self.guacamoleServer.value = self.guacamoleServer.value.strip()
        if self.guacamoleServer.value[0:4] != 'http':
            raise transports.Transport.ValidationException(_('The server must be http or https'))

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

    def getLink(  # pylint: disable=too-many-locals
            self,
            userService: 'models.UserService',
            transport: 'models.Transport',
            ip: str,
            os: typing.Dict[str, str],
            user: 'models.User',
            password: str,
            request: 'HttpRequest'
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

        onw = '&o_n_w={};'.format(hash(transport.name)) if self.forceNewWindow.isTrue() else ''
        return str(
            "{}/guacamole/#/?data={}.{}{}".format(
                self.guacamoleServer.value,
                ticket,
                scrambler,
                onw
            )
        )
