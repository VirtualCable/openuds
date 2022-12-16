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
import random
import asyncio
import contextlib
import socket
import ssl
import logging
import multiprocessing
from unittest import IsolatedAsyncioTestCase, mock

from udstunnel import process_connection
from uds_tunnel import tunnel, consts

from . import fixtures
from .utils import tools, certs, conf

if typing.TYPE_CHECKING:
    from uds_tunnel import config

logger = logging.getLogger(__name__)


class TestTunnel(IsolatedAsyncioTestCase):
    async def test_tunnel_invalid_command(self) -> None:
        # Test invalid handshake
        # data = b''
        # future: asyncio.Future = asyncio.Future()

        # def callback(ldata: bytes) -> None:
        #     nonlocal data
        #     data += ldata
        #     future.set_result(True)

        # Send invalid commands and see what happens
        # Commands are 4 bytes length, try with less and more invalid commands
        for i in range(0, 100, 10):
            # Set timeout to 1 seconds
            bad_cmd = bytes(random.randint(0, 255) for _ in range(i))  # Some garbage
            consts.TIMEOUT_COMMAND = 0.1  # type: ignore  # timeout is a final variable, but we need to change it for testing speed
            logger.info(f'Testing invalid command with {bad_cmd!r}')
            async with TestTunnel.create_test_tunnel(lambda x: None) as cfg:
                logger_mock = mock.MagicMock()
                with mock.patch('uds_tunnel.tunnel.logger', logger_mock):
                    # Open connection to tunnel
                    async with TestTunnel.open_tunnel(cfg) as (reader, writer):
                        # Send data
                        writer.write(bad_cmd)
                        await writer.drain()
                        # Wait for response
                        readed = await reader.read(1024)
                        # Logger should have been called once with error
                        logger_mock.error.assert_called_once()
                        # last (first printed) info should have been connection info
                        self.assertIn(
                            'TERMINATED', logger_mock.info.call_args_list[-1][0][0]
                        )

                        if len(bad_cmd) < 4:
                            # Response shout have been timeout
                            self.assertEqual(readed, consts.RESPONSE_ERROR_TIMEOUT)
                            # And logger should have been called with timeout
                            self.assertIn('TIMEOUT', logger_mock.error.call_args[0][0])
                            # Logger info with connection info
                            logger_mock.info.assert_called_once()
                        else:
                            # Response shout have been command error
                            self.assertEqual(readed, consts.RESPONSE_ERROR_COMMAND)
                            # And logger should have been called with command error
                            self.assertIn('ERROR', logger_mock.error.call_args[0][0])
                            # Info should have been called with connection info and
                            self.assertIn(
                                'CONNECT FROM', logger_mock.info.call_args_list[0][0][0]
                            )  # First call to info

    def test_tunnel_invalid_handshake(self) -> None:
        # Pipe for testing
        own_conn, other_conn = multiprocessing.Pipe()

        # Some random data to send on each test, all invalid
        # 0 bytes will make timeout to be reached
        for i in [i for i in range(10)] + [i for i in range(100, 10000, 100)]:
            # Create a simple socket for testing
            rsock, wsock = socket.socketpair()
            # Set read timeout to 1 seconds
            rsock.settimeout(1)

            # Set timeout to 1 seconds
            bad_handshake = bytes(random.randint(0, 255) for _ in range(i))
            logger_mock = mock.MagicMock()
            with mock.patch('udstunnel.logger', logger_mock):
                wsock.sendall(bad_handshake)
                process_connection(rsock, ('host', 'port'), own_conn)

            # Check that logger has been called
            logger_mock.error.assert_called_once()
            # And ensure that error contains 'HANDSHAKE invalid'
            self.assertIn('HANDSHAKE invalid', logger_mock.error.call_args[0][0])
            # and host, port are the second parameter (tuple)
            self.assertEqual(logger_mock.error.call_args[0][1], ('host', 'port'))

    def test_valid_handshake(self) -> None:
        # Pipe for testing
        own_conn, other_conn = multiprocessing.Pipe()

        # Create a simple socket for testing
        rsock, wsock = socket.socketpair()
        # Set read timeout to 1 seconds
        rsock.settimeout(1)

        # Patch logger to check that it's not called
        logger_mock = mock.MagicMock()
        with mock.patch('udstunnel.logger', logger_mock):
            wsock.sendall(consts.HANDSHAKE_V1)
            process_connection(rsock, ('host', 'port'), own_conn)

        # Check that logger has not been called
        logger_mock.error.assert_not_called()
        # and that other_conn has received a ('host', 'port') tuple
        # recv()[0] will be a copy of the socket, we don't care about it
        self.assertEqual(other_conn.recv()[1], ('host', 'port'))

    @staticmethod
    async def create_tunnel_server(
        cfg: 'config.ConfigurationType', context: 'ssl.SSLContext'
    ) -> 'asyncio.Server':
        # Create fake proxy
        proxy = mock.MagicMock()
        proxy.cfg = cfg
        proxy.ns = mock.MagicMock()
        proxy.ns.current = 0
        proxy.ns.total = 0
        proxy.ns.sent = 0
        proxy.ns.recv = 0
        proxy.counter = 0

        loop = asyncio.get_running_loop()

        # Create an asyncio listen socket on cfg.listen_host:cfg.listen_port
        return await loop.create_server(
            lambda: tunnel.TunnelProtocol(proxy),
            cfg.listen_address,
            cfg.listen_port,
            ssl=context,
            family=socket.AF_INET6
            if cfg.listen_ipv6 or ':' in cfg.listen_address
            else socket.AF_INET,
        )

    @staticmethod
    @contextlib.asynccontextmanager
    async def create_test_tunnel(
        callback: typing.Callable[[bytes], None]
    ) -> typing.AsyncGenerator['config.ConfigurationType', None]:
        # Generate a listening server for testing tunnel
        # Prepare the end of the tunnel
        async with tools.AsyncTCPServer(port=54876, callback=callback) as server:
            # Create a tunnel to localhost 13579
            # SSl cert for tunnel server
            with certs.ssl_context(server.host) as (ssl_ctx, _):
                _, cfg = fixtures.get_config(
                    address=server.host,
                    port=7777,
                )
                with mock.patch(
                    'uds_tunnel.tunnel.TunnelProtocol._readFromUDS',
                    new_callable=tools.AsyncMock,
                ) as m:
                    m.return_value = conf.UDS_GET_TICKET_RESPONSE(
                        server.host, server.port
                    )

                    tunnel_server = await TestTunnel.create_tunnel_server(cfg, ssl_ctx)
                    yield cfg
                    tunnel_server.close()
                    await tunnel_server.wait_closed()

    @staticmethod
    @contextlib.asynccontextmanager
    async def open_tunnel(
        cfg: 'config.ConfigurationType',
    ) -> typing.AsyncGenerator[
        typing.Tuple[asyncio.StreamReader, asyncio.StreamWriter], None
    ]:
        """opens an ssl socket to the tunnel server"""
        if cfg.listen_ipv6 or ':' in cfg.listen_address:
            family = socket.AF_INET6
        else:
            family = socket.AF_INET
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        reader, writer = await asyncio.open_connection(
            cfg.listen_address, cfg.listen_port, ssl=context, family=family
        )
        yield reader, writer
        writer.close()
        await writer.wait_closed()
