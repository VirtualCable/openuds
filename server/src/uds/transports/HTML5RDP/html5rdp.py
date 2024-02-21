# pylint: disable=no-member  # For some reason, pylint does not detect the Tab member of gui

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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import re
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds import models
from uds.core import transports, types, ui, consts
from uds.core.managers.crypto import CryptoManager
from uds.core.util import fields
from uds.core.util.model import sql_datetime

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class HTML5RDPTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    type_name = _('HTML5 RDP')
    type_type = 'HTML5RDPTransport'
    type_description = _('RDP protocol using HTML5 client')
    icon_file = 'html5.png'

    own_link = True
    supported_oss = consts.os.ALL_OS_LIST
    protocol = types.transports.Protocol.RDP
    group = types.transports.Grouping.TUNNELED

    tunnel = fields.tunnel_field()

    use_glyptodon = ui.gui.CheckBoxField(
        label=_('Use Glyptodon Enterprise tunnel'),
        order=2,
        tooltip=_(
            'If checked, UDS will use Glyptodon Enterprise Tunnel for HTML tunneling instead of UDS Tunnel'
        ),
        tab=types.ui.Tab.TUNNEL,
        old_field_name='useGlyptodonTunnel',
    )

    force_empty_creds = ui.gui.CheckBoxField(
        label=_('Empty creds'),
        order=3,
        tooltip=_('If checked, the credentials used to connect will be emtpy'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='useEmptyCreds',
    )
    forced_username = ui.gui.TextField(
        label=_('Username'),
        order=4,
        tooltip=_('If not empty, this username will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedName',
    )
    forced_password = ui.gui.PasswordField(
        label=_('Password'),
        order=5,
        tooltip=_('If not empty, this password will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedPassword',
    )
    force_no_domain = ui.gui.CheckBoxField(
        label=_('Without Domain'),
        order=6,
        tooltip=_(
            'If checked, the domain part will always be emptied (to connecto to xrdp for example is needed)'
        ),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='withoutDomain',
    )
    forced_domain = ui.gui.TextField(
        label=_('Domain'),
        order=7,
        tooltip=_('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedDomain',
    )
    wallpaper = ui.gui.CheckBoxField(
        label=_('Show wallpaper'),
        order=18,
        tooltip=_(
            'If checked, the wallpaper and themes will be shown on machine (better user experience, more bandwidth)'
        ),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='wallpaper',
    )
    allow_destop_composition = ui.gui.CheckBoxField(
        label=_('Allow Desk.Comp.'),
        order=19,
        tooltip=_('If checked, desktop composition will be allowed'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='desktopComp',
    )
    smooth = ui.gui.CheckBoxField(
        label=_('Font Smoothing'),
        order=20,
        tooltip=_('If checked, fonts smoothing will be allowed (windows clients only)'),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='smooth',
    )
    enable_audio = ui.gui.CheckBoxField(
        label=_('Enable Audio'),
        order=21,
        tooltip=_('If checked, the audio will be redirected to remote session (if client browser supports it)'),
        tab=types.ui.Tab.PARAMETERS,
        default=True,
        old_field_name='enableAudio',
    )
    enable_microphone = ui.gui.CheckBoxField(
        label=_('Enable Microphone'),
        order=22,
        tooltip=_(
            'If checked, the microphone will be redirected to remote session (if client browser supports it)'
        ),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enableAudioInput',
    )
    enable_printing = ui.gui.CheckBoxField(
        label=_('Enable Printing'),
        order=23,
        tooltip=_(
            'If checked, the printing will be redirected to remote session (if client browser supports it)'
        ),
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enablePrinting',
    )
    enable_file_sharing = ui.gui.ChoiceField(
        label=_('File Sharing'),
        order=24,
        tooltip=_('File upload/download redirection policy'),
        default='false',
        choices=[
            {'id': 'false', 'text': _('Disable file sharing')},
            {'id': 'down', 'text': _('Allow download only')},
            {'id': 'up', 'text': _('Allow upload only')},
            {'id': 'true', 'text': _('Enable file sharing')},
        ],
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enableFileSharing',
    )
    enable_clipboard = ui.gui.ChoiceField(
        label=_('Clipboard'),
        order=25,
        tooltip=_('Clipboard redirection policy'),
        default='enabled',
        choices=[
            {'id': 'disabled', 'text': _('Disable clipboard')},
            {'id': 'dis-copy', 'text': _('Disable copy from remote')},
            {'id': 'dis-paste', 'text': _('Disable paste to remote')},
            {'id': 'enabled', 'text': _('Enable clipboard')},
        ],
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='enableClipboard',
    )

    server_layout = ui.gui.ChoiceField(
        order=26,
        label=_('Layout'),
        tooltip=_('Keyboard Layout of server'),
        required=True,
        choices=[
            ui.gui.choice_item('-', 'default'),
            ui.gui.choice_item('en-us-qwerty', _('English (US) keyboard')),
            ui.gui.choice_item('en-gb-qwerty', _('English (GB) keyboard')),
            ui.gui.choice_item('es-es-qwerty', _('Spanish keyboard')),
            ui.gui.choice_item('es-latam-qwerty', _('Latin American keyboard')),
            ui.gui.choice_item('da-dk-querty', _('Danish keyboard')),
            ui.gui.choice_item('de-de-qwertz', _('German keyboard (qwertz)')),
            ui.gui.choice_item('fr-fr-azerty', _('French keyboard (azerty)')),
            ui.gui.choice_item('fr-be-azerty', _('Belgian French keyboard (azerty)')),
            ui.gui.choice_item('de-ch-qwertz', _('Swiss German keyboard (qwertz)')),
            ui.gui.choice_item('fr-ch-qwertz', _('Swiss French keyboard (qwertz)')),
            ui.gui.choice_item('hu-hu-qwerty', _('Hungarian keyboard')),
            ui.gui.choice_item('it-it-qwerty', _('Italian keyboard')),
            ui.gui.choice_item('ja-jp-qwerty', _('Japanese keyboard')),
            ui.gui.choice_item('no-no-querty', _('Norwegian keyboard')),
            ui.gui.choice_item('pt-br-qwerty', _('Portuguese Brazilian keyboard')),
            ui.gui.choice_item('sv-se-qwerty', _('Swedish keyboard')),
            ui.gui.choice_item('tr-tr-qwerty', _('Turkish keyboard')),
            ui.gui.choice_item('failsafe', _('Failsafe')),
        ],
        default='-',
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='serverLayout',
    )

    ticket_validity = fields.tunnel_ticket_validity_field()

    force_new_window = ui.gui.ChoiceField(
        order=91,
        label=_('Force new HTML Window'),
        tooltip=_('Select windows behavior for new connections on HTML5'),
        required=True,
        choices=[
            ui.gui.choice_item(
                'false',
                _('Open every connection on the same window, but keeps UDS window.'),
            ),
            ui.gui.choice_item('true', _('Force every connection to be opened on a new window.')),
            ui.gui.choice_item(
                'overwrite',
                _('Override UDS window and replace it with the connection.'),
            ),
        ],
        default='true',
        tab=types.ui.Tab.ADVANCED,
        old_field_name='forceNewWindow',
    )
    
    security = ui.gui.ChoiceField(
        order=92,
        label=_('Security'),
        tooltip=_('Connection security mode for Guacamole RDP connection'),
        required=True,
        choices=[
            ui.gui.choice_item('any', _('Any (Allow the server to choose the type of auth)')),
            ui.gui.choice_item(
                'rdp',
                _('RDP (Standard RDP encryption. Should be supported by all servers)'),
            ),
            ui.gui.choice_item(
                'nla',
                _(
                    'NLA (Network Layer authentication. Requires VALID username&password, or connection will fail)'
                ),
            ),
            ui.gui.choice_item(
                'nla-ext',
                _(
                    'NLA extended (Network Layer authentication. Requires VALID username&password, or connection will fail)'
                ),
            ),
            ui.gui.choice_item('tls', _('TLS (Transport Security Layer encryption)')),
        ],
        default='any',
        tab=types.ui.Tab.ADVANCED,
        old_field_name='security',
    )

    rdp_port = ui.gui.NumericField(
        order=93,
        length=5,  # That is, max allowed value is 65535
        label=_('RDP Port'),
        tooltip=_('Use this port as RDP port. Defaults to 3389.'),
        required=True,  #: Numeric fields have always a value, so this not really needed
        default=3389,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='rdpPort',
    )

    custom_glyptodon_path = ui.gui.TextField(
        label=_('Glyptodon Enterprise context path'),
        order=94,
        tooltip=_(
            'Customized path for Glyptodon Enterprise tunnel. (Only valid for Glyptodon Enterprise Tunnel)'
        ),
        default='/',
        length=128,
        required=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='customGEPath',
    )

    def initialize(self, values: 'types.core.ValuesType'):
        if not values:
            return
        # if self.useEmptyCreds.as_bool() and self.security.value != 'rdp':
        #    raise exceptions.ValidationException(
        #        _(
        #            'Empty credentials (on Credentials tab) is only allowed with Security level (on Parameters tab) set to "RDP"'
        #        )
        #    )

    # Same check as normal RDP transport
    def is_ip_allowed(self, userService: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            # Check again for readyness
            if self.test_connectivity(userService, ip, self.rdp_port.as_int()) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processed_username(self, userService: 'models.UserService', user: 'models.User') -> str:
        v = self.get_connection_info(userService, user, '')
        return v.username

    def get_connection_info(
        self,
        userService: typing.Union['models.UserService', 'models.ServicePool'],
        user: 'models.User',
        password: str,
    ) -> types.connections.ConnectionData:
        username = user.get_username_for_auth()

        # Maybe this is called from another provider, as for example WYSE, that need all connections BEFORE
        if isinstance(userService, models.UserService):
            cdata = userService.get_instance().get_connection_data()
            if cdata:
                username = cdata[1] or username
                password = cdata[2] or password

        if self.forced_password.value:
            password = self.forced_password.value

        if self.forced_username.value:
            username = self.forced_username.value

        proc = username.split('@')
        if len(proc) > 1:
            domain = proc[1]
        else:
            domain = ''
        username = proc[0]

        azureAd = False
        if self.forced_domain.value != '':
            if self.forced_domain.value.lower() == 'azuread':
                azureAd = True
            else:
                domain = self.forced_domain.value

        if self.force_empty_creds.as_bool():
            username, password, domain = '', '', ''

        if self.force_no_domain.as_bool():
            domain = ''

        if '.' in domain:  # FQDN domain form
            username = username + '@' + domain
            domain = ''

        # If AzureAD, include it on username
        if azureAd:
            username = 'AzureAD\\' + username

        # Fix username/password acording to os manager
        username, password = userService.process_user_password(username, password)

        return types.connections.ConnectionData(
            protocol=self.protocol,
            username=username,
            service_type=types.services.ServiceType.VDI,
            password=password,
            domain=domain,
        )

    def get_link(
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',  # pylint: disable=unused-argument
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',  # pylint: disable=unused-argument
    ) -> str:
        credsInfo = self.get_connection_info(userService, user, password)
        username, password, domain = (
            credsInfo.username,
            credsInfo.password,
            credsInfo.domain,
        )

        scrambler = CryptoManager().random_string(32)
        passwordCrypted = CryptoManager().symmetric_encrypt(password, scrambler)

        def as_txt(txt: typing.Any) -> str:
            return 'true' if txt else 'false'

        # Build params dict
        params = {
            'protocol': 'rdp',
            'hostname': ip,
            'port': self.rdp_port.as_int(),
            'username': username,
            'password': passwordCrypted,
            'resize-method': 'display-update',
            'ignore-cert': 'true',
            'security': self.security.value,
            'enable-drive': as_txt(self.enable_file_sharing.value in ('true', 'down', 'up')),
            'disable-upload': as_txt(self.enable_file_sharing.value not in ('true', 'up')),
            'drive-path': f'/share/{user.uuid}',
            'drive-name': 'UDSfs',
            'disable-copy': as_txt(self.enable_clipboard.value in ('dis-copy', 'disabled')),
            'disable-paste': as_txt(self.enable_clipboard.value in ('dis-paste', 'disabled')),
            'create-drive-path': 'true',
            'ticket-info': {
                'userService': userService.uuid,
                'user': user.uuid,
                'service_type': types.services.ServiceType.VDI,
            },
        }

        if (
            not password and self.security.value != 'rdp'
        ):  # No password, but not rdp, so we need to use creds popup
            extra_params = f'&creds={username}@{domain}'
        else:
            extra_params = ''

        # pylint: disable=using-constant-test
        if False:  # Future imp
            # sanitize = lambda x: re.sub("[^a-zA-Z0-9_-]", "_", x)
            def sanitize(text: str) -> str:
                return re.sub("[^a-zA-Z0-9_-]", "_", text)

            params['recording-path'] = (
                '/share/recording/'
                + sanitize(user.manager.name)
                + '_'
                + sanitize(user.name)
                + '/'
                + sql_datetime().strftime('%Y%m%d-%H%M')
            )
            params['create-recording-path'] = 'true'

        if domain:
            params['domain'] = domain

        if self.server_layout.value != '-':
            params['server-layout'] = self.server_layout.value

        if not self.enable_audio.as_bool():
            params['disable-audio'] = 'true'
        elif self.enable_microphone.as_bool():
            params['enable-audio-input'] = 'true'

        if self.enable_printing.as_bool():
            params['enable-printing'] = 'true'
            params['printer-name'] = 'UDS-Printer'

        if self.wallpaper.as_bool():
            params['enable-wallpaper'] = 'true'

        if self.allow_destop_composition.as_bool():
            params['enable-desktop-composition'] = 'true'

        if self.smooth.as_bool():
            params['enable-font-smoothing'] = 'true'

        logger.debug('RDP Params: %s', params)

        ticket = models.TicketStore.create(params, validity=self.ticket_validity.as_int())

        onw = f'&o_n_w={transport.uuid}'
        if self.force_new_window.value == consts.TRUE_STR:
            onw = f'&o_n_w={userService.deployed_service.uuid}'
        elif self.force_new_window.value == 'overwrite':
            onw = '&o_s_w=yes'
        path = self.custom_glyptodon_path.value if self.use_glyptodon.as_bool() else '/guacamole'
        # Remove trailing /
        path = path.rstrip('/')

        tunnelServer = fields.get_tunnel_from_field(self.tunnel)
        return str(
            f'https://{tunnelServer.host}:{tunnelServer.port}{path}/#/?data={ticket}.{scrambler}{onw}{extra_params}'
        )
