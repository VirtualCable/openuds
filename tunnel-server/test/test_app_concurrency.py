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

from uds_tunnel import consts

from .utils import tuntools, tools, conf

if typing.TYPE_CHECKING:
    from uds_tunnel import config

logger = logging.getLogger(__name__)


class TestUDSTunnelApp(IsolatedAsyncioTestCase):
    async def test_run_app_help(self) -> None:
        # Executes the app with --help
        async with tuntools.tunnel_app_runner(args=['--help']) as process:

            stdout, stderr = await process.communicate()
            self.assertEqual(process.returncode, 0, f'{stdout!r} {stderr!r}')
            self.assertEqual(stderr, b'')
            self.assertIn(b'usage: udstunnel', stdout)

    async def client_task(self, host: str, port: int) -> None:
        received: bytes = b''
        callback_invoked: asyncio.Event = asyncio.Event()

        def callback(data: bytes) -> None:
            nonlocal received
            received += data
            # if data contains EOS marcker ('STREAM_END'), we are done
            if b'STREAM_END' in data:
                callback_invoked.set()

        async with tools.AsyncTCPServer(
            host=host, port=5445, callback=callback
        ) as server:
            # Create a random ticket with valid format
            ticket = tuntools.get_correct_ticket()
            # Open and send handshake
            # Fake config, only needed data for open_tunnel_client
            cfg = mock.MagicMock()
            cfg.ipv6 = ':' in host
            cfg.listen_address = host
            cfg.listen_port = port

            async with tuntools.open_tunnel_client(cfg, use_tunnel_handshake=True) as (
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
                self.assertEqual(
                    data,
                    consts.RESPONSE_OK,
                    f'Server host: {host}:{port} - Ticket: {ticket!r} - Response: {data!r}',
                )

    async def test_run_app_serve(self) -> None:
        return
        port = random.randint(10000, 20000)
        for host in ('127.0.0.1', '::1'):
            if ':' in host:
                url = f'http://[{host}]:{port}/uds/rest'
            else:
                url = f'http://{host}:{port}/uds/rest'
            # Create fake uds broker
            async with tuntools.create_fake_broker_server(
                host, port, response=conf.UDS_GET_TICKET_RESPONSE(host, port)
            ) as broker:
                async with tuntools.tunnel_app_runner(
                    host, 7770, uds_server=url,
                    logfile='/tmp/tunnel_test.log',
                    loglevel='DEBUG',
                ) as process:
                    # Create a "bunch" of clients
                    tasks = [
                        asyncio.create_task(self.client_task(host, 7777))
                        for _ in range(1)
                    ]

                    # Wait for all tasks to finish
                    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
                    # If any exception was raised, raise it
                    for task in tasks:
                        task.result()
