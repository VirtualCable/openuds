# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import threading
import logging
import typing
import datetime

from django.http import HttpRequest, HttpResponse

from uds.core.util import OsDetector
from uds.core.util.Config import GlobalConfig
from uds.core.auths.auth import ROOT_ID, USER_KEY, getRootUser
from uds.models import User


logger = logging.getLogger(__name__)

_requests: typing.Dict[int, typing.Tuple[HttpRequest, datetime.datetime]] = {}


def getIdent() -> int:
    ident = threading.current_thread().ident
    return ident if ident else -1


def getRequest() -> HttpRequest:
    ident = getIdent()
    if ident in _requests:
        return _requests[ident][0]

    return HttpRequest()


class GlobalRequestMiddleware:
    def __init__(self, get_response: typing.Callable[[HttpRequest], HttpResponse]):
        self._get_response: typing.Callable[[HttpRequest], HttpResponse] = get_response

    def _process_request(self, request: HttpRequest) -> None:
        # Add IP to request
        GlobalRequestMiddleware.fillIps(request)
        # Ensures request contains os
        request.os = OsDetector.getOsFromUA(request.META.get('HTTP_USER_AGENT', 'Unknown'))
        # Ensures that requests contains the valid user
        GlobalRequestMiddleware.getUser(request)

        # Store request on cache
        _requests[getIdent()] = (request, datetime.datetime.now())


    def _process_response(self, request: HttpRequest, response: HttpResponse):
        # Remove IP from global cache (processing responses after this will make global request unavailable,
        # but can be got from request again)
        ident = getIdent()
        logger.debug('Deleting %s', ident)
        try:
            if ident in _requests:
                del _requests[ident]  # Remove stored request
            else:
                logger.info('Request id %s not stored in cache', ident)
        except Exception:
            logger.exception('Deleting stored request')
        return response

    def __call__(self, request: HttpRequest):
        self._process_request(request)

        response = self._get_response(request)

        return self._process_response(request, response)

    @staticmethod
    def fillIps(request: HttpRequest):
        """
        Obtains the IP of a Django Request, even behind a proxy

        Returns the obtained IP, that always will be a valid ip address.
        """
        behind_proxy = GlobalConfig.BEHIND_PROXY.getBool(False)
        try:
            request.ip = request.META['REMOTE_ADDR']
        except Exception:
            logger.exception('Request ip not found!!')
            request.ip = '0.0.0.0'  # No remote addr?? set this IP to a "basic" one, anyway, this should never ocur

        try:
            proxies = request.META['HTTP_X_FORWARDED_FOR'].split(",")
            request.ip_proxy = proxies[0]

            if  request.ip is None or behind_proxy is True:  # Request.IP will be None in case of nginx & gunicorn
                request.ip = request.ip_proxy  # Stores the ip
                # will raise "list out of range", leaving ip_proxy = proxy in case of no other proxy apart of nginx
                request.ip_proxy = proxies[1]
        except Exception:
            request.ip_proxy = request.ip

    @staticmethod
    def getUser(request: HttpRequest)-> None:
        """
        Ensures request user is the correct user
        """
        user_id: str = request.session.get(USER_KEY)
        user: typing.Optional[User] = None
        if user_id:
            try:
                if user_id == ROOT_ID:
                    user = getRootUser()
                else:
                    user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                user = None

        logger.debug('User at Middleware: %s %s', user_id, user)
        request.user = user
