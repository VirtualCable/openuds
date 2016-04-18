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

from django.utils.translation import ugettext_noop as _
from uds.core.util import OsDetector
from uds.core.util import tools
from .BaseSPICETransport import BaseSpiceTransport
from .RemoteViewerFile import RemoteViewerFile

import logging

__updated__ = '2016-04-18'

logger = logging.getLogger(__name__)


class SPICETransport(BaseSpiceTransport):
    '''
    Provides access via SPICE to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('RHEV/oVirt SPICE Transport (direct)')
    typeType = 'SPICETransport'
    typeDescription = _('SPICE Transport for direct connection (EXPERIMENTAL)')

    # useEmptyCreds = BaseSpiceTransport.useEmptyCreds
    # fixedName = BaseSpiceTransport.fixedName
    # fixedPassword = BaseSpiceTransport.fixedPassword
    serverCertificate = BaseSpiceTransport.serverCertificate

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        userServiceInstance = userService.getInstance()

        con = userServiceInstance.getConsoleConnection()

        logger.debug('Connection data: {}'.format(con))

        port, secure_port = con['port'], con['secure_port']
        port = -1 if port is None else port
        secure_port = -1 if secure_port is None else secure_port

        r = RemoteViewerFile(con['address'], port, secure_port, con['ticket']['value'], self.serverCertificate.value, con['cert_subject'], fullscreen=False)

        m = tools.DictAsObj({
            'r': r
        })

        os = {
            OsDetector.Windows: 'windows',
            OsDetector.Linux: 'linux',
            OsDetector.Macintosh: 'macosx'
        }.get(os.OS)

        if os is None:
            return super(SPICETransport, self).getUDSTransportScript(self, userService, transport, ip, os, user, password, request)

        return self.getScript('scripts/{}/direct.py'.format(os)).format(m=m)
