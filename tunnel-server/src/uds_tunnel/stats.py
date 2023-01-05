# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import multiprocessing
import socket
import time
import logging
import typing
import io
import asyncio
import ssl
import logging
import typing


from . import config
from . import consts


if typing.TYPE_CHECKING:
    from multiprocessing.managers import Namespace, SyncManager

INTERVAL = 2  # Interval in seconds between stats update

logger = logging.getLogger(__name__)

class StatsSingleCounter:
    def __init__(self, parent: 'StatsManager', for_receiving=True) -> None:
        if for_receiving:
            self.adder = parent.add_recv
        else:
            self.adder = parent.add_sent

    def add(self, value: int):
        self.adder(value)
        return self


class StatsManager:
    ns: 'Namespace'
    last_sent: int
    sent: int
    last_recv: int
    recv: int
    last: float
    start: float  # timestamp
    end: float    

    def __init__(self, ns: 'Namespace'):
        self.ns = ns
        self.ns.current += 1
        self.ns.total += 1
        self.sent = self.last_sent = 0
        self.recv = self.last_recv = 0
        self.last = time.monotonic()
        self.start = time.monotonic()
        self.end = self.start

    def update(self, force: bool = False):
        now = time.monotonic()
        if force or now - self.last > INTERVAL:
            self.last = now
            self.ns.recv += self.recv - self.last_recv
            self.ns.sent += self.sent - self.last_sent
            self.last_sent = self.sent
            self.last_recv = self.recv

    def add_recv(self, size: int) -> None:
        self.recv += size
        self.update()

    def add_sent(self, size: int) -> None:
        self.sent += size
        self.update()

    @property
    def as_sent_counter(self) -> 'StatsSingleCounter':
        return StatsSingleCounter(self, False)

    @property
    def as_recv_counter(self) -> 'StatsSingleCounter':
        return StatsSingleCounter(self, True)

    def close(self):
        self.update(True)
        self.ns.current -= 1
        self.end = time.monotonic()

# Stats collector thread
class GlobalStats:
    manager: 'SyncManager'
    ns: 'Namespace'
    counter: int

    def __init__(self):
        super().__init__()
        self.manager = multiprocessing.Manager()
        self.ns = self.manager.Namespace()

        # Counters
        self.ns.current = 0
        self.ns.total = 0
        self.ns.sent = 0
        self.ns.recv = 0
        self.counter = 0

    def info(self) -> typing.Iterable[str]:
        return GlobalStats.get_stats(self.ns)

    @staticmethod
    def get_stats(ns: 'Namespace') -> typing.Iterable[str]:
        yield ';'.join([str(ns.current), str(ns.total), str(ns.sent), str(ns.recv)])

# Stats processor, invoked from command line
async def getServerStats(detailed: bool = False) -> None:
    cfg = config.read()

    # Context for local connection (ignores cert hostname)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # For ServerStats, does not checks certificate

    try:
        host = cfg.listen_address if cfg.listen_address != '0.0.0.0' else 'localhost'
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, cfg.listen_port))
            # Send HANDSHAKE
            sock.sendall(consts.HANDSHAKE_V1)
            # Ugrade connection to TLS
            reader, writer = await asyncio.open_connection(sock=sock, ssl=context, server_hostname=host)

            tmpdata = io.BytesIO()
            cmd = consts.COMMAND_STAT if detailed else consts.COMMAND_INFO
            
            writer.write(cmd + cfg.secret.encode())           
            await writer.drain()

            while True:
                chunk = await reader.read(consts.BUFFER_SIZE)
                if not chunk:
                    break
                tmpdata.write(chunk)

        # Now we can output chunk data
        print(tmpdata.getvalue().decode())
    except Exception as e:
        print(e)
        return
