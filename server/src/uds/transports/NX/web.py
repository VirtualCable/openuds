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

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from uds.core.util import OsDetector
import logging, os, sys

logger = logging.getLogger(__name__)


def simpleScrambler(data):
    '''
    Simple scrambler so password are not seen at source page
    '''
    res = []
    n = ord('M')
    pos = 0
    for c in data:
        res.append( chr(ord(c) ^ n) )
        n = n ^ pos
        pos = pos + 1
    return "".join(res).encode('hex')
    


def generateHtmlForNX(transport, idUserService, idTransport, ip, os, user, password, extra):
    isMac = os['OS'] == OsDetector.Macintosh
    applet = reverse('uds.web.views.transcomp', kwargs = { 'idTransport' : idTransport, 'componentId' : '1' })
    # Gets the codebase, simply remove last char from applet
    codebase = applet[:-1]
    # We generate the "data" parameter
    data = simpleScrambler( '\t'.join([
        'user:' + user,
        'pass:' + password,
        'ip:' + ip,
        'port:' + extra['port'],
        'session:' + extra['session'],
        'connection:' + extra['connection'],
        'cacheDisk:' + extra['cacheDisk'],
        'cacheMem:' + extra['cacheMem'],
        'width:' + str(extra['width']),
        'height:' + str(extra['height']),
        'is:' + idUserService
        ]))
    if isMac is True:
        msg = '<p>' + _('In order to use this transport, you need to install first OpenNX Client for mac') + '</p>'
        msg += '<p>' + _('You can oibtain it from ') + '<a href="http://opennx.net/download.html">' + _('OpenNx Website') + '</a></p>'
    else:
        msg = '<p>' + _('In order to use this transport, you need to install first Nomachine Nx Client version 3.5.x') + '</p>'
        msg +='<p>' + _('you can obtain it for your platform from') + '<a href="http://www.nomachine.com/download.php">' + _('nochamine web site') + '</a></p>' 
    res = '<div idTransport="applet"><applet code="NxTransportApplet.class" codebase="%s" archive="%s" width="140" height="22"><param name="data" value="%s"/><param name="permissions" value="all-permissions"/></applet></div>' % (codebase, '1', data )
    res += '<div>' + msg + '</div>'
    return res
    

def getHtmlComponent(module, componentId):
    dict = { '1' : ['nxtransport.jar', 'application/java-archive' ]}
    
    if dict.has_key(componentId) == False:
        return ['text/plain', 'no component']
    fname = os.path.dirname(sys.modules[module].__file__) + '/applet/' + dict[componentId][0]
    logger.debug('Loading component {0} from {1}'.format(componentId, fname))

    f = open(fname, 'rb')
    data = f.read()
    f.close()
    return [ dict[componentId][1], data ]