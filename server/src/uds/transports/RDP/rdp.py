# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
# All rights reservem.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import types

from .rdp_base import BaseRDPTransport
from .rdp_file import RDPFile

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class RDPTransport(BaseRDPTransport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''

    is_base = False

    type_name = _('RDP')
    type_type = 'RDPTransport'
    type_description = _('RDP Protocol. Direct connection.')

    force_empty_creds = BaseRDPTransport.force_empty_creds
    forced_username = BaseRDPTransport.forced_username
    forced_password = BaseRDPTransport.forced_password
    force_no_domain = BaseRDPTransport.force_no_domain
    forced_domain = BaseRDPTransport.forced_domain
    allow_smartcards = BaseRDPTransport.allow_smartcards
    allow_printers = BaseRDPTransport.allow_printers
    allow_drives = BaseRDPTransport.allow_drives
    enforce_drives = BaseRDPTransport.enforce_drives
    allow_serial_ports = BaseRDPTransport.allow_serial_ports
    allow_clipboard = BaseRDPTransport.allow_clipboard
    allow_audio = BaseRDPTransport.allow_audio
    allow_webcam = BaseRDPTransport.allow_webcam
    allow_usb_redirection = BaseRDPTransport.allow_usb_redirection

    wallpaper = BaseRDPTransport.wallpaper
    multimon = BaseRDPTransport.multimon
    aero = BaseRDPTransport.aero
    smooth = BaseRDPTransport.smooth
    show_connection_bar = BaseRDPTransport.show_connection_bar
    credssp = BaseRDPTransport.credssp
    rdp_port = BaseRDPTransport.rdp_port

    screen_size = BaseRDPTransport.screen_size
    color_depth = BaseRDPTransport.color_depth

    lnx_alsa = BaseRDPTransport.lnx_alsa
    lnx_multimedia = BaseRDPTransport.lnx_multimedia
    lnx_printer_string = BaseRDPTransport.lnx_printer_string
    lnx_smartcard_string = BaseRDPTransport.lnx_smartcard_string
    mac_allow_msrdc = BaseRDPTransport.mac_allow_msrdc
    lnx_custom_parameters = BaseRDPTransport.lnx_custom_parameters
    mac_custom_parameters = BaseRDPTransport.mac_custom_parameters
    wnd_custom_parameters = BaseRDPTransport.wnd_custom_parameters

    lnx_use_rdp_file = BaseRDPTransport.lnx_use_rdp_file

    def get_transport_script(  # pylint: disable=too-many-locals
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> 'types.transports.TransportScript':
        # We use helper to keep this clean

        ci = self.get_connection_info(userservice, user, password)

        # escape conflicting chars : Note, on 3.0 this should not be neccesary. Kept until more tests
        # password = password.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

        # width, height = CommonPrefs.getWidthHeight(prefs)
        # depth = CommonPrefs.getDepth(prefs)
        width, height = self.screen_size.value.split('x')
        depth = self.color_depth.value

        r = RDPFile(width == '-1' or height == '-1', width, height, depth, target=os.os)
        # r.enablecredsspsupport = ci.get('sso') == 'True' or self.credssp.as_bool()
        r.enable_credssp_support = self.credssp.as_bool()
        r.address = f'{ip}:{self.rdp_port.as_int()}'
        r.username = ci.username
        r.password = ci.password
        r.domain = ci.domain
        r.redir_printers = self.allow_printers.as_bool()
        r.redir_smartcards = self.allow_smartcards.as_bool()
        r.redir_drives = self.allow_drives.value
        r.redir_serials = self.allow_serial_ports.as_bool()
        r.enable_clipboard = self.allow_clipboard.as_bool()
        r.redir_audio = self.allow_audio.as_bool()
        r.redir_webcam = self.allow_webcam.as_bool()
        r.show_wallpaper = self.wallpaper.as_bool()
        r.multimon = self.multimon.as_bool()
        r.desktop_composition = self.aero.as_bool()
        r.smooth_fonts = self.smooth.as_bool()
        r.connection_bar = self.show_connection_bar.as_bool()
        r.enable_credssp_support = self.credssp.as_bool()
        r.multimedia = self.lnx_multimedia.as_bool()
        r.alsa = self.lnx_alsa.as_bool()
        r.smartcard_params = self.lnx_smartcard_string.value
        r.printer_params = self.lnx_printer_string.value
        r.enforced_shares = self.enforce_drives.value
        r.redir_usb = self.allow_usb_redirection.value

        sp: collections.abc.MutableMapping[str, typing.Any] = {
            'password': ci.password,
            'this_server': request.build_absolute_uri('/'),
            'ip': ip,
            'port': self.rdp_port.value,  # As string, because we need to use it in the template
            'address': r.address,
        }

        if os.os == types.os.KnownOS.WINDOWS:
            r.custom_parameters = self.wnd_custom_parameters.value
            if ci.password:
                r.password = '{password}'  # nosec: password is not hardcoded
            sp.update(
                {
                    'as_file': r.as_file,
                }
            )
        elif os.os == types.os.KnownOS.LINUX:
            if self.lnx_use_rdp_file.as_bool():
                r.custom_parameters = self.wnd_custom_parameters.value
            else:
                r.custom_parameters = self.lnx_custom_parameters.value
            sp.update(
                {
                    'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                    'address': r.address,
                    'as_file': r.as_file if self.lnx_use_rdp_file.as_bool() else '',
                }
            )
        elif os.os == types.os.KnownOS.MAC_OS:
            r.custom_parameters = self.mac_custom_parameters.value
            sp.update(
                {
                    'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                    'as_rdp_url': r.as_rdp_url if self.mac_allow_msrdc.as_bool() else '',
                    'as_file': r.as_file if self.mac_allow_msrdc.as_bool() else '',
                    'address': r.address,
                }
            )
        else:
            logger.error(
                'Os not valid for RDP Transport: %s',
                request.META.get('HTTP_USER_AGENT', 'Unknown'),
            )
            return super().get_transport_script(userservice, transport, ip, os, user, password, request)

        return self.get_script(os.os.os_name(), 'direct', sp)
