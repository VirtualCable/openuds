# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
 Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing
import collections.abc

from django.http import HttpResponseForbidden
from django.utils import timezone

from uds.core.util import os_detector as OsDetector
from uds.core.util.config import GlobalConfig
from uds.core.auths.auth import (
    AUTHORIZED_KEY,
    EXPIRY_KEY,
    ROOT_ID,
    USER_KEY,
    getRootUser,
    webLogout,
)
from uds.models import User
from uds.core.util.state import State


from . import builder

if typing.TYPE_CHECKING:
    from django.http import HttpResponse
    from uds.core.types.request import ExtendedHttpRequest


logger = logging.getLogger(__name__)

# How often to check the requests cache for stuck objects
CHECK_SECONDS = 3600 * 24  # Once a day is more than enough


def _fill_ips(request: 'ExtendedHttpRequest') -> None:
    """
    Obtains the IP of a Django Request, even behind a proxy

    Returns the obtained IP, that always will be a valid ip address.
    """
    behind_proxy = GlobalConfig.BEHIND_PROXY.getBool(False)

    request.ip = request.META.get('REMOTE_ADDR', '')

    # X-FORWARDED-FOR: CLIENT, FAR_PROXY, PROXY, NEAR_PROXY, NGINX
    # We will accept only 2 proxies, the last ones
    # And the only trusted address, counting with NGINX, will be PROXY if behind_proxy is True
    proxies = list(
        reversed([i.split('%')[0].strip() for i in request.META.get('HTTP_X_FORWARDED_FOR', '').split(",")])
    )

    # Original IP will be empty in case of nginx & gunicorn using sockets, as we do
    if not request.ip:
        request.ip = proxies[0]  # Stores the ip
        proxies = proxies[1:]  # Remove from proxies list

    request.ip_proxy = proxies[0] if proxies and proxies[0] else request.ip

    # Basically, behind_proxy will ignore the LAST proxy, and will use the previous one
    # as proxy_ip (if exists)
    # So, with behind_proxy = True, and X-FORWARDED-FOR is (CLIENT, PROXY1, PROXY2, PROXY3) we will have:
    #   request.ip = PROXY2
    #   request.ip_proxy = PROXY1
    # If behind_proxy = False, we will have:
    #   request.ip = PROXY3
    #   request.ip_proxy = PROXY2

    if behind_proxy:
        request.ip = request.ip_proxy
        request.ip_proxy = proxies[1] if len(proxies) > 1 else request.ip

    # Check if ip are ipv6 and set version field
    request.ip_version = 6 if '.' not in request.ip else 4

    # If ipv4 ip, remove the ::ffff: prefix from ip and ip_proxy
    if request.ip_version == 4:
        request.ip = request.ip.replace('::ffff:', '')
        request.ip_proxy = request.ip_proxy.replace('::ffff:', '')

    logger.debug('ip: %s, ip_proxy: %s', request.ip, request.ip_proxy)


def _get_user(request: 'ExtendedHttpRequest') -> None:
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
    if user and user.state != State.ACTIVE:
        user = None

    logger.debug('User at Middleware: %s %s', user_id, user)

    request.user = user


def _process_request(request: 'ExtendedHttpRequest') -> typing.Optional['HttpResponse']:
    # Add IP to request, user, ...
    # Add IP to request
    _fill_ips(request)
    request.authorized = request.session.get(AUTHORIZED_KEY, False)

    # Ensures request contains os
    request.os = OsDetector.getOsFromUA(request.META.get('HTTP_USER_AGENT', 'Unknown'))

    # Ensures that requests contains the valid user
    _get_user(request)

    # Now, check if session is timed out...
    if request.user:
        # return HttpResponse(content='Session Expired', status=403, content_type='text/plain')
        now = timezone.now()
        try:
            expiry = datetime.datetime.fromisoformat(request.session.get(EXPIRY_KEY, ''))
        except ValueError:
            expiry = now
        if expiry < now:
            try:
                return webLogout(request=request)
            except Exception:  # nosec: intentionaly catching all exceptions and ignoring them
                pass  # If fails, we don't care, we just want to logout
            return HttpResponseForbidden(content='Session Expired', content_type='text/plain')
        # Update session timeout..self.
        request.session[EXPIRY_KEY] = (
            now
            + datetime.timedelta(
                seconds=GlobalConfig.SESSION_DURATION_ADMIN.getInt()
                if request.user.isStaff()
                else GlobalConfig.SESSION_DURATION_USER.getInt()
            )
        ).isoformat()  # store as ISO format, str, json serilizable

    return None


def _process_response(request: 'ExtendedHttpRequest', response: 'HttpResponse') -> 'HttpResponse':
    # Update authorized on session
    if hasattr(request, 'session'):
        request.session[AUTHORIZED_KEY] = request.authorized
    return response


# Compatibility with old middleware, so we can use it in settings.py as it was
GlobalRequestMiddleware = builder.build_middleware(_process_request, _process_response)
