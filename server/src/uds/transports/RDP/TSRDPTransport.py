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

from django.utils.translation import ugettext_noop as _
from uds.core.managers.UserPrefsManager import CommonPrefs
from uds.core.ui.UserInterface import gui
from uds.core.transports.BaseTransport import Transport
from uds.core.transports import protocols
from uds.core.util import connection
from uds.core.util.Cache import Cache
from .web import generateHtmlForRdp, getHtmlComponent
from .BaseRDPTransport import BaseRDPTransport

import logging
import random
import string
import time

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class TSRDPTransport(BaseRDPTransport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('RDP Transport (tunneled)')
    typeType = 'TSRDPTransport'
    typeDescription = _('RDP Transport for tunneled connection')
    iconFile = 'rdp.png'
    needsJava = True  # If this transport needs java for rendering
    protocol = protocols.RDP

    tunnelServer = gui.TextField(label=_('Tunnel server'), order=1, tooltip=_('IP or Hostname of tunnel server send to client device ("public" ip) and port. (use HOST:PORT format)'))
    tunnelCheckServer = gui.TextField(label=_('Tunnel host check'), order=2, tooltip=_('If not empty, this server will be used to check if service is running before assigning it to user. (use HOST:PORT format)'))

    useEmptyCreds = BaseRDPTransport.useEmptyCreds
    fixedName = BaseRDPTransport.fixedName
    fixedPassword = BaseRDPTransport.fixedPassword
    withoutDomain = BaseRDPTransport.withoutDomain
    fixedDomain = BaseRDPTransport.fixedDomain
    allowSmartcards = BaseRDPTransport.allowSmartcards
    allowPrinters = BaseRDPTransport.allowPrinters
    allowDrives = BaseRDPTransport.allowDrives
    allowSerials = BaseRDPTransport.allowSerials
    wallpaper = BaseRDPTransport.wallpaper

    def initialize(self, values):
        if values is not None:
            if values['tunnelServer'].count(':') != 1:
                raise Transport.ValidationException(_('Must use HOST:PORT in Tunnel Server Field'))

    def renderForHtml(self, userService, transport, ip, os, user, password):
        # We use helper to keep this clean
        prefs = user.prefs('rdp')

        ci = self.getConnectionInfo(userService, user, password)
        username, password, domain = ci['username'], ci['password'], ci['domain']

        width, height = CommonPrefs.getWidthHeight(prefs)
        depth = CommonPrefs.getDepth(prefs)
        cache = Cache('pam')

        tunuser = ''.join(random.choice(string.letters + string.digits) for _i in range(12)) + ("%f" % time.time()).split('.')[1]
        tunpass = ''.join(random.choice(string.letters + string.digits) for _i in range(12))
        cache.put(tunuser, tunpass, 60 * 10)  # Credential valid for ten minutes, and for 1 use only

        sshHost, sshPort = self.tunnelServer.value.split(':')

        logger.debug('Username generated: {0}, password: {1}'.format(tunuser, tunpass))
        tun = "{0} {1} {2} {3} {4} {5} {6}".format(tunuser, tunpass, sshHost, sshPort, ip, '3389', '9')
        ip = '127.0.0.1'

        # Extra data
        extra = {
            'width': width,
            'height': height,
            'depth': depth,
            'printers': self.allowPrinters.isTrue(),
            'smartcards': self.allowSmartcards.isTrue(),
            'drives': self.allowDrives.isTrue(),
            'serials': self.allowSerials.isTrue(),
            'tun': tun,
            'compression': True,
            'wallpaper': self.wallpaper.isTrue()
        }

        return generateHtmlForRdp(self, userService.uuid, transport.uuid, os, ip, '-1', username, password, domain, extra)
