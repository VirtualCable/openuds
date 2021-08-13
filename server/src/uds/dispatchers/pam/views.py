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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from django.http import HttpResponseNotAllowed, HttpResponse, HttpRequest
from uds.models import TicketStore
from uds.core.auths import auth
from uds.core.util.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

# We will use the cache to "hold" the tickets valid for users


@auth.trustedSourceRequired
def pam(request: ExtendedHttpRequestWithUser) -> HttpResponse:
    response = ''
    if request.method == 'POST':
        return HttpResponseNotAllowed(['GET'])
    if 'id' in request.GET and 'pass' in request.GET:
        # This is an "auth" request
        ids = request.GET.getlist('id')
        response = '0'
        # If request is not forged...
        if len(ids) == 1:
            userId = ids[0]
            logger.debug(
                "Auth request for user [%s] and pass [%s]",
                request.GET['id'],
                request.GET['pass'],
            )
            try:
                password = TicketStore.get(userId)
                if password == request.GET['pass']:
                    response = '1'
            except Exception:
                # Non existing ticket, log it and stop
                logger.info('Invalid access from %s using user %s', request.ip, userId)
        else:
            logger.warning(
                'Invalid request from %s: %s',
                request.ip,
                [v for v in request.GET.lists()],
            )
    elif 'uid' in request.GET:
        # This is an "get name for id" call
        logger.debug("NSS Request for id [%s]", request.GET['uid'])
        response = '10000 udstmp'
    elif 'name' in request.GET:
        logger.debug("NSS Request for username [%s]", request.GET['name'])
        response = '10000 udstmp'

    return HttpResponse(response, content_type='text/plain')
