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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import transports, types, consts
from uds.core.ui import gui
from uds.core.util import fields, validators
from uds.models import TicketStore

from .rdp_base import BaseRDPTransport
from .rdp_file import RDPFile

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.module import Module
    from uds.core.types.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class TRDPTransport(BaseRDPTransport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    isBase = False

    iconFile = 'rdp-tunnel.png'
    typeName = _('RDP')
    typeType = 'TSRDPTransport'
    typeDescription = _('RDP Protocol. Tunneled connection.')
    group = transports.TUNNELED_GROUP

    tunnel = fields.tunnelField()

    tunnelWait = fields.tunnelTunnelWait()

    verifyCertificate = gui.CheckBoxField(
        label=_('Force SSL certificate verification'),
        order=23,
        tooltip=_('If enabled, the certificate of tunnel server will be verified (recommended).'),
        default=False,
        tab=types.ui.Tab.TUNNEL,
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
    # optimizeTeams = BaseRDPTransport.optimizeTeams

    def initialize(self, values: 'Module.ValuesType'):
        if values:
            validators.validateHostPortPair(values.get('tunnelServer', ''))

    def getUDSTransportScript(  # pylint: disable=too-many-locals
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> 'transports.TransportScript':
        # We use helper to keep this clean

        ci = self.getConnectionInfo(userService, user, password)

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

        tunnelFields = fields.getTunnelFromField(self.tunnel)
        tunHost, tunPort = tunnelFields.host, tunnelFields.port

        r = RDPFile(width == '-1' or height == '-1', width, height, depth, target=os.os)
        #r.enablecredsspsupport = ci.get('sso') == 'True' or self.credssp.isTrue()
        r.enablecredsspsupport = self.credssp.isTrue()
        r.address = '{address}'
        r.username = ci.username
        r.password = ci.password
        r.domain = ci.domain

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
        r.optimizeTeams = self.optimizeTeams.isTrue()

        sp: collections.abc.MutableMapping[str, typing.Any] = {
            'tunHost': tunHost,
            'tunPort': tunPort,
            'tunWait': self.tunnelWait.num(),
            'tunChk': self.verifyCertificate.isTrue(),
            'ticket': ticket,
            'password': ci.password,
            'this_server': request.build_absolute_uri('/'),
        }

        if os.os == types.os.KnownOS.WINDOWS:
            r.customParameters = self.customParametersWindows.value
            if ci.password:
                r.password = '{password}'  # nosec: password is not hardcoded
            sp.update(
                {
                    'as_file': r.as_file,
                    'optimize_teams': self.optimizeTeams.isTrue(),
                }
            )
        elif os.os == types.os.KnownOS.LINUX:
            r.customParameters = self.customParameters.value
            sp.update(
                {
                    'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                }
            )
        elif os.os == types.os.KnownOS.MAC_OS:
            r.customParameters = self.customParametersMAC.value
            sp.update(
                {
                    'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                    'as_file': r.as_file if self.allowMacMSRDC.isTrue() else '',
                    'as_rdp_url': r.as_rdp_url if self.allowMacMSRDC.isTrue() else '',
                }
            )
        else:
            logger.error(
                'Os not valid for RDP Transport: %s',
                request.META.get('HTTP_USER_AGENT', 'Unknown'),
            )
            return super().getUDSTransportScript(userService, transport, ip, os, user, password, request)

        return self.getScript(os.os.os_name(), 'tunnel', sp)
