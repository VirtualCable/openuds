# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Virtual Cable S.L.U.
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
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import asyncio
import socket
import logging
import typing

from . import config
from . import tunnel

if typing.TYPE_CHECKING:
    from multiprocessing.managers import Namespace
    import ssl

logger = logging.getLogger(__name__)


class Proxy:
    cfg: config.ConfigurationType
    ns: 'Namespace'

    def __init__(self, cfg: config.ConfigurationType, ns: 'Namespace') -> None:
        self.cfg = cfg
        self.ns = ns

    # Method responsible of proxying requests
    async def __call__(self, source: socket.socket, context: 'ssl.SSLContext') -> None:
        await self.proxy(source, context)

    async def proxy(self, source: socket.socket, context: 'ssl.SSLContext') -> None:

        loop = asyncio.get_event_loop()

        # Handshake correct in this point, upgrade the connection to TSL and let
        # the protocol controller do the rest
        
        # Upgrade connection to SSL, and use asyncio to handle the rest
        transport: 'asyncio.transports.Transport'
        protocol: tunnel.TunnelProtocol
        (transport, protocol) = await loop.connect_accepted_socket(  # type: ignore
            lambda: tunnel.TunnelProtocol(self), source, ssl=context
        )

        await protocol.finished
        return

        # try:
        #     command: bytes = await loop.sock_recv(source, consts.COMMAND_LENGTH)
        #     if command == consts.COMMAND_TEST:
        #         logger.info('COMMAND: TEST')
        #         await loop.sock_sendall(source, b'OK')
        #         logger.info('TERMINATED %s', prettySource)
        #         return

        #     if command in (consts.COMMAND_STAT, consts.COMMAND_INFO):
        #         logger.info('COMMAND: %s', command.decode())
        #         # This is an stats requests
        #         await self.stats(
        #             full=command == consts.COMMAND_STAT, source=source, address=address
        #         )
        #         logger.info('TERMINATED %s', prettySource)
        #         return

        #     if command != consts.COMMAND_OPEN:
        #         # Invalid command
        #         raise Exception()

        #     # Now, read a TICKET_LENGTH (64) bytes string, that must be [a-zA-Z0-9]{64}
        #     ticket: bytes = await source.recv(consts.TICKET_LENGTH)

        #     # Ticket received, now process it with UDS
        #     try:
        #         result = await curio.run_in_thread(
        #             Proxy.getFromUds, self.cfg, ticket, address
        #         )
        #     except Exception as e:
        #         logger.error('ERROR %s', e.args[0] if e.args else e)
        #         await source.sendall(b'ERROR_TICKET')
        #         return

        #     prettyDest = f"{result['host']}:{result['port']}"
        #     logger.info('OPEN TUNNEL FROM %s to %s', prettySource, prettyDest)

        # except Exception:
        #     if consts.DEBUG:
        #         logger.exception('COMMAND')
        #     logger.error('ERROR from %s', prettySource)
        #     await source.sendall(b'ERROR_COMMAND')
        #     return

        # # Communicate source OPEN is ok
        # await source.sendall(b'OK')

        # # Initialize own stats counter
        # counter = stats.Stats(self.ns)

        # # Open remote server connection
        # try:
        #     destination = await curio.open_connection(
        #         result['host'], int(result['port'])
        #     )
        #     async with curio.TaskGroup(wait=any) as grp:
        #         await grp.spawn(
        #             Proxy.doProxy, source, destination, counter.as_sent_counter()
        #         )
        #         await grp.spawn(
        #             Proxy.doProxy, destination, source, counter.as_recv_counter()
        #         )
        #         logger.debug('PROXIES READY')

        #     logger.debug('Proxies finalized: %s', grp.exceptions)
        #     await curio.run_in_thread(
        #         Proxy.notifyEndToUds, self.cfg, result['notify'].encode(), counter
        #     )

        # except Exception as e:
        #     if consts.DEBUG:
        #         logger.exception('OPEN REMOTE')

        #     logger.error('REMOTE from %s: %s', address, e)
        # finally:
        #     counter.close()  # So we ensure stats are correctly updated on ns

        # logger.info(
        #     'TERMINATED %s to %s, s:%s, r:%s, t:%s',
        #     prettySource,
        #     prettyDest,
        #     counter.sent,
        #     counter.recv,
        #     int(counter.end - counter.start),
        # )
