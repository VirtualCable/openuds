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
import typing
import asyncio
import random
import logging
from unittest import IsolatedAsyncioTestCase, mock

from uds_tunnel import consts, stats

from .utils import tuntools, tools, conf

if typing.TYPE_CHECKING:
    from uds_tunnel import config

logger = logging.getLogger(__name__)

class TestUDSTunnelApp(IsolatedAsyncioTestCase):
    async def client_task(self, host: str, tunnel_port: int, remote_port: int) -> None:
        received: bytes = b''
        callback_invoked: asyncio.Event = asyncio.Event()
        # Data sent will be received by server
        # One single write will ensure all data is on same packet
        test_str = (
            b'Some Random Data'
            + bytes(random.randint(0, 255) for _ in range(1024)) * 4
            + b'STREAM_END'
        )  # length = 16 + 1024 * 4 + 10 = 4122
        test_response = (
            bytes(random.randint(48, 127) for _ in range(12))
        )  # length = 12, random printable chars

        def callback(data: bytes) -> typing.Optional[bytes]:
            nonlocal received
            received += data
            # if data contains EOS marcker ('STREAM_END'), we are done
            if b'STREAM_END' in data:
                callback_invoked.set()
                return test_response
            return None

        async with tools.AsyncTCPServer(
            host=host, port=remote_port, callback=callback, name='client_task'
        ) as server:
            # Create a random ticket with valid format
            ticket = tuntools.get_correct_ticket(prefix=f'bX0bwmb{remote_port}bX0bwmb')
            # Open and send handshake
            # Fake config, only needed data for open_tunnel_client
            cfg = mock.MagicMock()
            cfg.ipv6 = ':' in host
            cfg.listen_address = host
            cfg.listen_port = tunnel_port

            async with tuntools.open_tunnel_client(
                cfg, local_port=remote_port + 10000, use_tunnel_handshake=True
            ) as (
                creader,
                cwriter,
            ):
                # Now open command with ticket
                cwriter.write(consts.COMMAND_OPEN)
                # fake ticket, consts.TICKET_LENGTH bytes long, letters and numbers. Use a random ticket,
                cwriter.write(ticket)

                await cwriter.drain()
                # Read response, should be ok
                data = await creader.read(1024)
                logger.debug('Received response: %r', data)
                self.assertEqual(
                    data,
                    consts.RESPONSE_OK,
                    f'Server host: {host}:{tunnel_port} - Ticket: {ticket!r} - Response: {data!r}',
                )
                # Clean received data
                received = b''
                # And reset event
                callback_invoked.clear()

                cwriter.write(test_str)
                await cwriter.drain()

                # Read response, should be just FAKE_OK_RESPONSE
                data = await creader.read(1024)
                logger.debug('Received response: %r', data)
                self.assertEqual(
                    data,
                    test_response,
                    f'Server host: {host}:{tunnel_port} - Ticket: {ticket!r} - Response: {data!r}',
                )
                # Close connection
                cwriter.close()

                # Wait for callback to be invoked
                await callback_invoked.wait()
                self.assertEqual(received, test_str)

    async def test_app_concurrency(self) -> None:
        concurrent_tasks = 512
        fake_broker_port = 20000
        tunnel_server_port = fake_broker_port + 1
        remote_port = fake_broker_port + 2
        # Extracts the port from an string that has bX0bwmbPORTbX0bwmb in it
        def extract_port(data: bytes) -> int:
            if b'bX0bwmb' not in data:
                return 12345  # No port, wil not be used because is an "stop" request
            return int(data.split(b'bX0bwmb')[1])

        for host in ('127.0.0.1', '::1'):
            if ':' in host:
                url = f'http://[{host}]:{fake_broker_port}/uds/rest'
            else:
                url = f'http://{host}:{fake_broker_port}/uds/rest'
            # Create fake uds broker
            async with tuntools.create_fake_broker_server(
                host,
                fake_broker_port,
                response=lambda data: conf.UDS_GET_TICKET_RESPONSE(
                    host, extract_port(data)
                ),
            ) as req_queue:
                if req_queue is None:
                    raise AssertionError('req_queue is None')

                async with tuntools.tunnel_app_runner(
                    host,
                    tunnel_server_port,
                    wait_for_port=True,
                    # Tunnel config
                    uds_server=url,
                    logfile='/tmp/tunnel_test.log',
                    loglevel='DEBUG',
                    workers=4,
                    command_timeout=16,  # Increase command timeout because heavy load we will create
                ) as process:

                    # Create a "bunch" of clients
                    tasks = [
                        asyncio.create_task(
                            self.client_task(host, tunnel_server_port, remote_port + i)
                        )
                        async for i in tools.waitable_range(concurrent_tasks)
                    ]

                    # Wait for all tasks to finish
                    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

                    # If any exception was raised, raise it
                    for task in tasks:
                        task.result()
                # Queue should have all requests (concurrent_tasks*2, one for open and one for close)
                self.assertEqual(req_queue.qsize(), concurrent_tasks * 2)

    async def test_tunnel_proc_concurrency(self) -> None:
        concurrent_tasks = 512
        fake_broker_port = 20000
        tunnel_server_port = fake_broker_port + 1
        remote_port = fake_broker_port + 2
        # Extracts the port from an string that has bX0bwmbPORTbX0bwmb in it

        req_queue: asyncio.Queue[bytes] = asyncio.Queue()

        def extract_port(data: bytes) -> int:
            logger.debug('Data: %r', data)
            req_queue.put_nowait(data)
            if b'bX0bwmb' not in data:
                return 12345  # No port, wil not be used because is an "stop" request
            return int(data.split(b'bX0bwmb')[1])

        for host in ('127.0.0.1', '::1'):
            if ':' in host:
                url = f'http://[{host}]:{fake_broker_port}/uds/rest'
            else:
                url = f'http://{host}:{fake_broker_port}/uds/rest'

            req_queue = asyncio.Queue()  # clear queue
            # Use tunnel proc for testing
            stats_collector = stats.GlobalStats()
            async with tuntools.create_tunnel_proc(
                host,
                tunnel_server_port,
                response=lambda data: conf.UDS_GET_TICKET_RESPONSE(
                    host, extract_port(data)
                ),
                command_timeout=16,  # Increase command timeout because heavy load we will create,
                global_stats=stats_collector,
            ) as (cfg, _):
                # Create a "bunch" of clients
                tasks = [
                    asyncio.create_task(
                        self.client_task(host, tunnel_server_port, remote_port + i)
                    )
                    async for i in tools.waitable_range(concurrent_tasks)
                ]

                # Wait for tasks to finish and check for exceptions
                await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

                # If any exception was raised, raise it
                await asyncio.gather(*tasks, return_exceptions=True)

                # Queue should have all requests (concurrent_tasks*2, one for open and one for close)
                self.assertEqual(req_queue.qsize(), concurrent_tasks * 2)
                
            # Check stats
            self.assertEqual(stats_collector.ns.recv, concurrent_tasks*12)
            self.assertEqual(stats_collector.ns.sent, concurrent_tasks*4122)
            self.assertEqual(stats_collector.ns.total, concurrent_tasks)
