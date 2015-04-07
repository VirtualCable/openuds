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
from uds.core.util import OsDetector
from .BaseRDPTransport import BaseRDPTransport
from .RDPFile import RDPFile

import logging
import os

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class RDPTransport(BaseRDPTransport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('RDP Transport (direct)')
    typeType = 'RDPTransport'
    typeDescription = _('RDP Transport for direct connection')

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
    multimon = BaseRDPTransport.multimon

    def windowsScript(self, data):
        r = RDPFile(data['fullScreen'], data['width'], data['height'], data['depth'], target=OsDetector.Windows)
        r.address = '{}:{}'.format(data['ip'], 3389)
        r.username = data['username']
        r.password = '{password}'
        r.domain = data['domain']
        r.redirectPrinters = self.allowPrinters.isTrue()
        r.redirectSmartcards = self.allowSmartcards.isTrue()
        r.redirectDrives = self.allowDrives.isTrue()
        r.redirectSerials = self.allowSerials.isTrue()
        r.showWallpaper = self.wallpaper.isTrue()
        r.multimon = self.multimon.isTrue()

        # The password must be encoded, to be included in a .rdp file, as 'UTF-16LE' before protecting (CtrpyProtectData) it in order to work with mstsc
        return self.getScript('scripts/windows/direct.py').format(os=data['os'], file=r.get(), password=data['password'])

    def macOsXScript(self, data):
        r = RDPFile(data['fullScreen'], data['width'], data['height'], data['depth'], target=OsDetector.Macintosh)
        r.address = '{}:{}'.format(data['ip'], 3389)
        r.username = data['username']
        r.domain = data['domain']
        r.redirectPrinters = self.allowPrinters.isTrue()
        r.redirectSmartcards = self.allowSmartcards.isTrue()
        r.redirectDrives = self.allowDrives.isTrue()
        r.redirectSerials = self.allowSerials.isTrue()
        r.showWallpaper = self.wallpaper.isTrue()
        r.multimon = self.multimon.isTrue()

        if data['domain'] != '':
            username = '{}\\\\{}'.format(data['domain'], data['username'])
        else:
            username = data['username']

        return self.getScript('scripts/macosx/direct.py').format(os=data['os'],
                                                                 file=r.get(),
                                                                 password=data['password'],
                                                                 username=username,
                                                                 ip=data['ip'],
                                                                 this_server=data['this_server'],
                                                                 r=r
                                                                 )

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        # We use helper to keep this clean
        prefs = user.prefs('rdp')

        ci = self.getConnectionInfo(userService, user, password)
        username, password, domain = ci['username'], ci['password'], ci['domain']

        width, height = CommonPrefs.getWidthHeight(prefs)
        depth = CommonPrefs.getDepth(prefs)

        # data
        data = {
            'os': os['OS'],
            'ip': ip,
            'port': 3389,
            'username': username,
            'password': password,
            'domain': domain,
            'width': width,
            'height': height,
            'depth': depth,
            'printers': self.allowPrinters.isTrue(),
            'smartcards': self.allowSmartcards.isTrue(),
            'drives': self.allowDrives.isTrue(),
            'serials': self.allowSerials.isTrue(),
            'compression': True,
            'wallpaper': self.wallpaper.isTrue(),
            'multimon': self.multimon.isTrue(),
            'fullScreen': width == -1 or height == -1,
            'this_server': request.build_absolute_uri('/')
        }

        logger.debug('Detected os: {}'.format(data['os']))

        if data['os'] == OsDetector.Windows:
            return self.windowsScript(data)
        elif data['os'] == OsDetector.Macintosh:
            return self.macOsXScript(data)

        return ''
