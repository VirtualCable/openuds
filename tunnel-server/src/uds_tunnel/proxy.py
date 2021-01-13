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

logger = logging.getLogger(__name__)

class Proxy:
    cfg: config.ConfigurationType
    stat: stats.Stats

    def __init__(self, cfg: config.ConfigurationType) -> None:
        self.cfg = cfg
        self.stat = stats.Stats()

    @staticmethod
    def getFromUds(cfg: config.ConfigurationType, ticket: bytes) -> typing.MutableMapping[str, typing.Any]:
        # Sanity checks
        if len(ticket) != consts.TICKET_LENGTH:
            raise Exception(f'TICKET INVALID (len={len(ticket)})')

        for n, i in enumerate(ticket.decode(errors='ignore')):
            if (i >= 'a' and i <= 'z') or (i >= '0' and i <= '9') or (i >= 'A' and i <= 'Z'):
                continue  # Correctus
            raise Exception(f'TICKET INVALID (char {i} at pos {n})')

        # Gets the UDS connection data
        # r = requests.get(f'{cfg.uds_server}/XXXX/ticket')
        # if not r.ok:
        #     raise Exception(f'TICKET INVALID (check {r.json})')
        return {
            'host': ['172.27.1.15', '172.27.0.10'][int(ticket[0]) - 0x30],
            'port': '3389'
        }

    @staticmethod
    async def doProxy(source, destination, counter: stats.StatsSingleCounter) -> None:
        while True:
            data = await source.recv(consts.BUFFER_SIZE)
            if not data:
                break
            await destination.sendall(data)
            counter.add(len(data))

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

        logger.info('STATS TO %s', address)

        if full:
            data = self.stat.full_as_csv()
        else:
            data = self.stat.simple_as_csv()

        async for v in data:
            await source.sendall(v.encode() + b'\n')

    # Method responsible of proxying requests
    async def __call__(self, source, address: typing.Tuple[str, int]) -> None:
        await self.proxy(source, address)

    async def proxy(self, source, address: typing.Tuple[str, int]) -> None:
        logger.info('OPEN FROM %s', address)

        try:
            # First, ensure handshake (simple handshake) and command
            data: bytes = await source.recv(len(consts.HANDSHAKE_V1))

            if data != consts.HANDSHAKE_V1:
                raise Exception()
        except Exception:
            if consts.DEBUG:
                logger.exception('HANDSHAKE')
            logger.error('HANDSHAKE from %s', address)
            await source.sendall(b'HANDSHAKE_ERROR')

            # Closes connection now
            return

        try:
            # Handshake correct, get the command (4 bytes)
            command: bytes = await source.recv(consts.COMMAND_LENGTH)
            if command == consts.COMMAND_TEST:
                await source.sendall(b'OK')
                return

            if command in (consts.COMMAND_STAT, consts.COMMAND_INFO):
                # This is an stats requests
                await self.stats(full=command==consts.COMMAND_STAT, source=source, address=address)
                return

            if command != consts.COMMAND_OPEN:
                # Invalid command
                raise Exception()

            # Now, read a TICKET_LENGTH (64) bytes string, that must be [a-zA-Z0-9]{64}
            ticket: bytes = await source.recv(consts.TICKET_LENGTH)

            # Ticket received, now process it with UDS
            try:
                result = await curio.run_in_thread(Proxy.getFromUds, self.cfg, ticket)
            except Exception as e:
                logger.error('%s', e.args[0] if e.args else e)
                raise

            print(f'Result: {result}')

            # Invalid result from UDS, not allowed to connect
            if not result:
                raise Exception()

        except Exception:
            if consts.DEBUG:
                logger.exception('COMMAND')
            logger.error('COMMAND from %s', address)
            await source.sendall(b'COMMAND_ERROR')
            return

        # Communicate source OPEN is ok
        await source.sendall(b'OK')

        # Initialize own stats counter
        counter = await self.stat.new()

        # Open remote server connection
        try:
            destination = await curio.open_connection(result['host'], int(result['port']))
            async with curio.TaskGroup(wait=any) as grp:
                await grp.spawn(Proxy.doProxy, source, destination, counter.as_sent_counter())
                await grp.spawn(Proxy.doProxy, destination, source, counter.as_recv_counter())
                logger.debug('Launched proxies')

            logger.debug('Proxies finalized: %s', grp.exceptions)

        except Exception as e:
            if consts.DEBUG:
                logger.exception('OPEN REMOTE')

            logger.error('REMOTE from %s: %s', address, e)
        finally:
            await counter.close()


        logger.info('CLOSED FROM %s', address)
        logger.info('STATS: %s', counter.as_csv())
