# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2016 Virtual Cable S.L.
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

from uds.core.util import OsDetector
from uds.core.util.Config import GlobalConfig
from uds.core.auths.auth import ROOT_ID, USER_KEY, getRootUser
from uds.models import User

import threading
import logging

__updated__ = '2016-08-26'

logger = logging.getLogger(__name__)

_requests = {}


def getIdent():
    return threading.current_thread().ident


def getRequest():
    ident = getIdent()
    if ident in _requests:
        return _requests[ident]
    return {}


class GlobalRequestMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def process_request(self, request):
        # Add IP to request
        GlobalRequestMiddleware.fillIps(request)
        # Ensures request contains os
        request.os = OsDetector.getOsFromUA(request.META.get('HTTP_USER_AGENT', 'Unknown'))
        # Ensures that requests contains the valid user
        GlobalRequestMiddleware.getUser(request)

        # Add a counter var, reseted on every request
        _requests[getIdent()] = request
        return None

    def process_response(self, request, response):
        # Remove IP from global cache (processing responses after this will make global request unavailable,
        # but can be got from request again)
        ident = getIdent()
        logger.debug('Deleting {}'.format(ident))
        try:
            if ident in _requests:
                del _requests[ident]
            else:
                logger.info('Request id {} not stored'.format(ident))
        except Exception:
            logger.exception('Deleting stored request')
        return response

    def __call__(self, request):
        self.process_request(request)

        response = self.get_response(request)

        return self.process_response(request, response)

    @staticmethod
    def fillIps(request):
        '''
        Obtains the IP of a Django Request, even behind a proxy

        Returns the obtained IP, that always will be a valid ip address.
        '''
        behind_proxy = GlobalConfig.BEHIND_PROXY.getBool(False)
        try:
            request.ip = request.META['REMOTE_ADDR']
        except:
            logger.exception('Request ip not found!!')
            request.ip = '0.0.0.0'  # No remote addr?? set this IP to a "basic" one, anyway, this should never ocur

        try:
            request.ip_proxy = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0]

            if behind_proxy is True:
                request.ip = request.ip_proxy
                request.ip_proxy = request.META['HTTP_X_FORWARDED_FOR'].split(",")[1]  # Try to get next proxy

            request.is_proxy = True
        except:
            request.ip_proxy = request.ip
            request.is_proxy = False

    @staticmethod
    def getUser(request):
        '''
        Ensures request user is the correct user
        '''
        user = request.session.get(USER_KEY)
        if user is not None:
            try:
                if user == ROOT_ID:
                    user = getRootUser()
                else:
                    user = User.objects.get(pk=user)
            except User.DoesNotExist:
                user = None

        if user is not None:
            request.user = user
        else:
            request.user = None
