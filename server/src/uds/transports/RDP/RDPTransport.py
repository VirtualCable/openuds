# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
from uds.core.util import OsDetector
from uds.core.util import tools
from .BaseRDPTransport import BaseRDPTransport
from .RDPFile import RDPFile

import logging

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30

__updated__ = '2018-07-19'


class RDPTransport(BaseRDPTransport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('RDP')
    typeType = 'RDPTransport'
    typeDescription = _('RDP Protocol. Direct connection.')

    useEmptyCreds = BaseRDPTransport.useEmptyCreds
    fixedName = BaseRDPTransport.fixedName
    fixedPassword = BaseRDPTransport.fixedPassword
    withoutDomain = BaseRDPTransport.withoutDomain
    fixedDomain = BaseRDPTransport.fixedDomain
    allowSmartcards = BaseRDPTransport.allowSmartcards
    allowPrinters = BaseRDPTransport.allowPrinters
    allowDrives = BaseRDPTransport.allowDrives
    allowSerials = BaseRDPTransport.allowSerials
    allowClipboard = BaseRDPTransport.allowClipboard
    allowAudio = BaseRDPTransport.allowAudio

    wallpaper = BaseRDPTransport.wallpaper
    multimon = BaseRDPTransport.multimon
    aero = BaseRDPTransport.aero
    smooth = BaseRDPTransport.smooth
    credssp = BaseRDPTransport.credssp

    screenSize = BaseRDPTransport.screenSize
    colorDepth = BaseRDPTransport.colorDepth

    alsa = BaseRDPTransport.alsa
    multimedia = BaseRDPTransport.multimedia
    redirectHome = BaseRDPTransport.redirectHome
    printerString = BaseRDPTransport.printerString
    smartcardString = BaseRDPTransport.smartcardString
    customParameters = BaseRDPTransport.customParameters

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        # We use helper to keep this clean
        # prefs = user.prefs('rdp')

        ci = self.getConnectionInfo(userService, user, password)
        username, password, domain = ci['username'], ci['password'], ci['domain']

        # width, height = CommonPrefs.getWidthHeight(prefs)
        # depth = CommonPrefs.getDepth(prefs)
        width, height = self.screenSize.value.split('x')
        depth = self.colorDepth.value

        r = RDPFile(width == '-1' or height == '-1', width, height, depth, target=os['OS'])
        r.enablecredsspsupport = ci.get('sso', self.credssp.isTrue())
        r.address = '{}:{}'.format(ip, 3389)
        r.username = username
        r.password = password
        r.domain = domain
        r.redirectPrinters = self.allowPrinters.isTrue()
        r.redirectSmartcards = self.allowSmartcards.isTrue()
        r.redirectDrives = self.allowDrives.value
        r.redirectHome = self.redirectHome.isTrue()
        r.redirectSerials = self.allowSerials.isTrue()
        r.enableClipboard = self.allowClipboard.isTrue()
        r.redirectAudio = self.allowAudio.isTrue()
        r.showWallpaper = self.wallpaper.isTrue()
        r.multimon = self.multimon.isTrue()
        r.desktopComposition = self.aero.isTrue()
        r.smoothFonts = self.smooth.isTrue()
        r.multimedia = self.multimedia.isTrue()
        r.alsa = self.alsa.isTrue()
        r.smartcardString = self.smartcardString.value
        r.printerString = self.printerString.value
        r.linuxCustomParameters = self.customParameters.value

        # data
#         data = {
#             'os': os['OS'],
#             'ip': ip,
#             'port': 3389,
#             'username': username,
#             'password': password,
#             'hasCredentials': username != '' and password != '',
#             'domain': domain,
#             'width': width,
#             'height': height,
#             'depth': depth,
#             'printers': self.allowPrinters.isTrue(),
#             'smartcards': self.allowSmartcards.isTrue(),
#             'drives': self.allowDrives.isTrue(),
#             'serials': self.allowSerials.isTrue(),
#             'compression': True,
#             'wallpaper': self.wallpaper.isTrue(),
#             'multimon': self.multimon.isTrue(),
#             'fullScreen': width == -1 or height == -1,
#             'this_server': request.build_absolute_uri('/')
#         }

        os = {
            OsDetector.Windows: 'windows',
            OsDetector.Linux: 'linux',
            OsDetector.Macintosh: 'macosx'

        }.get(os['OS'])

        if os is None:
            logger.error('Os not detected for RDP Transport: {}'.format(request.META.get('HTTP_USER_AGENT', 'Unknown')))
            return super(RDPTransport, self).getUDSTransportScript(userService, transport, ip, os, user, password, request)

        sp = {
            'password': password,
            'this_server': request.build_absolute_uri('/'),
        }

        if os == 'windows':
            if password != '':
                r.password = '{password}'
            sp.update({
                'as_file': r.as_file,
            })
        elif os == 'linux':
            sp.update({
                'as_new_xfreerdp_params': r.as_new_xfreerdp_params,
                'as_rdesktop_params': r.as_rdesktop_params,
                'address': r.address,
            })
        else:  # Mac
            sp.update({
                'as_file': r.as_file,
                'ip': ip,
                'as_cord_url': r.as_cord_url,
            })
            if domain != '':
                sp['usernameWithDomain'] = '{}\\\\{}'.format(domain, username)
            else:
                sp['usernameWithDomain'] = username


        return self.getScript('scripts/{}/direct.py', os, sp)
