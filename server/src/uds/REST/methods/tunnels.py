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
import collections.abc
import logging
import typing

from uds import models
from uds.core import exceptions, types
from uds.core.auths.auth import is_source_trusted
from uds.core.util import log, net
from uds.core.util.model import sql_datetime, sql_stamp_seconds
from uds.core.util.stats import events
from uds.REST import Handler

from .servers import ServerRegisterBase

logger = logging.getLogger(__name__)

MAX_SESSION_LENGTH = (
    60 * 60 * 24 * 7 * 2
)  # Two weeks is max session length for a tunneled connection

# Enclosed methods under /tunnel path
class TunnelTicket(Handler):
    """
    Processes tunnel requests
    """

    authenticated = False  # Client requests are not authenticated
    path = 'tunnel'
    name = 'ticket'

    def get(self) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Processes get requests
        """
        logger.debug(
            'Tunnel parameters for GET: %s (%s) from %s',
            self._args,
            self._params,
            self._request.ip,
        )

        if (
            not is_source_trusted(self._request.ip)
            or len(self._args) != 3
            or len(self._args[0]) != 48
        ):
            # Invalid requests
            raise exceptions.rest.AccessDenied()

        # Take token from url
        token = self._args[2][:48]
        if not models.Server.validate_token(token, serverType=types.servers.ServerType.TUNNEL):
            if self._args[1][:4] == 'stop':
                # "Discard" invalid stop requests, because Applications does not like them.
                # RDS connections keep alive for a while after the application is finished,
                # Also, same tunnel can be used for multiple applications, so we need to
                # discard invalid stop requests. (because the data provided is also for "several" applications)")
                return {}
            logger.error('Invalid token %s from %s', token, self._request.ip)
            raise exceptions.rest.AccessDenied()

        # Try to get ticket from DB
        try:
            user, user_service, host, port, extra = models.TicketStore.get_for_tunnel(
                self._args[0]
            )
            host = host or ''
            data = {}
            if self._args[1][:4] == 'stop':
                sent, recv = self._params['sent'], self._params['recv']
                # Ensures extra exists...
                extra = extra or {}
                now = sql_stamp_seconds()
                totalTime = now - extra.get('b', now - 1)
                msg = f'User {user.name} stopped tunnel {extra.get("t", "")[:8]}... to {host}:{port}: u:{sent}/d:{recv}/t:{totalTime}.'
                log.log(user.manager, log.LogLevel.INFO, msg)
                log.log(user_service, log.LogLevel.INFO, msg)

                # Try to log Close event
                try:
                    # If pool does not exists, do not log anything
                    events.add_event(
                        user_service.deployed_service,
                        events.types.stats.EventType.TUNNEL_CLOSE,
                        duration=totalTime,
                        sent=sent,
                        received=recv,
                        tunnel=extra.get('t', 'unknown'),
                    )
                except Exception as e:
                    logger.warning('Error logging tunnel close event: %s', e)

            else:
                if net.ip_to_long(self._args[1][:32]).version == 0:
                    raise Exception('Invalid from IP')
                events.add_event(
                    user_service.deployed_service,
                    events.types.stats.EventType.TUNNEL_OPEN,
                    username=user.pretty_name,
                    srcip=self._args[1],
                    dstip=host,
                    tunnel=self._args[0],
                )
                msg = f'User {user.name} started tunnel {self._args[0][:8]}... to {host}:{port} from {self._args[1]}.'
                log.log(user.manager, log.LogLevel.INFO, msg)
                log.log(user_service, log.LogLevel.INFO, msg)
                # Generate new, notify only, ticket
                notifyTicket = models.TicketStore.create_for_tunnel(
                    userService=user_service,
                    port=port,
                    host=host,
                    extra={
                        't': self._args[0],  # ticket
                        'b': sql_stamp_seconds(),  # Begin time stamp
                    },
                    validity=MAX_SESSION_LENGTH,
                )
                data = {'host': host, 'port': port, 'notify': notifyTicket}

            return data
        except Exception as e:
            logger.info('Ticket ignored: %s', e)
            raise exceptions.rest.AccessDenied() from e


class TunnelRegister(ServerRegisterBase):
    needs_admin = True
    path = 'tunnel'
    name = 'register'

    # Just a compatibility method for old tunnel servers
    def post(self) -> collections.abc.MutableMapping[str, typing.Any]:
        self._params['type'] = types.servers.ServerType.TUNNEL
        self._params['os'] = self._params.get('os', types.os.KnownOS.LINUX.os_name())  # Legacy tunnels are always linux
        self._params['version'] = ''  # No version for legacy tunnels, does not respond to API requests from UDS
        self._params['certificate'] = '' # No certificate for legacy tunnels, does not respond to API requests from UDS
        return super().post()
