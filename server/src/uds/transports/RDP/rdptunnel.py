# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

from django.utils.translation import ugettext_noop as _
from uds.core.ui import gui
from uds.core import transports
from uds.models import TicketStore
from uds.core.util import os_detector as OsDetector

from .rdp_base import BaseRDPTransport
from .rdp_file import RDPFile


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import Module
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class TRDPTransport(BaseRDPTransport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """
    iconFile = 'rdp-tunnel.png'
    typeName = _('RDP')
    typeType = 'TSRDPTransport'
    typeDescription = _('RDP Protocol. Tunneled connection.')
    group = transports.TUNNELED_GROUP

    tunnelServer = gui.TextField(
        label=_('Tunnel server'),
        order=1,
        tooltip=_(
            'IP or Hostname of tunnel server sent to client device ("public" ip) and port. (use HOST:PORT format)'
        ),
        tab=gui.TUNNEL_TAB,
    )

    tunnelWait = gui.NumericField(
        length=3,
        label=_('Tunnel wait time'),
        defvalue='60',
        minValue=5,
        maxValue=65536,
        order=2,
        tooltip=_('Maximum time to wait before closing the tunnel listener'),
        required=True,
        tab=gui.TUNNEL_TAB,
    )

    verifyCertificate = gui.CheckBoxField(
        label=_('Force SSL certificate verification'),
        order=23,
        tooltip=_(
            'If enabled, the certificate of tunnel server will be verified (recommended).'
        ),
        defvalue=gui.FALSE,
        tab=gui.TUNNEL_TAB,
    )

    useEmptyCreds = BaseRDPTransport.useEmptyCreds
    fixedName = BaseRDPTransport.fixedName
    fixedPassword = BaseRDPTransport.fixedPassword
    withoutDomain = BaseRDPTransport.withoutDomain
    fixedDomain = BaseRDPTransport.fixedDomain
    allowSmartcards = BaseRDPTransport.allowSmartcards
    allowPrinters = BaseRDPTransport.allowPrinters
    allowDrives = BaseRDPTransport.allowDrives
    enforceDrives = BaseRDPTransport.enforceDrives
    allowSerials = BaseRDPTransport.allowSerials
    allowClipboard = BaseRDPTransport.allowClipboard
    allowAudio = BaseRDPTransport.allowAudio
    allowWebcam = BaseRDPTransport.allowWebcam
    usbRedirection = BaseRDPTransport.usbRedirection

    wallpaper = BaseRDPTransport.wallpaper
    multimon = BaseRDPTransport.multimon
    aero = BaseRDPTransport.aero
    smooth = BaseRDPTransport.smooth
    showConnectionBar = BaseRDPTransport.showConnectionBar
    credssp = BaseRDPTransport.credssp
    rdpPort = BaseRDPTransport.rdpPort

    screenSize = BaseRDPTransport.screenSize
    colorDepth = BaseRDPTransport.colorDepth

    alsa = BaseRDPTransport.alsa
    multimedia = BaseRDPTransport.multimedia
    printerString = BaseRDPTransport.printerString
    smartcardString = BaseRDPTransport.smartcardString
    allowMacMSRDC = BaseRDPTransport.allowMacMSRDC
    customParameters = BaseRDPTransport.customParameters
    customParametersMAC = BaseRDPTransport.customParametersMAC
    customParametersWindows = BaseRDPTransport.customParametersWindows

    def initialize(self, values: 'Module.ValuesType'):
        if values:
            if values['tunnelServer'].count(':') != 1:
                raise transports.Transport.ValidationException(
                    _('Must use HOST:PORT in Tunnel Server Field')
                )

    def getUDSTransportScript(  # pylint: disable=too-many-locals
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: typing.Dict[str, typing.Any],
        user: 'models.User',
        password: str,
        request: 'HttpRequest',
    ) -> typing.Tuple[str, str, typing.Mapping[str, typing.Any]]:
        # We use helper to keep this clean
        # prefs = user.prefs('rdp')

        ci = self.getConnectionInfo(userService, user, password)
        username, password, domain = ci['username'], ci['password'], ci['domain']

        # escape conflicting chars : Note, on 3.0 this should not be neccesary. Kept until more tests
        # password = password.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

        # width, height = CommonPrefs.getWidthHeight(prefs)
        # depth = CommonPrefs.getDepth(prefs)
        width, height = self.screenSize.value.split('x')
        depth = self.colorDepth.value

        ticket = TicketStore.create_for_tunnel(
            userService=userService,
            port=self.rdpPort.num(),
            validity=self.tunnelWait.num() + 60,  # Ticket overtime
        )

        tunHost, tunPort = self.tunnelServer.value.split(':')

        r = RDPFile(
            width == '-1' or height == '-1', width, height, depth, target=os['OS']
        )
        r.enablecredsspsupport = ci.get('sso') == 'True' or self.credssp.isTrue()
        r.address = '{address}'
        r.username = username
        r.password = password
        r.domain = domain

        r.redirectPrinters = self.allowPrinters.isTrue()
        r.redirectSmartcards = self.allowSmartcards.isTrue()
        r.redirectDrives = self.allowDrives.value
        r.redirectSerials = self.allowSerials.isTrue()
        r.enableClipboard = self.allowClipboard.isTrue()
        r.redirectAudio = self.allowAudio.isTrue()
        r.redirectWebcam = self.allowWebcam.isTrue()
        r.showWallpaper = self.wallpaper.isTrue()
        r.multimon = self.multimon.isTrue()
        r.desktopComposition = self.aero.isTrue()
        r.smoothFonts = self.smooth.isTrue()
        r.displayConnectionBar = self.showConnectionBar.isTrue()
        r.enablecredsspsupport = self.credssp.isTrue()
        r.multimedia = self.multimedia.isTrue()
        r.alsa = self.alsa.isTrue()
        r.smartcardString = self.smartcardString.value
        r.printerString = self.printerString.value
        r.enforcedShares = self.enforceDrives.value
        r.redirectUSB = self.usbRedirection.value

        osName = {
            OsDetector.KnownOS.Windows: 'windows',
            OsDetector.KnownOS.Linux: 'linux',
            OsDetector.KnownOS.Macintosh: 'macosx',
        }.get(os['OS'])

        if osName is None:
            return super().getUDSTransportScript(
                userService, transport, ip, os, user, password, request
            )

        sp: typing.MutableMapping[str, typing.Any] = {
            'tunHost': tunHost,
            'tunPort': tunPort,
            'tunWait': self.tunnelWait.num(),
            'tunChk': self.verifyCertificate.isTrue(),
            'ticket': ticket,
            'password': password,
            'this_server': request.build_absolute_uri('/'),
        }

        if osName == 'windows':
            r.customParameters = self.customParametersWindows.value
            if password != '':
                r.password = '{password}'
            sp.update(
                {
                    'as_file': r.as_file,
                }
            )
        elif osName == 'linux':
            r.customParameters = self.customParameters.value
            sp.update(
                {
                    'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                }
            )
        else:  # Mac
            r.customParameters = self.customParametersMAC.value
            sp.update(
                {
                    'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                    'as_file': r.as_file if self.allowMacMSRDC.isTrue() else '',
                    'as_rdp_url': r.as_rdp_url if self.allowMacMSRDC.isTrue() else '',
                }
            )

        return self.getScript(osName, 'tunnel', sp)
