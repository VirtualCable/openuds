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
import re
import logging
import typing
from uds.models.util import getSqlDatetime

from django.utils.translation import gettext_noop as _

from uds.core.ui import gui

from uds.core import transports

from uds.core.util import os_detector as OsDetector
from uds.core.managers import cryptoManager
from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module
    from uds.core.util.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class HTML5RDPTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeName = _('HTML5 RDP')
    typeType = 'HTML5RDPTransport'
    typeDescription = _('RDP protocol using HTML5 client')
    iconFile = 'html5.png'

    ownLink = True
    supportedOss = OsDetector.allOss
    protocol = transports.protocols.RDP
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

    useGlyptodonTunnel = gui.CheckBoxField(
        label=_('Use Glyptodon Enterprise tunnel'),
        order=2,
        tooltip=_(
            'If checked, UDS will use Glyptodon Enterprise Tunnel for HTML tunneling instead of UDS Tunnel'
        ),
        tab=gui.Tab.TUNNEL,
    )

    useEmptyCreds = gui.CheckBoxField(
        label=_('Empty creds'),
        order=3,
        tooltip=_('If checked, the credentials used to connect will be emtpy'),
        tab=gui.Tab.CREDENTIALS,
    )
    fixedName = gui.TextField(
        label=_('Username'),
        order=4,
        tooltip=_('If not empty, this username will be always used as credential'),
        tab=gui.Tab.CREDENTIALS,
    )
    fixedPassword = gui.PasswordField(
        label=_('Password'),
        order=5,
        tooltip=_('If not empty, this password will be always used as credential'),
        tab=gui.Tab.CREDENTIALS,
    )
    withoutDomain = gui.CheckBoxField(
        label=_('Without Domain'),
        order=6,
        tooltip=_(
            'If checked, the domain part will always be emptied (to connecto to xrdp for example is needed)'
        ),
        tab=gui.Tab.CREDENTIALS,
    )
    fixedDomain = gui.TextField(
        label=_('Domain'),
        order=7,
        tooltip=_(
            'If not empty, this domain will be always used as credential (used as DOMAIN\\user)'
        ),
        tab=gui.Tab.CREDENTIALS,
    )
    wallpaper = gui.CheckBoxField(
        label=_('Show wallpaper'),
        order=18,
        tooltip=_(
            'If checked, the wallpaper and themes will be shown on machine (better user experience, more bandwidth)'
        ),
        tab=gui.Tab.PARAMETERS,
    )
    desktopComp = gui.CheckBoxField(
        label=_('Allow Desk.Comp.'),
        order=19,
        tooltip=_('If checked, desktop composition will be allowed'),
        tab=gui.Tab.PARAMETERS,
    )
    smooth = gui.CheckBoxField(
        label=_('Font Smoothing'),
        order=20,
        tooltip=_('If checked, fonts smoothing will be allowed (windows clients only)'),
        tab=gui.Tab.PARAMETERS,
    )
    enableAudio = gui.CheckBoxField(
        label=_('Enable Audio'),
        order=21,
        tooltip=_(
            'If checked, the audio will be redirected to remote session (if client browser supports it)'
        ),
        tab=gui.Tab.PARAMETERS,
        defvalue=gui.TRUE,
    )
    enableAudioInput = gui.CheckBoxField(
        label=_('Enable Microphone'),
        order=22,
        tooltip=_(
            'If checked, the microphone will be redirected to remote session (if client browser supports it)'
        ),
        tab=gui.Tab.PARAMETERS,
    )
    enablePrinting = gui.CheckBoxField(
        label=_('Enable Printing'),
        order=23,
        tooltip=_(
            'If checked, the printing will be redirected to remote session (if client browser supports it)'
        ),
        tab=gui.Tab.PARAMETERS,
    )
    enableFileSharing = gui.ChoiceField(
        label=_('File Sharing'),
        order=24,
        tooltip=_('File upload/download redirection policy'),
        defvalue='false',
        values=[
            {'id': 'false', 'text': _('Disable file sharing')},
            {'id': 'down', 'text': _('Allow download only')},
            {'id': 'up', 'text': _('Allow upload only')},
            {'id': 'true', 'text': _('Enable file sharing')},
        ],
        tab=gui.Tab.PARAMETERS,
    )
    enableClipboard = gui.ChoiceField(
        label=_('Clipboard'),
        order=25,
        tooltip=_('Clipboard redirection policy'),
        defvalue='enabled',
        values=[
            {'id': 'disabled', 'text': _('Disable clipboard')},
            {'id': 'dis-copy', 'text': _('Disable copy from remote')},
            {'id': 'dis-paste', 'text': _('Disable paste to remote')},
            {'id': 'enabled', 'text': _('Enable clipboard')},
        ],
        tab=gui.Tab.PARAMETERS,
    )

    serverLayout = gui.ChoiceField(
        order=26,
        label=_('Layout'),
        tooltip=_('Keyboards Layout of server'),
        required=True,
        values=[
            gui.choiceItem('-', 'default'),
            gui.choiceItem('en-us-qwerty', _('English (US) keyboard')),
            gui.choiceItem('en-gb-qwerty', _('English (GB) keyboard')),
            gui.choiceItem('es-es-qwerty', _('Spanish keyboard')),
            gui.choiceItem('es-latam-qwerty', _('Latin American keyboard')),
            gui.choiceItem('da-dk-querty', _('Danish keyboard')),
            gui.choiceItem('de-de-qwertz', _('German keyboard (qwertz)')),
            gui.choiceItem('fr-fr-azerty', _('French keyboard (azerty)')),
            gui.choiceItem('fr-be-azerty', _('Belgian French keyboard (azerty)')),
            gui.choiceItem('de-ch-qwertz', _('Swiss German keyboard (qwertz)')),
            gui.choiceItem('fr-ch-qwertz', _('Swiss French keyboard (qwertz)')),
            gui.choiceItem('hu-hu-qwerty', _('Hungarian keyboard')),
            gui.choiceItem('it-it-qwerty', _('Italian keyboard')),
            gui.choiceItem('ja-jp-qwerty', _('Japanese keyboard')),
            gui.choiceItem('no-no-querty', _('Norwegian keyboard')),
            gui.choiceItem('pt-br-qwerty', _('Portuguese Brazilian keyboard')),
            gui.choiceItem('sv-se-qwerty', _('Swedish keyboard')),
            gui.choiceItem('tr-tr-qwerty', _('Turkish keyboard')),
            gui.choiceItem('failsafe', _('Failsafe')),
        ],
        defvalue='-',
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
    security = gui.ChoiceField(
        order=92,
        label=_('Security'),
        tooltip=_('Connection security mode for Guacamole RDP connection'),
        required=True,
        values=[
            gui.choiceItem(
                'any', _('Any (Allow the server to choose the type of auth)')
            ),
            gui.choiceItem(
                'rdp',
                _('RDP (Standard RDP encryption. Should be supported by all servers)'),
            ),
            gui.choiceItem(
                'nla',
                _(
                    'NLA (Network Layer authentication. Requires VALID username&password, or connection will fail)'
                ),
            ),
            gui.choiceItem(
                'nla-ext',
                _(
                    'NLA extended (Network Layer authentication. Requires VALID username&password, or connection will fail)'
                ),
            ),
            gui.choiceItem('tls', _('TLS (Transport Security Layer encryption)')),
        ],
        defvalue='any',
        tab=gui.Tab.ADVANCED,
    )

    rdpPort = gui.NumericField(
        order=93,
        length=5,  # That is, max allowed value is 65535
        label=_('RDP Port'),
        tooltip=_('Use this port as RDP port. Defaults to 3389.'),
        required=True,  #: Numeric fields have always a value, so this not really needed
        defvalue='3389',
        tab=gui.Tab.ADVANCED,
    )

    customGEPath = gui.TextField(
        label=_('Glyptodon Enterprise context path'),
        order=94,
        tooltip=_(
            'Customized path for Glyptodon Enterprise tunnel. (Only valid for Glyptodon Enterprise Tunnel)'
        ),
        defvalue='/',
        length=128,
        required=False,
        tab=gui.Tab.ADVANCED,
    )

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return
        # Strip spaces and all trailing '/'
        self.guacamoleServer.value = self.guacamoleServer.value.strip().rstrip('/')
        if self.guacamoleServer.value[0:4] != 'http':
            raise transports.Transport.ValidationException(
                _('The server must be http or https')
            )
        if self.useEmptyCreds.isTrue() and self.security.value != 'rdp':
            raise transports.Transport.ValidationException(
                _(
                    'Empty credentials (on Credentials tab) is only allowed with Security level (on Parameters tab) set to "RDP"'
                )
            )

    # Same check as normal RDP transport
    def isAvailableFor(self, userService: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for %s', ip)
        ready = self.cache.get(ip)
        if not ready:
            # Check again for readyness
            if self.testServer(userService, ip, self.rdpPort.num()) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processedUser(
        self, userService: 'models.UserService', user: 'models.User'
    ) -> str:
        v = self.getConnectionInfo(userService, user, '')
        return v['username']

    def getConnectionInfo(
        self,
        userService: typing.Union['models.UserService', 'models.ServicePool'],
        user: 'models.User',
        password: str,
    ) -> typing.Mapping[str, str]:
        username = user.getUsernameForAuth()

        # Maybe this is called from another provider, as for example WYSE, that need all connections BEFORE
        if isinstance(userService, models.UserService):
            cdata = userService.getInstance().getConnectionData()
            if cdata:
                username = cdata[1] or username
                password = cdata[2] or password

        if self.fixedPassword.value:
            password = self.fixedPassword.value

        if self.fixedName.value:
            username = self.fixedName.value

        proc = username.split('@')
        if len(proc) > 1:
            domain = proc[1]
        else:
            domain = ''
        username = proc[0]

        azureAd = False

        if self.fixedDomain.value != '':
            domain = self.fixedDomain.value

        if self.useEmptyCreds.isTrue():
            username, passwd, domain = '', '', ''

        if self.withoutDomain.isTrue():
            domain = ''

        if '.' in domain:  # FQDN domain form
            username = username + '@' + domain
            domain = ''

        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)

        return {
            'protocol': self.protocol,
            'username': username,
            'password': password,
            'domain': domain,
        }

    def getLink(
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: typing.Dict[str, str],
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> str:
        credsInfo = self.getConnectionInfo(userService, user, password)
        username, password, domain = (
            credsInfo['username'],
            credsInfo['password'],
            credsInfo['domain'],
        )

        scrambler = cryptoManager().randomString(32)
        passwordCrypted = cryptoManager().symCrypt(password, scrambler)

        as_txt = lambda x: 'true' if x else 'false'

        # Build params dict
        params = {
            'protocol': 'rdp',
            'hostname': ip,
            'port': self.rdpPort.num(),
            'username': username,
            'password': passwordCrypted,
            'resize-method': 'display-update',
            'ignore-cert': 'true',
            'security': self.security.value,
            'enable-drive': as_txt(
                self.enableFileSharing.value in ('true', 'down', 'up')
            ),
            'disable-upload': as_txt(
                self.enableFileSharing.value not in ('true', 'up')
            ),
            'drive-path': '/share/{}'.format(user.uuid),
            'drive-name': 'UDSfs',
            'disable-copy': as_txt(
                self.enableClipboard.value in ('dis-copy', 'disabled')
            ),
            'disable-paste': as_txt(
                self.enableClipboard.value in ('dis-paste', 'disabled')
            ),
            'create-drive-path': 'true',
            'ticket-info': {
                'userService': userService.uuid,
                'user': userService.user.uuid if userService.user else '',
            },
        }

        if False:  # Future imp
            sanitize = lambda x: re.sub("[^a-zA-Z0-9_-]", "_", x)
            params['recording-path'] = (
                '/share/recording/'
                + sanitize(user.manager.name)
                + '_'
                + sanitize(user.name)
                + '/'
                + getSqlDatetime().strftime('%Y%m%d-%H%M')
            )
            params['create-recording-path'] = 'true'

        if domain:
            params['domain'] = domain

        if self.serverLayout.value != '-':
            params['server-layout'] = self.serverLayout.value

        if not self.enableAudio.isTrue():
            params['disable-audio'] = 'true'
        elif self.enableAudioInput.isTrue():
            params['enable-audio-input'] = 'true'

        if self.enablePrinting.isTrue():
            params['enable-printing'] = 'true'
            params['printer-name'] = 'UDS-Printer'

        if self.wallpaper.isTrue():
            params['enable-wallpaper'] = 'true'

        if self.desktopComp.isTrue():
            params['enable-desktop-composition'] = 'true'

        if self.smooth.isTrue():
            params['enable-font-smoothing'] = 'true'

        logger.debug('RDP Params: %s', params)

        ticket = models.TicketStore.create(params, validity=self.ticketValidity.num())

        onw = '&o_n_w={}'.format(transport.uuid)
        if self.forceNewWindow.value == gui.TRUE:
            onw = '&o_n_w={}'.format(userService.deployed_service.uuid)
        elif self.forceNewWindow.value == 'overwrite':
            onw = '&o_s_w=yes'
        path = (
            self.customGEPath.value
            if self.useGlyptodonTunnel.isTrue()
            else '/guacamole'
        )
        # Remove trailing /
        if path[-1] == '/':
            path = path[:-1]

        return str(
            "{server}{path}/#/?data={ticket}.{scrambler}{onw}".format(
                server=self.guacamoleServer.value,
                path=path,
                ticket=ticket,
                scrambler=scrambler,
                onw=onw,
            )
        )
