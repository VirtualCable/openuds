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

    guacamoleServer = gui.TextField(label=_('Tunnel Server'), order=1, tooltip=_('Host of the tunnel server (use http/https & port if needed) as accesible from users'), defvalue='https://', length=64, required=True, tab=gui.TUNNEL_TAB)
    useEmptyCreds = gui.CheckBoxField(label=_('Empty creds'), order=2, tooltip=_('If checked, the credentials used to connect will be emtpy'), tab=gui.CREDENTIALS_TAB)
    fixedName = gui.TextField(label=_('Username'), order=3, tooltip=_('If not empty, this username will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    fixedPassword = gui.PasswordField(label=_('Password'), order=4, tooltip=_('If not empty, this password will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    withoutDomain = gui.CheckBoxField(label=_('Without Domain'), order=5, tooltip=_('If checked, the domain part will always be emptied (to connecto to xrdp for example is needed)'), tab=gui.CREDENTIALS_TAB)
    fixedDomain = gui.TextField(label=_('Domain'), order=6, tooltip=_('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'), tab=gui.CREDENTIALS_TAB)
    wallpaper = gui.CheckBoxField(label=_('Show wallpaper'), order=20, tooltip=_('If checked, the wallpaper and themes will be shown on machine (better user experience, more bandwidth)'), tab=gui.PARAMETERS_TAB)
    desktopComp = gui.CheckBoxField(label=_('Allow Desk.Comp.'), order=22, tooltip=_('If checked, desktop composition will be allowed'), tab=gui.PARAMETERS_TAB)
    smooth = gui.CheckBoxField(label=_('Font Smoothing'), order=23, tooltip=_('If checked, fonts smoothing will be allowed (windows clients only)'), tab=gui.PARAMETERS_TAB)
    enableAudio = gui.CheckBoxField(label=_('Enable Audio'), order=24, tooltip=_('If checked, the audio will be redirected to client (if client browser supports it)'), tab=gui.PARAMETERS_TAB)
    enablePrinting = gui.CheckBoxField(label=_('Enable Printing'), order=25, tooltip=_('If checked, the printing will be redirected to client (if client browser supports it)'), tab=gui.PARAMETERS_TAB)
    enableFileSharing = gui.CheckBoxField(label=_('Enable File Sharing'), order=8, tooltip=_('If checked, the user will be able to upload/download files (if client browser supports it)'), tab=gui.PARAMETERS_TAB)
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
            gui.choiceItem('de-de-qwertz', _('German keyboard (qwertz)')),
            gui.choiceItem('fr-fr-azerty', _('French keyboard (azerty)')),
            gui.choiceItem('fr-ch-qwertz', _('Swiss French keyboard (qwertz)')),
            gui.choiceItem('de-ch-qwertz', _('Swiss German keyboard (qwertz)')),
            gui.choiceItem('it-it-qwerty', _('Italian keyboard')),
            gui.choiceItem('sv-se-qwerty', _('Swedish keyboard')),
            gui.choiceItem('ja-jp-qwerty', _('Japanese keyboard')),
            gui.choiceItem('pt-br-qwerty', _('Brazilian keyboard')),
            gui.choiceItem('failsafe', _('Failsafe')),
        ],
        defvalue='-',
        tab=gui.PARAMETERS_TAB
    )
    security = gui.ChoiceField(
        order=27,
        label=_('Security'),
        tooltip=_('Connection security mode for Guacamole RDP connection'),
        required=True,
        values=[
            gui.choiceItem('any', _('Any (Allow the server to choose the type of auth)')),
            gui.choiceItem('rdp', _('RDP (Standard RDP encryption. Should be supported by all servers)')),
            gui.choiceItem('nla', _('NLA (Network Layer authentication. Requires VALID username&password, or connection will fail)')),
            gui.choiceItem('tls', _('TLS (Transport Security Layer encryption)')),
        ],
        defvalue='rdp',
        tab=gui.PARAMETERS_TAB
    )

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

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return
        # Strip spaces
        self.guacamoleServer.value = self.guacamoleServer.value.strip()
        if self.guacamoleServer.value[0:4] != 'http':
            raise transports.Transport.ValidationException(_('The server must be http or https'))
        if self.useEmptyCreds.isTrue() and self.security.value != 'rdp':
            raise transports.Transport.ValidationException(_('Empty credentials (on Credentials tab) is only allowed with Security level (on Parameters tab) set to "RDP"'))

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
            if self.testServer(userService, ip, '3389') is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processedUser(self, userService: 'models.UserService', user: 'models.User') -> str:
        v = self.processUserAndPassword(userService, user, '')
        return v['username']

    def processUserAndPassword(self, userService: 'models.UserService', user: 'models.User', password: str) -> typing.Dict[str, str]:
        username: str = user.getUsernameForAuth()

        if self.fixedName.value != '':
            username = self.fixedName.value

        proc = username.split('@')
        domain = proc[1] if len(proc) > 1 else ''
        username = proc[0]

        if self.fixedPassword.value != '':
            password = self.fixedPassword.value

        if self.fixedDomain.value != '':
            domain = self.fixedDomain.value

        if self.useEmptyCreds.isTrue():
            username, password, domain = '', '', ''

        # If no domain to be transfered, set it to ''
        if self.withoutDomain.isTrue():
            domain = ''

        if '.' in domain:  # Dotter domain form
            username = username + '@' + domain
            domain = ''

        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)

        return {'protocol': self.protocol, 'username': username, 'password': password, 'domain': domain}

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
        credsInfo = self.processUserAndPassword(userService, user, password)
        username, password, domain = credsInfo['username'], credsInfo['password'], credsInfo['domain']

        if domain != '':
            username = domain + '\\' + username

        scrambler = cryptoManager().randomString(32)
        passwordCrypted = cryptoManager().symCrypt(password, scrambler)

        # Build params dict
        params = {
            'protocol': 'rdp',
            'hostname': ip,
            'username': username,
            'password': passwordCrypted,
            'ignore-cert': 'true',
            'security': self.security.value,
            'drive-path': '/share/{}'.format(user.uuid),
            'create-drive-path': 'true'
        }

        if self.enableFileSharing.isTrue():
            params['enable-drive'] = 'true'

        if self.serverLayout.value != '-':
            params['server-layout'] = self.serverLayout.value

        if self.enableAudio.isTrue() is False:
            params['disable-audio'] = 'true'

        if self.enablePrinting.isTrue() is True:
            params['enable-printing'] = 'true'
            params['printer-name'] = 'UDS-Printer'

        if self.wallpaper.isTrue() is True:
            params['enable-wallpaper'] = 'true'

        if self.desktopComp.isTrue() is True:
            params['enable-desktop-composition'] = 'true'

        if self.smooth.isTrue() is True:
            params['enable-font-smoothing'] = 'true'

        logger.debug('RDP Params: %s', params)

        ticket = models.TicketStore.create(params, validity=self.ticketValidity.num())

        return HttpResponseRedirect("{}/transport/?{}.{}&{}".format(
            self.guacamoleServer.value,
            ticket,
            scrambler,
            request.build_absolute_uri(reverse('utility.closer'))
            ))
