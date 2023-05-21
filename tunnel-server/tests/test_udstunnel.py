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
import random
import asyncio
import logging
from unittest import IsolatedAsyncioTestCase

from uds_tunnel import consts

from .utils import tuntools, tools

logger = logging.getLogger(__name__)


class TestUDSTunnelMainProc(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Disable logging os slow tests
        logging.disable(logging.WARNING)
        return await super().asyncSetUp()

    async def test_run_app_help(self) -> None:
        # Executes the app with --help
        async with tuntools.tunnel_app_runner(args=['--help']) as process:
            stdout, stderr = await process.communicate()
            self.assertEqual(process.returncode, 0, f'{stdout!r} {stderr!r}')
            self.assertEqual(stderr, b'')
            self.assertIn(b'usage: udstunnel', stdout)

    async def test_tunnel_fail_cmd(self) -> None:
        # Test on ipv4 and ipv6
        for host in ('::1', '127.0.0.1'):
            # Remote is not really important in this tests, will fail before using it
            async with tuntools.create_tunnel_proc(
                host,
                7890,  # A port not used by any other test
                '127.0.0.1',
                13579,  # A port not used by any other test
                command_timeout=0.1,
            ) as (cfg, queue):  # pylint: disable=unused-variable
                for i in range(0, 8192, 128):
                    # Set timeout to 1 seconds
                    bad_cmd = bytes(random.randint(0, 255) for _ in range(i))  # nosec:  Some garbage
                    logger.info('Testing invalid command with %s', bad_cmd)
                    # On full, we need the handshake to be done, before connecting
                    # Our "test" server will simple "eat" the handshake, but we need to do it
                    async with tuntools.open_tunnel_client(cfg) as (
                        creader,
                        cwriter,
                    ):
                        cwriter.write(bad_cmd)
                        await cwriter.drain()
                        # Read response
                        data = await creader.read(1024)
                        # if len(bad_cmd) < consts.COMMAND_LENGTH, response will be RESPONSE_ERROR_TIMEOUT
                        if len(bad_cmd) >= consts.COMMAND_LENGTH:
                            self.assertEqual(data, consts.RESPONSE_ERROR_COMMAND)
                        else:
                            self.assertEqual(data, consts.RESPONSE_ERROR_TIMEOUT)

    async def test_tunnel_test(self) -> None:
        for host in ('127.0.0.1', '::1'):
            # Remote is not really important in this tests, will return ok before using it (this is a TEST command, not OPEN)
            async with tuntools.create_tunnel_proc(
                host,
                7891,
                '127.0.0.1',
                13581,
            ) as (cfg, queue):  # pylint: disable=unused-variable
                for _ in range(10):  # Several times
                    # On full, we need the handshake to be done, before connecting
                    # Our "test" server will simple "eat" the handshake, but we need to do it
                    async with tuntools.open_tunnel_client(cfg) as (
                        creader,
                        cwriter,
                    ):
                        cwriter.write(consts.COMMAND_TEST)
                        await cwriter.drain()
                        # Read response
                        data = await creader.read(1024)
                        self.assertEqual(data, consts.RESPONSE_OK)

    async def test_tunnel_fail_open(self) -> None:
        for host in ('127.0.0.1', '::1'):
            # Remote is NOT important in this tests
            # create a remote server
            async with tools.AsyncTCPServer(host=host, port=5444) as server:
                async with tuntools.create_tunnel_proc(
                    host,
                    7775,
                    server.host,
                    server.port,
                    command_timeout=0.1,
                ) as (cfg, queue):  # pylint: disable=unused-variable
                    for i in range(
                        0, consts.TICKET_LENGTH - 1, 4
                    ):  # All will fail. Any longer will be processed, and mock will return correct don't matter the ticket
                        # Ticket must contain only letters and numbers
                        ticket = tuntools.get_correct_ticket(i)
                        # On full, we need the handshake to be done, before connecting
                        # Our "test" server will simple "eat" the handshake, but we need to do it
                        async with tuntools.open_tunnel_client(cfg) as (
                            creader,
                            cwriter,
                        ):
                            cwriter.write(consts.COMMAND_OPEN)
                            # fake ticket, consts.TICKET_LENGTH bytes long, letters and numbers. Use a random ticket,
                            cwriter.write(ticket)

                            await cwriter.drain()
                            # Read response
                            data = await creader.read(1024)
                            self.assertEqual(data, consts.RESPONSE_ERROR_TIMEOUT)

    async def test_tunnel_open(self) -> None:
        for host in ('127.0.0.1', '::1'):
            received: bytes = b''
            callback_invoked: asyncio.Event = asyncio.Event()

            def callback(data: bytes) -> None:
                nonlocal received
                received += data
                # if data contains EOS marcker ('STREAM_END'), we are done
                if b'STREAM_END' in data:
                    callback_invoked.set()  # pylint: disable=cell-var-from-loop

            # Remote is important in this tests
            # create a remote server, use a different port than the tunnel fail test, because tests may run in parallel
            async with tools.AsyncTCPServer(host=host, port=5445, callback=callback) as server:
                for tunnel_host in ('127.0.0.1', '::1'):
                    async with tuntools.create_tunnel_proc(
                        tunnel_host,
                        7778,  # Not really used here
                        server.host,
                        server.port,
                        use_fake_http_server=True,
                    ) as (cfg, queue):
                        # Ensure queue is not none but an asyncio.Queue
                        # Note, this also let's mypy know that queue is not None after this point
                        if queue is None:
                            raise AssertionError('Queue is None')

                        for _ in range(16):
                            # Create a random ticket with valid format
                            ticket = tuntools.get_correct_ticket()
                            # On full, we need the handshake to be done, before connecting
                            # Our "test" server will simple "eat" the handshake, but we need to do it
                            async with tuntools.open_tunnel_client(cfg) as (
                                creader,
                                cwriter,
                            ):
                                cwriter.write(consts.COMMAND_OPEN)
                                # fake ticket, consts.TICKET_LENGTH bytes long, letters and numbers. Use a random ticket,
                                cwriter.write(ticket)
                                await cwriter.drain()
                                # Read response, should be ok
                                data = await creader.read(1024)
                                self.assertEqual(
                                    data,
                                    consts.RESPONSE_OK,
                                    f'Tunnel host: {tunnel_host}, server host: {host}',
                                )
                                # Queue should contain a new item, extract it
                                queue_item = await queue.get()
                                # Ensure it an http request (ends with \r\n\r\n)
                                self.assertTrue(queue_item.endswith(b'\r\n\r\n'))
                                # Extract URL and ensure it contains the correct data, that is
                                # .../ticket/ip/uds_token
                                # or .../notify_token/stop/uds_token
                                if not b'stop' in queue_item:
                                    should_be_url = f'/{tunnel_host}/{cfg.uds_token}'.encode()
                                else:
                                    should_be_url = f'/stop/{cfg.uds_token}'.encode()
                                self.assertIn(should_be_url, queue_item)

                                # Ensure user agent is correct

                                # Data sent will be received by server
                                # One single write will ensure all data is on same packet
                                test_str = (
                                    b'Some Random Data'
                                    + bytes(random.randint(0, 255) for _ in range(8192))  # nosec: some random data, not used for security
                                    + b'STREAM_END'
                                )
                                # Clean received data
                                received = b''
                                # And reset event
                                callback_invoked.clear()

                                cwriter.write(test_str)
                                await cwriter.drain()

                                # Wait for callback to be invoked
                                await callback_invoked.wait()
                                self.assertEqual(received, test_str)

    async def test_tunnel_no_remote(self) -> None:
        for host in ('127.0.0.1', '::1'):
            for tunnel_host in ('127.0.0.1', '::1'):
                async with tuntools.create_tunnel_proc(
                    tunnel_host,
                    7888,
                    host,
                    17222,  # Any non used port will do the trick
                ) as (cfg, _):
                    ticket = tuntools.get_correct_ticket()
                    # On full, we need the handshake to be done, before connecting
                    # Our "test" server will simple "eat" the handshake, but we need to do it
                    async with tuntools.open_tunnel_client(cfg) as (
                        creader,
                        cwriter,
                    ):
                        cwriter.write(consts.COMMAND_OPEN)
                        # fake ticket, consts.TICKET_LENGTH bytes long, letters and numbers. Use a random ticket,
                        cwriter.write(ticket)

                        await cwriter.drain()
                        # Read response
                        data = await creader.read(1024)
                        self.assertEqual(data, b'', f'Tunnel host: {tunnel_host}, server host: {host}')

    async def test_tunnel_invalid_ssl_handshake(self) -> None:
        for tunnel_host in ('127.0.0.1', '::1'):
            async with tuntools.create_tunnel_proc(
                tunnel_host,
                7779,
                'localhost',
                17222,  # Any non used port will do the trick
            ) as (cfg, _):
                async with tuntools.open_tunnel_client(cfg, skip_ssl=True) as (
                    creader,
                    cwriter
                ):
                    cwriter.write(consts.COMMAND_OPEN)  # Will fail, not ssl connection, this is invalid in fact

                    await cwriter.drain()

                    # Read response, shoub be empty and at_eof
                    data = await creader.read(1024)

                    self.assertEqual(data, b'')
                    self.assertTrue(creader.at_eof())
