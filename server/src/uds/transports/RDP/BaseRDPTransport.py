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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals
from django.utils.translation import ugettext_noop as _
from uds.core.managers.UserPrefsManager import CommonPrefs
from uds.core.ui.UserInterface import gui
from uds.core.transports.BaseTransport import Transport
from uds.core.transports import protocols
from uds.core.util import connection

import logging
import os

__updated__ = '2016-02-26'


logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class BaseRDPTransport(Transport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    iconFile = 'rdp.png'
    protocol = protocols.RDP

    useEmptyCreds = gui.CheckBoxField(label=_('Empty creds'), order=1, tooltip=_('If checked, the credentials used to connect will be emtpy'))
    fixedName = gui.TextField(label=_('Username'), order=2, tooltip=_('If not empty, this username will be always used as credential'))
    fixedPassword = gui.PasswordField(label=_('Password'), order=3, tooltip=_('If not empty, this password will be always used as credential'))
    withoutDomain = gui.CheckBoxField(label=_('Without Domain'), order=4, tooltip=_('If checked, the domain part will always be emptied (to connecto to xrdp for example is needed)'))
    fixedDomain = gui.TextField(label=_('Domain'), order=5, tooltip=_('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'))
    allowSmartcards = gui.CheckBoxField(label=_('Allow Smartcards'), order=6, tooltip=_('If checked, this transport will allow the use of smartcards'))
    allowPrinters = gui.CheckBoxField(label=_('Allow Printers'), order=7, tooltip=_('If checked, this transport will allow the use of user printers'))
    allowDrives = gui.CheckBoxField(label=_('Allow Drives'), order=8, tooltip=_('If checked, this transport will allow the use of user drives'))
    allowSerials = gui.CheckBoxField(label=_('Allow Serials'), order=9, tooltip=_('If checked, this transport will allow the use of user serial ports'))
    wallpaper = gui.CheckBoxField(label=_('Show wallpaper'), order=10, tooltip=_('If checked, the wallpaper and themes will be shown on machine (better user experience, more bandwidth)'))
    multimon = gui.CheckBoxField(label=_('Multiple monitors'), order=10, tooltip=_('If checked, all client monitors will be used for displaying (only works on windows clients)'))
    aero = gui.CheckBoxField(label=_('Allow Aero'), order=11, tooltip=_('If checked, desktop composition will be allowed'))

    def isAvailableFor(self, userService, ip):
        '''
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        '''
        logger.debug('Checking availability for {0}'.format(ip))
        ready = self.cache.get(ip)
        if ready is None:
            # Check again for ready
            if connection.testServer(ip, '3389') is True:
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

        if '.' in domain:  # Dotter domain form
            username = username + '@' + domain
            domain = ''

        # Fix username/password acording to os manager
        username, password = service.processUserPassword(username, password)

        return {'protocol': self.protocol, 'username': username, 'password': password, 'domain': domain}

    def getConnectionInfo(self, service, user, password):
        return self.processUserPassword(service, user, password)

    def getScript(self, script):
        with open(os.path.join(os.path.dirname(__file__), script)) as f:
            data = f.read()
        return data
