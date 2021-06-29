# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import secrets
import logging
import typing

from uds import models
from uds.core import managers
from uds.REST import Handler
from uds.REST import AccessDenied
from uds.core.auths.auth import isTrustedSource
from uds.core.util import log, net, request
from uds.core.util.stats import events

logger = logging.getLogger(__name__)

MAX_SESSION_LENGTH = 60*60*24*7

# Enclosed methods under /tunnel path
class TunnelTicket(Handler):
    """
    Processes tunnel requests
    """
    authenticated = False  # Client requests are not authenticated
    path = 'tunnel'
    name = 'ticket'

    def get(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Processes get requests, currently none
        """
        logger.debug(
            'Tunnel parameters for GET: %s (%s) from %s', self._args, self._params, self._request.ip
        )

        if (
            not isTrustedSource(self._request.ip)
            or len(self._args) != 3
            or len(self._args[0]) != 48
        ):
            # Invalid requests
            raise AccessDenied()

        # Take token from url
        token = self._args[2][:48]
        if not models.TunnelToken.validateToken(token):
            logger.error('Invalid token %s from %s', token, self._request.ip)
            raise AccessDenied()
        

        # Try to get ticket from DB
        try:
            user, userService, host, port, extra = models.TicketStore.get_for_tunnel(
                self._args[0]
            )
            data = {}
            if self._args[1][:4] == 'stop':
                sent, recv = self._params['sent'], self._params['recv']
                # Ensures extra exists...
                extra = extra or {}
                now = models.getSqlDatetimeAsUnix()
                totalTime = now - extra.get('b', now-1)               
                msg = f'User {user.name} stopped tunnel {extra.get("t", "")[:8]}... to {host}:{port}: u:{sent}/d:{recv}/t:{totalTime}.'
                log.doLog(user.manager, log.INFO, msg)
                log.doLog(userService, log.INFO, msg)
            else:
                if net.ipToLong(self._args[1][:32]) == 0:
                    raise Exception('Invalid from IP')
                events.addEvent(
                    userService.deployed_service,
                    events.ET_TUNNEL_ACCESS,
                    username=user.pretty_name,
                    srcip=self._args[1],
                    dstip=host,
                    uniqueid=userService.unique_id,
                )
                msg = f'User {user.name} started tunnel {self._args[0][:8]}... to {host}:{port} from {self._args[1]}.'
                log.doLog(user.manager, log.INFO, msg)
                log.doLog(userService, log.INFO, msg)
                # Generate new, notify only, ticket
                rstr = managers.cryptoManager().randomString(length=8)
                notifyTicket = models.TicketStore.create_for_tunnel(
                    userService=userService,
                    port=port,
                    host=host,
                    extra={'t': self._args[0], 'b': models.getSqlDatetimeAsUnix()},
                    validity=MAX_SESSION_LENGTH)
                data = {
                    'host': host,
                    'port': port,
                    'notify': notifyTicket
                }

            return data
        except Exception as e:
            logger.info('Ticket ignored: %s', e)
            raise AccessDenied()


class TunnelRegister(Handler):
    needs_admin = True
    path = 'tunnel'
    name = 'register'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        tunnelToken: models.TunnelToken
        now = models.getSqlDatetimeAsUnix()
        try:
            # If already exists a token for this MAC, return it instead of creating a new one, and update the information...
            tunnelToken = models.TunnelToken.objects.get(ip=self._params['ip'], hostname= self._params['hostname'])
            # Update parameters
            tunnelToken.username = self._user.pretty_name
            tunnelToken.ip_from = self._request.ip
            tunnelToken.stamp = models.getSqlDatetime()
            tunnelToken.save()
        except Exception:
            try:
                tunnelToken = models.TunnelToken.objects.create(
                    username=self._user.pretty_name,
                    ip_from=self._request.ip,
                    ip=self._params['ip'],
                    hostname=self._params['hostname'],
                    token=secrets.token_urlsafe(36),
                    stamp=models.getSqlDatetime()
                )
            except Exception as e:
                return {
                    'result': '',
                    'stamp': now,
                    'error': str(e)
                }
        return {
            'result': tunnelToken.token,
            'stamp': now
        }
