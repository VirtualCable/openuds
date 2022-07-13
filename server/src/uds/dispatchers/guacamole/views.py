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
import typing
import logging

from django.http import HttpResponse

from uds.models import TicketStore, UserService, TunnelToken
from uds.core.auths import auth
from uds.core.managers import cryptoManager
from uds.core.util import log
from uds.core.util.stats import events
from uds.core.util.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

ERROR = "ERROR"
CONTENT_TYPE = 'text/plain'

# We will use the cache to "hold" the tickets valid for users


def dict2resp(dct: typing.Mapping[typing.Any, typing.Any]) -> str:
    return '\r'.join((str(k) + '\t' + str(v) for k, v in dct.items()))


@auth.trustedSourceRequired
def guacamole(
    request: ExtendedHttpRequestWithUser, token: str, tunnelId: str
) -> HttpResponse:
    if not TunnelToken.validateToken(token):
        logger.error('Invalid token %s from %s', token, request.ip)
        return HttpResponse(ERROR, content_type=CONTENT_TYPE)
    logger.debug('Received credentials request for tunnel id %s', tunnelId)

    try:
        tunnelId, scrambler = tunnelId.split('.')

        # All strings excetp "ticket-info", that is fixed if it exists later
        val = typing.cast(
            typing.MutableMapping[str, str], TicketStore.get(tunnelId, invalidate=False)
        )

        # Extra check that the ticket data belongs to original requested user service/user
        if 'ticket-info' in val:
            ti = typing.cast(typing.Mapping[str, str], val['ticket-info'])  # recast to dict
            del val['ticket-info']  # Do not send this data to guacamole!! :)

            try:
                userService = UserService.objects.get(uuid=ti['userService'])
                if not userService.isUsable() or not userService.user:
                    # Not usable, or not assigned to a user, we will not use it
                    raise Exception() 
                # Log message and event
                protocol = 'RDS' if 'remote-app' in val else val['protocol'].upper()
                host = val.get('hostname', '0.0.0.0')
                msg = f'User {userService.user.name} started HTML5 {protocol} tunnel to {host}.'
                log.doLog(userService.user.manager, log.INFO, msg)
                log.doLog(userService, log.INFO, msg)

                events.addEvent(
                    userService.deployed_service,
                    events.ET_TUNNEL_OPEN,
                    username=userService.user.pretty_name,
                    source='HTML5-'
                    + protocol,  # On HTML5, currently src is not provided by Guacamole
                    dstip=host,
                    uniqueid=userService.unique_id,
                )

            except Exception:
                logger.error(
                    'The requested guacamole userservice does not exists anymore'
                )
                raise  # Let it be handled by the upper layers
            if userService.user.uuid != ti['user']:
                logger.error(
                    'The requested userservice has changed owner and is not accesible'
                )
                raise Exception()  # Let it be handled by the upper layers

        if 'password' in val:
            val['password'] = cryptoManager().symDecrpyt(val['password'], scrambler)

        response = dict2resp(val)
    except Exception:
        # logger.error('Invalid guacamole ticket (F5 on client?): %s', tunnelId)
        return HttpResponse(ERROR, content_type=CONTENT_TYPE)

    return HttpResponse(response, content_type=CONTENT_TYPE)
