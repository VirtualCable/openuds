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

from __future__ import unicode_literals
from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core.transports.BaseTransport import Transport
from uds.core.transports import protocols

import logging
import os

__updated__ = '2017-12-15'

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class BaseRDPTransport(Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """
    iconFile = 'rdp.png'
    protocol = protocols.RDP

    useEmptyCreds = gui.CheckBoxField(label=_('Empty creds'), order=11, tooltip=_('If checked, the credentials used to connect will be emtpy'), tab=gui.CREDENTIALS_TAB)
    fixedName = gui.TextField(label=_('Username'), order=12, tooltip=_('If not empty, this username will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    fixedPassword = gui.PasswordField(label=_('Password'), order=13, tooltip=_('If not empty, this password will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    withoutDomain = gui.CheckBoxField(label=_('Without Domain'), order=14, tooltip=_('If checked, the domain part will always be emptied (to connect to xrdp for example is needed)'), tab=gui.CREDENTIALS_TAB)
    fixedDomain = gui.TextField(label=_('Domain'), order=15, tooltip=_('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'), tab=gui.CREDENTIALS_TAB)
    allowSmartcards = gui.CheckBoxField(label=_('Allow Smartcards'), order=20, tooltip=_('If checked, this transport will allow the use of smartcards'), tab=gui.PARAMETERS_TAB)
    allowPrinters = gui.CheckBoxField(label=_('Allow Printers'), order=21, tooltip=_('If checked, this transport will allow the use of user printers'), tab=gui.PARAMETERS_TAB)
    allowDrives = gui.CheckBoxField(label=_('Allow Drives'), order=22, tooltip=_('If checked, this transport will allow the use of user drives'), tab=gui.PARAMETERS_TAB)
    allowSerials = gui.CheckBoxField(label=_('Allow Serials'), order=23, tooltip=_('If checked, this transport will allow the use of user serial ports'), tab=gui.PARAMETERS_TAB)
    allowClipboard = gui.CheckBoxField(label=_('Enable clipboard'), order=24, tooltip=_('If checked, copy-paste functions will be allowed'), tab=gui.PARAMETERS_TAB, defvalue=gui.TRUE)
    credssp = gui.CheckBoxField(label=_('Credssp Support'), order=25, tooltip=_('If checked, will enable Credentials Provider Support)'), tab=gui.PARAMETERS_TAB)

    screenSize = gui.ChoiceField(
        label=_('Screen Size'),
        order=30,
        tooltip=_('Screen size for this transport'),
        defvalue='-1x-1',
        values=[
            {'id': '640x480', 'text': '640x480' },
            {'id': '800x600', 'text': '800x600' },
            {'id': '1024x768', 'text': '1024x768' },
            {'id': '1366x768', 'text': '1366x768' },
            {'id': '1920x1080', 'text': '1920x1080' },
            {'id': '-1x-1', 'text': 'Full screen' },
    ], tab=gui.DISPLAY_TAB)

    colorDepth = gui.ChoiceField(
        label=_('Color depth'),
        order=31,
        tooltip=_('Color depth for this conextion'),
        defvalue='24',
        values=[
            {'id': '8', 'text': '8' },
            {'id': '16', 'text': '16' },
            {'id': '24', 'text': '24' },
            {'id': '32', 'text': '32' },
    ], tab=gui.DISPLAY_TAB)

    wallpaper = gui.CheckBoxField(label=_('Wallpaper/theme'), order=32, tooltip=_('If checked, the wallpaper and themes will be shown on machine (better user experience, more bandwidth)'), tab=gui.DISPLAY_TAB)
    multimon = gui.CheckBoxField(label=_('Multiple monitors'), order=33, tooltip=_('If checked, all client monitors will be used for displaying (only works on windows clients)'), tab=gui.DISPLAY_TAB)
    aero = gui.CheckBoxField(label=_('Allow Desk.Comp.'), order=34, tooltip=_('If checked, desktop composition will be allowed'), tab=gui.DISPLAY_TAB)
    smooth = gui.CheckBoxField(label=_('Font Smoothing'), order=35, tooltip=_('If checked, fonts smoothing will be allowed (windows clients only)'), tab=gui.DISPLAY_TAB)

    multimedia = gui.CheckBoxField(label=_('Multimedia sync'), order=40, tooltip=_('If checked. Linux client will use multimedia parameter for xfreerdp'), tab='Linux Client')
    alsa = gui.CheckBoxField(label=_('Use Alsa'), order=41, tooltip=_('If checked, Linux client will try to use ALSA, otherwise Pulse will be used'), tab='Linux Client')
    printerString = gui.TextField(label=_('Printer string'), order=42, tooltip=_('If printer is checked, the printer string used with xfreerdp client'), tab='Linux Client')
    smartcardString = gui.TextField(label=_('Smartcard string'), order=43, tooltip=_('If smartcard is checked, the smartcard string used with xfreerdp client'), tab='Linux Client')
    customParameters = gui.TextField(label=_('Custom parameters'), order=44, tooltip=_('If not empty, extra parameter to include for Linux Client (for example /usb:id,dev:054c:0268, or aything compatible with your xfreerdp client)'), tab='Linux Client')

    def isAvailableFor(self, userService, ip):
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for {0}'.format(ip))
        ready = self.cache.get(ip)
        if ready is None:
            # Check again for ready
            if self.testServer(userService, ip, '3389') is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            else:
                self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def processedUser(self, userService, userName):
        v = self.processUserPassword(userService, userName, '')
        return v['username']

    def processUserPassword(self, service, user, password):
        username = user.getUsernameForAuth()

        if self.fixedName.value != '':
            username = self.fixedName.value

        proc = username.split('@')
        if len(proc) > 1:
            domain = proc[1]
        else:
            domain = ''
        username = proc[0]

        if self.fixedPassword.value != '':
            password = self.fixedPassword.value
        if self.fixedDomain.value != '':
            domain = self.fixedDomain.value
        if self.useEmptyCreds.isTrue():
            username, password, domain = '', '', ''

        if self.withoutDomain.isTrue():
            domain = ''

        if domain != '':  # If has domain
            if '.' in domain:  # Dotter domain form
                username = username + '@' + domain
                domain = ''
            else:  # In case of a NETBIOS domain (not recomended), join it so processUserPassword can deal with it
                username = domain + '\\' + username
                domain = ''

        # Temporal "fix" to check if we do something on processUserPassword

        # Fix username/password acording to os manager
        username, password = service.processUserPassword(username, password)

        # Recover domain name if needed
        if '\\' in username:
            username, domain = username.split('\\')

        return {'protocol': self.protocol, 'username': username, 'password': password, 'domain': domain}

    def getConnectionInfo(self, service, user, password):
        return self.processUserPassword(service, user, password)

    def getScript(self, scriptName, osName, params):
        # Reads script
        scriptName = scriptName.format(osName)
        with open(os.path.join(os.path.dirname(__file__), scriptName)) as f:
            script = f.read()
        # Reads signature
        with open(os.path.join(os.path.dirname(__file__), scriptName + '.signature')) as f:
            signature = f.read()
        return script, signature, params
