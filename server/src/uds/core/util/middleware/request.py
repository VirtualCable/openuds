# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
import datetime
import logging
import typing

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from uds.core.util import os_detector as OsDetector
from uds.core.util.config import GlobalConfig
from uds.core.auths.auth import EXPIRY_KEY, ROOT_ID, USER_KEY, getRootUser, webLogout
from uds.core.util.request import (
    setRequest,
    delCurrentRequest,
    cleanOldRequests,
    ExtendedHttpRequest,
)
from uds.models import User

logger = logging.getLogger(__name__)

# How often to check the requests cache for stuck objects
CHECK_SECONDS = 3600 * 24  # Once a day is more than enough


class GlobalRequestMiddleware:
    lastCheck: typing.ClassVar[datetime.datetime] = datetime.datetime.now()

    def __init__(self, get_response: typing.Callable[[HttpRequest], HttpResponse]):
        self._get_response: typing.Callable[[HttpRequest], HttpResponse] = get_response

    def _process_response(self, request: ExtendedHttpRequest, response: HttpResponse):
        # Remove IP from global cache (processing responses after this will make global request unavailable,
        # but can be got from request again)
        delCurrentRequest()
        # Clean old stored if needed
        GlobalRequestMiddleware.cleanStuckRequests()

        return response

    def __call__(self, request: ExtendedHttpRequest):
        # Add IP to request
        GlobalRequestMiddleware.fillIps(request)

        # Store request on cache
        setRequest(request=request)

        # Ensures request contains os
        request.os = OsDetector.getOsFromUA(
            request.META.get('HTTP_USER_AGENT', 'Unknown')
        )

        # Ensures that requests contains the valid user
        GlobalRequestMiddleware.getUser(request)

        # Now, check if session is timed out...
        if request.user:
            # return HttpResponse(content='Session Expired', status=403, content_type='text/plain')
            now = timezone.now()
            expiry = request.session.get(EXPIRY_KEY, now)
            if expiry < now:
                try:
                    return webLogout(
                        request=request
                    )  # Ignore the response, just processes usere session logout
                except Exception:
                    return HttpResponse(content='Session Expired', status=403)
            # Update session timeout..self.
            request.session[EXPIRY_KEY] = now + datetime.timedelta(
                seconds=GlobalConfig.SESSION_DURATION_ADMIN.getInt()
                if request.user.isStaff()
                else GlobalConfig.SESSION_DURATION_USER.getInt()
            )

        response = self._get_response(request)

        return self._process_response(request, response)

    @staticmethod
    def cleanStuckRequests() -> None:
        # In case of some exception, keep clean very old request from time to time...
        if (
            GlobalRequestMiddleware.lastCheck
            > datetime.datetime.now() - datetime.timedelta(seconds=CHECK_SECONDS)
        ):
            return
        cleanOldRequests()

    @staticmethod
    def fillIps(request: ExtendedHttpRequest):
        """
        Obtains the IP of a Django Request, even behind a proxy

        Returns the obtained IP, that always will be a valid ip address.
        """
        behind_proxy = GlobalConfig.BEHIND_PROXY.getBool(False)
        try:
            request.ip = request.META.get('REMOTE_ADDR', '')
        except Exception:
            request.ip = ''  # No remote addr?? ...

        # X-FORWARDED-FOR: CLIENT, FAR_PROXY, PROXY, NEAR_PROXY, NGINX
        # We will accept only 2 proxies, the last ones
        proxies = list(
            reversed(
                [
                    i.split('%')[0]
                    for i in request.META.get('HTTP_X_FORWARDED_FOR', '').split(",")
                ]
            )
        )
        # proxies = list(reversed(['172.27.0.8', '172.27.0.128', '172.27.0.1']))
        # proxies = list(reversed(['172.27.0.12', '172.27.0.1']))
        # proxies = list(reversed(['172.27.0.12']))
        # request.ip = ''

        logger.debug('Detected proxies: %s', proxies)

        # Request.IP will be None in case of nginx & gunicorn using sockets, as we do
        if not request.ip:
            request.ip = proxies[0]  # Stores the ip
            proxies = proxies[1:]  # Remove from proxies list

        logger.debug('Proxies: %s', proxies)

        request.ip_proxy = proxies[0] if proxies and proxies[0] else request.ip

        if behind_proxy:
            request.ip = request.ip_proxy
            request.ip_proxy = proxies[1] if len(proxies) > 1 else request.ip
            logger.debug('Behind a proxy is active')

        logger.debug('ip: %s, ip_proxy: %s', request.ip, request.ip_proxy)

    @staticmethod
    def getUser(request: ExtendedHttpRequest) -> None:
        """
        Ensures request user is the correct user
        """
        user_id = request.session.get(USER_KEY)
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
