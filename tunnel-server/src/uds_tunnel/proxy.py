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
import logging
import typing

import curio
import requests

from . import config
from . import stats
from . import consts

if typing.TYPE_CHECKING:
    from multiprocessing.managers import Namespace
    import curio.io

logger = logging.getLogger(__name__)


class Proxy:
    cfg: config.ConfigurationType
    ns: 'Namespace'

    def __init__(self, cfg: config.ConfigurationType, ns: 'Namespace') -> None:
        self.cfg = cfg
        self.ns = ns

    @staticmethod
    def _getUdsUrl(
        cfg: config.ConfigurationType,
        ticket: bytes,
        msg: str,
        queryParams: typing.Optional[typing.Mapping[str, str]] = None,
    ) -> typing.MutableMapping[str, typing.Any]:
        try:
            url = (
                cfg.uds_server + '/' + ticket.decode() + '/' + msg + '/' + cfg.uds_token
            )
            if queryParams:
                url += '?' + '&'.join(
                    [f'{key}={value}' for key, value in queryParams.items()]
                )
            r = requests.get(
                url,
                headers={
                    'content-type': 'application/json',
                    'User-Agent': f'UDSTunnel/{consts.VERSION}',
                },
            )
            if not r.ok:
                raise Exception(r.content or 'Invalid Ticket (timed out)')

            return r.json()
        except Exception as e:
            raise Exception(f'TICKET COMMS ERROR: {ticket.decode()} {msg} {e!s}')

    @staticmethod
    def getFromUds(
        cfg: config.ConfigurationType, ticket: bytes, address: typing.Tuple[str, int]
    ) -> typing.MutableMapping[str, typing.Any]:
        # Sanity checks
        if len(ticket) != consts.TICKET_LENGTH:
            raise Exception(f'TICKET INVALID (len={len(ticket)})')

        for n, i in enumerate(ticket.decode(errors='ignore')):
            if (
                (i >= 'a' and i <= 'z')
                or (i >= '0' and i <= '9')
                or (i >= 'A' and i <= 'Z')
            ):
                continue  # Correctus
            raise Exception(f'TICKET INVALID (char {i} at pos {n})')

        return Proxy._getUdsUrl(cfg, ticket, address[0])

    @staticmethod
    def notifyEndToUds(
        cfg: config.ConfigurationType, ticket: bytes, counter: stats.Stats
    ) -> None:
        Proxy._getUdsUrl(
            cfg, ticket, 'stop', {'sent': str(counter.sent), 'recv': str(counter.recv)}
        )  # Ignore results

    @staticmethod
    async def doProxy(
        source: 'curio.io.Socket',
        destination: 'curio.io.Socket',
        counter: stats.StatsSingleCounter,
    ) -> None:
        try:
            while True:
                data = await source.recv(consts.BUFFER_SIZE)
                if not data:
                    break
                await destination.sendall(data)
                counter.add(len(data))
        except Exception:
            # Connection broken, same result as closed for us
            # We must notice that i'ts easy that when closing one part of the tunnel,
            # the other can break (due to some internal data), that's why even log is removed
            # logger.info('CONNECTION LOST FROM %s to %s', source.getsockname(), destination.getpeername())
            pass

    # Method responsible of proxying requests
    async def __call__(self, source, address: typing.Tuple[str, int]) -> None:
        try:
            await self.proxy(source, address)
        except Exception as e:
            logger.exception('Error procesing connection from %s: %s', address, e)

    async def stats(self, full: bool, source, address: typing.Tuple[str, int]) -> None:
        # Check valid source ip
        if address[0] not in self.cfg.allow:
            # Invalid source
            await source.sendall(b'FORBIDDEN')
            return

        # Check password
        passwd = await source.recv(consts.PASSWORD_LENGTH)
        if passwd.decode(errors='ignore') != self.cfg.secret:
            # Invalid password
            await source.sendall(b'FORBIDDEN')
            return

        data = stats.GlobalStats.get_stats(self.ns)

        for v in data:
            logger.debug('SENDING %s', v)
            await source.sendall(v.encode() + b'\n')

    async def proxy(self, source, address: typing.Tuple[str, int]) -> None:
        prettySource = address[0]  # Get only source IP
        prettyDest = ''
        logger.info('CONNECT FROM %s', prettySource)

        # Handshake correct in this point, start SSL connection
        command: bytes = b''
        try:
            command = await source.recv(consts.COMMAND_LENGTH)
            if command == consts.COMMAND_TEST:
                logger.info('COMMAND: TEST')
                await source.sendall(b'OK')
                logger.info('TERMINATED %s', prettySource)
                return

            if command in (consts.COMMAND_STAT, consts.COMMAND_INFO):
                logger.info('COMMAND: %s', command.decode())
                # This is an stats requests
                await self.stats(
                    full=command == consts.COMMAND_STAT, source=source, address=address
                )
                logger.info('TERMINATED %s', prettySource)
                return

            if command != consts.COMMAND_OPEN:
                # Invalid command
                raise Exception(command)

            # Now, read a TICKET_LENGTH (64) bytes string, that must be [a-zA-Z0-9]{64}
            ticket: bytes = await source.recv(consts.TICKET_LENGTH)

            # Ticket received, now process it with UDS
            try:
                result = await curio.run_in_thread(
                    Proxy.getFromUds, self.cfg, ticket, address
                )
            except Exception as e:
                logger.error('ERROR %s', e.args[0] if e.args else e)
                try:
                    await source.sendall(b'ERROR_TICKET')
                except Exception:
                    pass  # Ignore errors
                return

            prettyDest = f"{result['host']}:{result['port']}"
            logger.info('OPEN TUNNEL FROM %s to %s', prettySource, prettyDest)

        except Exception:
            logger.error('ERROR from %s: COMMAND %s', prettySource, command)
            try:
                await source.sendall(b'ERROR_COMMAND')
            except Exception:
                pass  # Ignore errors
            return


        # Initialize own stats counter
        counter = stats.Stats(self.ns)

        try:
            # Communicate source OPEN is ok
            await source.sendall(b'OK')

            # Open remote server connection
            destination = await curio.open_connection(
                result['host'], int(result['port'])
            )
            async with curio.TaskGroup(wait=any) as grp:
                await grp.spawn(
                    Proxy.doProxy, source, destination, counter.as_sent_counter()
                )
                await grp.spawn(
                    Proxy.doProxy, destination, source, counter.as_recv_counter()
                )
                logger.debug('PROXIES READY')

            logger.debug('Proxies finalized: %s', grp.exceptions)
            await curio.run_in_thread(
                Proxy.notifyEndToUds, self.cfg, result['notify'].encode(), counter
            )

        except Exception as e:
            if consts.DEBUG:
                logger.exception('OPEN REMOTE')

            logger.error('REMOTE from %s: %s', address, e)
        finally:
            counter.close()  # So we ensure stats are correctly updated on ns

        logger.info(
            'TERMINATED %s to %s, s:%s, r:%s, t:%s',
            prettySource,
            prettyDest,
            counter.sent,
            counter.recv,
            int(counter.end - counter.start),
        )
