# -*- coding: utf-8 -*-
#
# Copyright (c) 2016-2021 Virtual Cable S.L.U.
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
from uds.core.managers.user_preferences import CommonPrefs
from uds.core.util import os_detector as OsDetector
from uds.core.util import tools, validators
from uds.core import transports
from uds.models import TicketStore
from .x2go_base import BaseX2GOTransport
from . import x2go_file

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import Module
    from uds.core.util.request import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)


class TX2GOTransport(BaseX2GOTransport):
    """
    Provides access via X2GO to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """
    isBase = False

    iconFile = 'x2go-tunnel.png'
    typeName = _('X2Go')
    typeType = 'TX2GOTransport'
    typeDescription = _('X2Go access (Experimental). Tunneled connection.')
    group = transports.TUNNELED_GROUP

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

    fixedName = BaseX2GOTransport.fixedName
    screenSize = BaseX2GOTransport.screenSize
    desktopType = BaseX2GOTransport.desktopType
    customCmd = BaseX2GOTransport.customCmd
    sound = BaseX2GOTransport.sound
    exports = BaseX2GOTransport.exports
    speed = BaseX2GOTransport.speed

    soundType = BaseX2GOTransport.soundType
    keyboardLayout = BaseX2GOTransport.keyboardLayout
    pack = BaseX2GOTransport.pack
    quality = BaseX2GOTransport.quality

    def initialize(self, values: 'Module.ValuesType'):
        if values:
            validators.validateHostPortPair(values.get('tunnelServer', ''))

    def getUDSTransportScript(
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: typing.Dict[str, typing.Any],
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> 'transports.TransportScript':

        ci = self.getConnectionInfo(userService, user, password)
        username = ci['username']

        priv, pub = self.getAndPushKey(username, userService)

        width, height = self.getScreenSize()

        rootless = False
        desktop = self.desktopType.value
        if desktop == "UDSVAPP":
            desktop = "/usr/bin/udsvapp " + self.customCmd.value
            rootless = True

        xf = x2go_file.getTemplate(
            speed=self.speed.value,
            pack=self.pack.value,
            quality=self.quality.value,
            sound=self.sound.isTrue(),
            soundSystem=self.sound.value,
            windowManager=desktop,
            exports=self.exports.isTrue(),
            rootless=rootless,
            width=width,
            height=height,
            user=username,
        )

        ticket = TicketStore.create_for_tunnel(
            userService=userService,
            port=22,
            validity=self.tunnelWait.num() + 60,  # Ticket overtime
        )

        tunHost, tunPort = self.tunnelServer.value.split(':')

        # data
        data = {
            'os': os['OS'],
            'ip': ip,
            'port': 22,
            'key': priv,
            'width': width,
            'height': height,
            'printers': True,
            'drives': self.exports.isTrue(),
            'fullScreen': width == -1 or height == -1,
            'this_server': request.build_absolute_uri('/'),
            'xf': xf,
        }

        m = tools.DictAsObj(data)

        osName = {
            OsDetector.KnownOS.Windows: 'windows',
            OsDetector.KnownOS.Linux: 'linux',
            # OsDetector.Macintosh: 'macosx'
        }.get(os['OS'])

        if osName is None:
            return super().getUDSTransportScript(
                userService, transport, ip, os, user, password, request
            )

        sp = {
            'tunHost': tunHost,
            'tunPort': tunPort,
            'tunWait': self.tunnelWait.num(),
            'tunChk': self.verifyCertificate.isTrue(),
            'ticket': ticket,
            'key': priv,
            'xf': xf,
        }

        return self.getScript('scripts/{}/tunnel.py', osName, sp)
