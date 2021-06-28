# -*- coding: utf-8 -*-

#
# Copyright (c) 2013-2019 Virtual Cable S.L.
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

from django.http import HttpResponse, HttpRequest

from uds.models import TicketStore, UserService
from uds.core.auths import auth
from uds.core.managers import cryptoManager


logger = logging.getLogger(__name__)

ERROR = "ERROR"
CONTENT_TYPE = 'text/plain'

# We will use the cache to "hold" the tickets valid for users


def dict2resp(dct):
    return '\r'.join((k + '\t' + v for k, v in dct.items()))


@auth.trustedSourceRequired
def guacamole(request: HttpRequest, tunnelId: str) -> HttpResponse:
    logger.debug('Received credentials request for tunnel id %s', tunnelId)

    try:
        tunnelId, scrambler = tunnelId.split('.')

        val = TicketStore.get(tunnelId, invalidate=False)

        # Extra check that the ticket data belongs to original requested user service/user
        if 'ticket-info' in val:
            ti = val['ticket-info']
            del val['ticket-info']   # Do not send this data to guacamole!! :)

            try:
                userService = UserService.objects.get(uuid=ti['userService'])
            except Exception:
                logger.error('The requested guacamole userservice does not exists anymore')
                raise
            if userService.user.uuid != ti['user']:
                logger.error('The requested userservice has changed owner and is not accesible')
                raise Exception()

        if 'password' in val:
            val['password'] = cryptoManager().symDecrpyt(val['password'], scrambler)

        response = dict2resp(val)
    except Exception:
        # logger.error('Invalid guacamole ticket (F5 on client?): %s', tunnelId)
        return HttpResponse(ERROR, content_type=CONTENT_TYPE)

    return HttpResponse(response, content_type=CONTENT_TYPE)

@auth.trustedSourceRequired
def guacamole_authenticated(request: HttpRequest, authId: str, tunnelId: str) -> HttpResponse:
    authId = authId[:48]
    # TODO: Check the authId validity
    return guacamole(request, tunnelId)