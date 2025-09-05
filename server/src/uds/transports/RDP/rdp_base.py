# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

from uds.core.ui import gui
from uds.core import transports, types
from uds.core.util.security import convert_to_credential_token
from uds.models import UserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class BaseRDPTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    is_base = True

    icon_file = 'rdp.png'
    PROTOCOL = types.transports.Protocol.RDP

    force_empty_creds = gui.CheckBoxField(
        label=_('Empty creds'),
        order=11,
        tooltip=_('If checked, the credentials used to connect will be emtpy'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='useEmptyCreds',
    )
    forced_username = gui.TextField(
        label=_('Username'),
        order=12,
        tooltip=_('If not empty, this username will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedName',
    )
    forced_password = gui.PasswordField(
        label=_('Password'),
        order=13,
        tooltip=_('If not empty, this password will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedPassword',
    )
    force_no_domain = gui.CheckBoxField(
        label=_('Without Domain'),
        order=14,
        tooltip=_(
            'If checked, the domain part will always be emptied (to connect to xrdp for example is needed)'
        ),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='withoutDomain',
    )
    forced_domain = gui.TextField(
        label=_('Domain'),
        order=15,
        tooltip=_('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedDomain',
    )
    use_sso = gui.CheckBoxField(
        label=_('Use SSO'),
        order=16,
        tooltip=_(
            'If checked, and user service supports it, will use UDS SSO mechanism. (Ensure you have enabled UDS SSO)'
        ),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='useSSO',
    )

    allow_smartcards = gui.CheckBoxField(
        label=_('Allow Smartcards'),
        order=20,
        tooltip=_('If checked, this transport will allow the use of smartcards'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='allowSmartcards',
    )
    allow_printers = gui.CheckBoxField(
        label=_('Allow Printers'),
        order=21,
        tooltip=_('If checked, this transport will allow the use of user printers'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='allowPrinters',
    )
    allow_drives = gui.ChoiceField(
        label=_('Local drives policy'),
        order=22,
        tooltip=_('Local drives redirection policy'),
        default='false',
        choices=[
            gui.choice_item('false', 'Allow none'),
            gui.choice_item('dynamic', 'Allow PnP drives'),
            gui.choice_item('true', 'Allow any drive'),
        ],
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='allowDrives',
    )
    enforce_drives = gui.TextField(
        label=_('Force drives'),
        order=23,
        tooltip=_(
            'Use comma separated values, for example "C:,D:". If drives policy is disallowed, this will be ignored'
        ),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enforceDrives',
    )

    allow_serial_ports = gui.CheckBoxField(
        label=_('Allow Serials'),
        order=24,
        tooltip=_('If checked, this transport will allow the use of user serial ports'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='allowSerials',
    )
    allow_clipboard = gui.CheckBoxField(
        label=_('Enable clipboard'),
        order=25,
        tooltip=_('If checked, copy-paste functions will be allowed'),
        tab=types.ui.Tab.PARAMETERS,
        default=True,
        old_field_name='allowClipboard',
    )
    allow_audio = gui.CheckBoxField(
        label=_('Enable sound'),
        order=26,
        tooltip=_('If checked, sound will be redirected.'),
        tab=types.ui.Tab.PARAMETERS,
        default=True,
        old_field_name='allowAudio',
    )
    allow_webcam = gui.CheckBoxField(
        label=_('Enable webcam'),
        order=27,
        tooltip=_('If checked, webcam will be redirected (ONLY Windows).'),
        tab=types.ui.Tab.PARAMETERS,
        default=False,
        old_field_name='allowWebcam',
    )
    allow_usb_redirection = gui.ChoiceField(
        label=_('USB redirection'),
        order=28,
        tooltip=_('USB redirection policy'),
        default='false',
        choices=[
            gui.choice_item('false', 'Allow none'),
            gui.choice_item('true', 'Allow all'),
            gui.choice_item('{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}', 'Cameras'),
            gui.choice_item('{4d36e967-e325-11ce-bfc1-08002be10318}', 'Disk Drives'),
            gui.choice_item('{4d36e979-e325-11ce-bfc1-08002be10318}', 'Printers'),
            gui.choice_item('{50dd5230-ba8a-11d1-bf5d-0000f805f530}', 'Smartcards'),
            gui.choice_item('{745a17a0-74d3-11d0-b6fe-00a0c90f57da}', 'HIDs'),
        ],
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='usbRedirection',
    )

    credssp = gui.CheckBoxField(
        label=_('Credssp Support'),
        order=29,
        tooltip=_('If checked, will enable Credentials Provider Support)'),
        tab=types.ui.Tab.PARAMETERS,
        default=True,
        old_field_name='credssp',
    )
    rdp_port = gui.NumericField(
        order=30,
        length=5,  # That is, max allowed value is 65535
        label=_('RDP Port'),
        tooltip=_('Use this port as RDP port. Defaults to 3389.'),
        tab=types.ui.Tab.PARAMETERS,
        required=True,  #: Numeric fields have always a value, so this not really needed
        default=3389,
        old_field_name='rdpPort',
    )

    screen_size = gui.ChoiceField(
        label=_('Screen Size'),
        order=31,
        tooltip=_('Screen size for this transport'),
        default='-1x-1',
        choices=[
            gui.choice_item('640x480', '640x480'),
            gui.choice_item('800x600', '800x600'),
            gui.choice_item('1024x768', '1024x768'),
            gui.choice_item('1366x768', '1366x768'),
            gui.choice_item('1920x1080', '1920x1080'),
            gui.choice_item('2304x1440', '2304x1440'),
            gui.choice_item('2560x1440', '2560x1440'),
            gui.choice_item('2560x1600', '2560x1600'),
            gui.choice_item('2880x1800', '2880x1800'),
            gui.choice_item('3072x1920', '3072x1920'),
            gui.choice_item('3840x2160', '3840x2160'),
            gui.choice_item('4096x2304', '4096x2304'),
            gui.choice_item('5120x2880', '5120x2880'),
            gui.choice_item('-1x-1', 'Full screen'),
        ],
        tab=types.ui.Tab.DISPLAY,
        old_field_name='screenSize',
    )

    color_depth = gui.ChoiceField(
        label=_('Color depth'),
        order=32,
        tooltip=_('Color depth for this connection'),
        default='24',
        choices=[
            gui.choice_item('8', '8'),
            gui.choice_item('16', '16'),
            gui.choice_item('24', '24'),
            gui.choice_item('32', '32'),
        ],
        tab=types.ui.Tab.DISPLAY,
        old_field_name='colorDepth',
    )

    wallpaper = gui.CheckBoxField(
        label=_('Wallpaper/theme'),
        order=33,
        tooltip=_(
            'If checked, the wallpaper and themes will be shown on machine (better user experience, more bandwidth)'
        ),
        tab=types.ui.Tab.DISPLAY,
        old_field_name='wallpaper',
    )
    multimon = gui.CheckBoxField(
        label=_('Multiple monitors'),
        order=34,
        tooltip=_(
            'If checked, all client monitors will be used for displaying (only works on windows clients)'
        ),
        tab=types.ui.Tab.DISPLAY,
        old_field_name='multimon',
    )
    aero = gui.CheckBoxField(
        label=_('Allow Desk.Comp.'),
        order=35,
        tooltip=_('If checked, desktop composition will be allowed'),
        tab=types.ui.Tab.DISPLAY,
        old_field_name='aero',
    )
    smooth = gui.CheckBoxField(
        label=_('Font Smoothing'),
        default=True,
        order=36,
        tooltip=_('If checked, fonts smoothing will be allowed'),
        tab=types.ui.Tab.DISPLAY,
        old_field_name='smooth',
    )
    show_connection_bar = gui.CheckBoxField(
        label=_('Connection Bar'),
        order=37,
        tooltip=_('If checked, connection bar will be shown (only on Windows clients)'),
        tab=types.ui.Tab.DISPLAY,
        default=True,
        old_field_name='showConnectionBar',
    )

    lnx_multimedia = gui.CheckBoxField(
        label=_('Multimedia sync'),
        order=40,
        tooltip=_('If checked. Linux client will use multimedia parameter for xfreerdp'),
        tab='Linux Client',
        old_field_name='multimedia',
    )
    lnx_alsa = gui.CheckBoxField(
        label=_('Use Alsa'),
        order=41,
        tooltip=_('If checked, Linux client will try to use ALSA, otherwise Pulse will be used'),
        tab='Linux Client',
        old_field_name='alsa',
    )
    lnx_printer_string = gui.TextField(
        label=_('Printer string'),
        order=43,
        tooltip=_('If printer is checked, the printer string used with xfreerdp client'),
        tab='Linux Client',
        length=256,
        old_field_name='printerString',
    )
    lnx_smartcard_string = gui.TextField(
        label=_('Smartcard string'),
        order=44,
        tooltip=_('If smartcard is checked, the smartcard string used with xfreerdp client'),
        tab='Linux Client',
        length=256,
        old_field_name='smartcardString',
    )
    lnx_custom_parameters = gui.TextField(
        label=_('Custom parameters'),
        order=45,
        tooltip=_(
            'If not empty, extra parameter to include for Linux Client (for example /usb:id,dev:054c:0268, or aything compatible with your xfreerdp client)'
        ),
        tab='Linux Client',
        length=256,
        old_field_name='customParameters',
    )

    mac_allow_msrdc = gui.CheckBoxField(
        label=_('Allow Microsoft Rdp Client'),
        order=50,
        tooltip=_('If checked, allows use of Microsoft Remote Desktop Client. PASSWORD WILL BE PROMPTED!'),
        tab='Mac OS X',
        default=False,
        old_field_name='allowMacMSRDC',
    )

    mac_custom_parameters = gui.TextField(
        label=_('Custom parameters'),
        order=51,
        tooltip=_(
            'If not empty, extra parameter to include for Mac OS X Freerdp Client (for example /usb:id,dev:054c:0268, or aything compatible with your xfreerdp client)'
        ),
        tab='Mac OS X',
        length=256,
        old_field_name='customParametersMAC',
    )

    wnd_custom_parameters = gui.TextField(
        label=_('Custom parameters'),
        order=45,
        tooltip=_('If not empty, extra parameters to include for Windows Client'),
        length=4096,
        lines=10,
        tab='Windows Client',
        old_field_name='customParametersWindows',
    )
    
    def initialize(self, values: types.core.ValuesType) -> None:
        if not values:
            return
        
        if self.use_sso.value:
            self.credssp.value = False   # Credssp and SSO are mutually exclusive, use_sso has preference
        

    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if ready is None:
            # Check again for ready
            if self.test_connectivity(userservice, ip, self.rdp_port.as_int()) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processed_username(self, userservice: 'models.UserService', user: 'models.User') -> str:
        v = self.process_user_password(userservice, user, '', alt_username=None)
        return v.username

    def process_user_password(
        self,
        userservice: 'models.UserService',
        user: 'models.User',
        password: str,
        *,
        alt_username: typing.Optional[str],
    ) -> types.connections.ConnectionData:
        username: str = alt_username or user.get_username_for_auth()

        if self.forced_username.value:
            username = self.forced_username.value

        proc = username.split('@', 1)
        if len(proc) > 1:
            domain = proc[1]
        else:
            domain = ''  # Default domain is empty
        username = proc[0]

        if self.forced_password.value:
            password = self.forced_password.value

        for_azure = False
        forced_domain = self.forced_domain.value.strip().lower()
        if forced_domain:  # If has forced domain
            if forced_domain == 'azuread':
                for_azure = True
            else:
                domain = forced_domain

        if self.force_empty_creds.as_bool():
            username, password, domain = '', '', ''

        if self.force_no_domain.as_bool():
            domain = ''

        if '.' in domain:  # Dotter domain form
            username = username + '@' + domain
            domain = ''

        if for_azure:
            username = 'AzureAD\\' + username  # AzureAD domain form

        # Fix username/password acording to os manager
        username, password = userservice.process_user_password(username, password)

        return types.connections.ConnectionData(
            protocol=self.PROTOCOL,
            username=username,
            service_type=types.services.ServiceType.VDI,
            password=password,
            domain=domain,
        )

    def get_connection_info(
        self,
        userservice: typing.Union['models.UserService', 'models.ServicePool'],
        user: 'models.User',
        password: str,
        *,
        for_notify: bool = False,
    ) -> types.connections.ConnectionData:
        username = None
        if isinstance(userservice, UserService):
            cdata = userservice.get_instance().get_connection_data()
            if cdata:
                username = cdata.username or username
                password = cdata.password or password

        cdata = self.process_user_password(
            typing.cast('models.UserService', userservice),
            user,
            password,
            alt_username=username,
        )

        if self.use_sso.as_bool() and isinstance(userservice, UserService):
            cdata = convert_to_credential_token(userservice, cdata)

        return cdata
