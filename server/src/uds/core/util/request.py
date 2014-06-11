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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

import threading
import logging

__updated__ = '2014-06-11'

logger = logging.getLogger(__name__)

_requests = {}


def getRequest():
    return _requests[threading._get_ident()]


class GlobalRequestMiddleware(object):
    def process_request(self, request):
        # Add IP to request
        GlobalRequestMiddleware.fillIps(request)
        _requests[threading._get_ident()] = request
        return None

    def process_response(self, request, response):
        # Remove IP from global cache (processing responses after this will make global request unavailable,
        # but can be got from request again)
        try:
            del _requests[threading._get_ident()]
        except:
            logger.exception('Deleting stored request')
        return response

    @staticmethod
    def fillIps(request):
        '''
        Obtains the IP of a Django Request, even behind a proxy

        Returns the obtained IP, that is always be a valid ip address.
        '''
        try:
            request.ip = request.META['REMOTE_ADDR']
        except:
            logger.exception('Request ip not found!!')
            request.ip = '0.0.0.0'  # No remote addr?? set this IP to a "basic" one, anyway, this should never ocur

        try:
            request.ip_proxy = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0]
            request.is_proxy = True
        except:
            request.ip_proxy = request.ip
            request.is_proxy = False
