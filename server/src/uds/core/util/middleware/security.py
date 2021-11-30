# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 Virtual Cable S.L.U.
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
import re
import logging
import typing

logger = logging.getLogger(__name__)

from django.http import HttpResponse

if typing.TYPE_CHECKING:
    from django.http import HttpRequest

# Simple Bot detection
bot = re.compile(r'bot|spider', re.IGNORECASE)


class UDSSecurityMiddleware:
    '''
    This class contains all the security checks done by UDS in order to add some extra protection.
    '''

    get_response: typing.Any  # typing.Callable[['HttpRequest'], 'HttpResponse']

    def __init__(
        self, get_response: typing.Callable[['HttpRequest'], 'HttpResponse']
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: 'HttpRequest') -> 'HttpResponse':
        # If bot, break now
        ua = request.META.get('HTTP_USER_AGENT', 'Connection Maybe a bot. No user agent detected.')
        if bot.search(ua):
            # Return emty response if bot is detected
            logger.info(
                'Denied Bot %s from %s to %s',
                ua,
                request.META.get(
                    'REMOTE_ADDR',
                    request.META.get('HTTP_X_FORWARDED_FOR', '').split(",")[-1],
                ),
                request.path,
            )
            return HttpResponse(content='Forbbiden', status=403)

        response = self.get_response(request)
        # Legacy browser support for X-XSS-Protection
        response.headers.setdefault('X-XSS-Protection', '1; mode=block')
        # Add Content-Security-Policy, allowing same origin and inline scripts, images from any https source and data:
        response.headers.setdefault('Content-Security-Policy', "default-src 'self' 'unsafe-inline'; img-src 'self' https: data:;")

        return response
