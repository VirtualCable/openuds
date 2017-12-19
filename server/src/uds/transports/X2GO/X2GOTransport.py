# -*- coding: utf-8 -*-

#
# Copyright (c) 2016 Virtual Cable S.L.
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

from django.utils.translation import ugettext_noop as _
from uds.core.managers.UserPrefsManager import CommonPrefs
from uds.core.util import OsDetector
from uds.core.util import tools
from .BaseX2GOTransport import BaseX2GOTransport
from . import x2gofile

import logging

__updated__ = '2017-12-19'

logger = logging.getLogger(__name__)


class X2GOTransport(BaseX2GOTransport):
    '''
    Provides access via SPICE to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('X2Go Transport (Experimental)')
    typeType = 'X2GOTransport'
    typeDescription = _('X2Go Protocol (Experimental). Direct connection.')

    fixedName = BaseX2GOTransport.fixedName
    # fullScreen = BaseX2GOTransport.fullScreen
    desktopType = BaseX2GOTransport.desktopType
    customCmd = BaseX2GOTransport.customCmd
    sound = BaseX2GOTransport.sound
    exports = BaseX2GOTransport.exports
    speed = BaseX2GOTransport.speed

    soundType = BaseX2GOTransport.soundType
    keyboardLayout = BaseX2GOTransport.keyboardLayout
    pack = BaseX2GOTransport.pack
    quality = BaseX2GOTransport.quality

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        prefs = user.prefs('nx')

        ci = self.getConnectionInfo(userService, user, password)
        username = ci['username']
        priv, pub = self.getAndPushKey(username, userService)

        width, height = CommonPrefs.getWidthHeight(prefs)

        desktop = self.desktopType.value
        if desktop == "UDSVAPP":
            desktop = "/usr/bin/udsvapp " + self.customCmd.value

        xf = x2gofile.getTemplate(
            speed=self.speed.value,
            pack=self.pack.value,
            quality=self.quality.value,
            sound=self.sound.isTrue(),
            soundSystem=self.sound.value,
            windowManager=desktop,
            exports=self.exports.isTrue(),
            width=width,
            height=height,
            user=username
        )

        # data
        data = {
            'os': os['OS'],
            'ip': ip,
            'port': 22,
            'username': username,
            'key': priv,
            'width': width,
            'height': height,
            'printers': True,
            'drives': self.exports.isTrue(),
            'fullScreen': width == -1 or height == -1,
            'this_server': request.build_absolute_uri('/'),
            'xf': xf
        }

        m = tools.DictAsObj(data)

        os = {
            OsDetector.Windows: 'windows',
            OsDetector.Linux: 'linux',
            # OsDetector.Macintosh: 'macosx'
        }.get(m.os)

        if os is None:
            return super(X2GOTransport, self).getUDSTransportScript(self, userService, transport, ip, os, user, password, request)

        return self.getScript('scripts/{}/direct.py'.format(os)).format(m=m)
