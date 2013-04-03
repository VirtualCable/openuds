# -*- coding: utf-8 -*-

#
# Copyright (c) 2013 Virtual Cable S.L.
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

from django.http import HttpResponse
from uds.core.util.Cache import Cache
from uds.core.util import net
import logging

logger = logging.getLogger(__name__)

ERROR = "ERROR"
CONTENT_TYPE = 'text/plain'

# We will use the cache to "hold" the tickets valid for users

def dict2resp(dct):
    return '\r'.join(( k + '\t' + v  for k, v in dct.iteritems()))

def guacamole(request, tunnelId):
    logger.debug('Received credentials request for tunnel id {0}'.format(tunnelId))

    try:    
        cache = Cache('guacamole')
        
        val = cache.get(tunnelId, None)
    
        # Ensure request for credentials are allowed
        allowFrom = val['allow-from'].replace(' ', '')
        # and remove allow-from from parameters
        del val['allow-from']
        
        allowFrom = net.networksFromString(allowFrom)
        

        # Remove key from cache, just 1 use
        # Cache has a limit lifetime, so we will allow to "reload" the page  
        # cache.remove(tunnelId) 
        
        #response = 'protocol\trdp\rhostname\tw7adolfo\rusername\tadmin\rpassword\ttemporal'
        response = dict2resp(val)

    except:
        return HttpResponse(ERROR, content_type=CONTENT_TYPE)

    
    
    
    return HttpResponse(response, content_type=CONTENT_TYPE)
