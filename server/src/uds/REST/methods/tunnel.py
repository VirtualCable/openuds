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
import typing
from uds.models.user_service import UserService

from uds import models
from uds.REST import Handler
from uds.REST import AccessDenied
from uds.core.auths.auth import isTrustedSource
from uds.core.util import log, net
from uds.core.util.stats import events

logger = logging.getLogger(__name__)


# Enclosed methods under /tunnel path
class Tunnel(Handler):
    """
    Processes tunnel requests
    """

    authenticated = False  # Client requests are not authenticated

    def get(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Processes get requests, currently none
        """
        logger.debug(
            'Tunnel parameters for GET: %s from %s', self._args, self._request.ip
        )

        if (
            not isTrustedSource(self._request.ip)
            or len(self._args) > 2
            or len(self._args[0]) != 48
        ):
            # Invalid requests
            raise AccessDenied()

        # Try to get ticket from DB
        try:
            user, userService, host, port, _ = models.TicketStore.get_for_tunnel(
                self._args[0]
            )
            start = len(self._args) == 2  # Start requests include source IP request

            if net.ipToLong(self._args[1][:32]) == 0:
                raise Exception('Invalid from IP')

            data = {}
            if start:
                events.addEvent(
                    userService.deployed_service,
                    events.ET_TUNNEL_ACCESS,
                    username=user.pretty_name,
                    srcip=self._args[1],
                    dstip=host,
                    uniqueid=userService.unique_id,
                )
                msg = f'User {user.name} started tunnel to {host}:{port} from {self._args[1]}.'
                log.doLog(user.manager, log.INFO, msg)
                log.doLog(userService, log.INFO, msg)
                data = {'host': host, 'port': port}

            return data
        except Exception as e:
            logger.info('Ticket ignored: %s', e)
            raise AccessDenied()
