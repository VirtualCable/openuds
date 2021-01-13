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
import time
import io
import ssl
import logging
import typing

import curio
import blist

from . import config
from . import consts


logger = logging.getLogger(__name__)

# Locker for id assigner
assignLock = curio.Lock()

# Tuple index for several stats
SENT, RECV = 0, 1

# Subclasses for += operation to work
class StatsSingleCounter:
    def __init__(self, parent: 'StatsConnection', for_receiving=True) -> None:
        if for_receiving:
            self.adder = parent.add_recv
        else:
            self.adder = parent.add_sent

    def add(self, value: int):
        self.adder(value)
        return self


class StatsConnection:
    id: int
    recv: int
    sent: int
    start_time: int
    parent: 'Stats'

    # Bandwidth stats (SENT, RECV)
    last: typing.List[int]
    last_time: typing.List[float]

    bandwidth: typing.List[int]
    max_bandwidth: typing.List[int]

    def __init__(self, parent: 'Stats', id: int) -> None:
        self.id = id
        self.recv = self.sent = 0

        now = time.time()
        self.start_time = int(now)
        self.parent = parent

        self.last = [0, 0]
        self.last_time = [now, now]
        self.bandwidth = [0, 0]
        self.max_bandwidth = [0, 0]

    def update_bandwidth(self, kind: int, counter: int):
        now = time.time()
        elapsed = now - self.last_time[kind]
        # Update only when enouth data
        if elapsed < consts.BANDWIDTH_TIME:
            return
        total = counter - self.last[kind]
        self.bandwidth[kind] = int(float(total) / elapsed)
        self.last[kind] = counter
        self.last_time[kind] = now

        if self.bandwidth[kind] > self.max_bandwidth[kind]:
            self.max_bandwidth[kind] = self.bandwidth[kind]

    def add_recv(self, size: int) -> None:
        self.recv += size
        self.update_bandwidth(RECV, counter=self.recv)
        self.parent.add_recv(size)

    def add_sent(self, size: int) -> None:
        self.sent += size
        self.update_bandwidth(SENT, counter=self.sent)
        self.parent.add_sent(size)

    def as_sent_counter(self) -> 'StatsSingleCounter':
        return StatsSingleCounter(self, False)

    def as_recv_counter(self) -> 'StatsSingleCounter':
        return StatsSingleCounter(self, True)

    async def close(self) -> None:
        if self.id:
            logger.debug(f'STAT {self.id} closed')
            await self.parent.remove(self.id)
            self.id = 0

    def as_csv(self, separator: typing.Optional[str] = None) -> str:
        separator = separator or ';'
        # With connections of less than a second, consider them as a second
        elapsed = (int(time.time()) - self.start_time)

        return separator.join(
            str(i)
            for i in (
                self.id,
                self.start_time,
                elapsed,
                self.sent,
                self.bandwidth[SENT],
                self.max_bandwidth[SENT],
                self.recv,
                self.bandwidth[RECV],
                self.max_bandwidth[RECV],
            )
        )

    def __str__(self) -> str:
        return f'{self.id} t:{int(time.time())-self.start_time}, r:{self.recv}, s:{self.sent}>'

    # For sorted array
    def __lt__(self, other) -> bool:
        if isinstance(other, int):
            return self.id < other

        if not isinstance(other, StatsConnection):
            raise NotImplemented

        return self.id < other.id

    def __eq__(self, other) -> bool:
        if isinstance(other, int):
            return self.id == other

        if not isinstance(other, StatsConnection):
            raise NotImplemented

        return self.id == other.id


class Stats:
    counter_id: int

    total_sent: int
    total_received: int
    current_connections: blist.sortedlist

    def __init__(self) -> None:
        # First connection will be 1
        self.counter_id = 0
        self.total_sent = self.total_received = 0
        self.current_connections = blist.sortedlist()

    async def new(self) -> StatsConnection:
        """Initializes a connection stats counter and returns it id

        Returns:
            str: connection id
        """
        async with assignLock:
            self.counter_id += 1
            connection = StatsConnection(self, self.counter_id)
            self.current_connections.add(connection)
            return connection

    def add_sent(self, size: int) -> None:
        self.total_sent += size

    def add_recv(self, size: int) -> None:
        self.total_received += size

    async def remove(self, connection_id: int) -> None:
        async with assignLock:
            try:
                self.current_connections.remove(connection_id)
            except Exception:
                logger.debug(
                    'Tried to remove %s from connections but was not present',
                    connection_id,
                )
                # Does not exists, ignore it
                pass

    async def simple_as_csv(self, separator: typing.Optional[str] = None) -> typing.AsyncIterable[str]:
        separator = separator or ';'
        yield separator.join(
            str(i)
            for i in (
                self.counter_id,
                self.total_sent,
                self.total_received,
                len(self.current_connections),
            )
        )

    async def full_as_csv(self, separator: typing.Optional[str] = None) -> typing.AsyncIterable[str]:
        for i in self.current_connections:
            yield i.as_csv(separator)


# Stats processor, invoked from command line
async def getServerStats(detailed: bool = False) -> None:
    cfg = config.read()

    # Context for local connection (ignores cert hostname)
    context = ssl.create_default_context()
    context.check_hostname = False

    try:
        host = cfg.listen_address if cfg.listen_address != '0.0.0.0' else 'localhost'
        sock = await curio.open_connection(
            host, cfg.listen_port, ssl=context, server_hostname='localhost'
        )
        tmpdata = io.BytesIO()
        cmd = consts.COMMAND_STAT if detailed else consts.COMMAND_INFO
        async with sock:
            await sock.sendall(consts.HANDSHAKE_V1 + cmd + cfg.secret.encode())
            while True:
                chunk = await sock.recv(consts.BUFFER_SIZE)
                if not chunk:
                    break
                tmpdata.write(chunk)

        # Now we can output chunk data
        print(tmpdata.getvalue().decode())
    except Exception as e:
        print(e)
        return
