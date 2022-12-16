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
import string
import random
import aiohttp
import asyncio
import contextlib
import socket
import ssl
import logging

from unittest import IsolatedAsyncioTestCase, mock

from uds_tunnel import proxy, tunnel, consts

from . import fixtures
from .utils import tools, certs

if typing.TYPE_CHECKING:
    from uds_tunnel import config

logger = logging.getLogger(__name__)

NOTIFY_TICKET = '0123456789cdef01456789abcdebcdef0123456789abcdef'
UDS_GET_TICKET_RESPONSE = lambda host, port: {
    'host': host,
    'port': port,
    'notify': NOTIFY_TICKET,
}
CALLER_HOST = ('host', 12345)
REMOTE_HOST = ('127.0.0.1', 54876)


def uds_response(
    _,
    ticket: bytes,
    msg: str,
    queryParams: typing.Optional[typing.Mapping[str, str]] = None,
) -> typing.Dict[str, typing.Any]:
    if msg == 'stop':
        return {}

    return UDS_GET_TICKET_RESPONSE(*REMOTE_HOST)


class TestTunnel(IsolatedAsyncioTestCase):
    async def test_get_ticket_from_uds_broker(self) -> None:
        _, cfg = fixtures.get_config()
        # Test some invalid tickets
        # Valid ticket are consts.TICKET_LENGTH bytes long, and must be A-Z, a-z, 0-9
        with mock.patch(
            'uds_tunnel.tunnel.TunnelProtocol._readFromUDS',
            new_callable=tools.AsyncMock,
        ) as m:
            m.side_effect = uds_response
            for i in range(0, 100):
                ticket = ''.join(
                    random.choices(
                        string.ascii_letters + string.digits, k=i % consts.TICKET_LENGTH
                    )
                )

                with self.assertRaises(ValueError):
                    await tunnel.TunnelProtocol.getTicketFromUDS(
                        cfg, ticket.encode(), CALLER_HOST
                    )

            ticket = NOTIFY_TICKET  # Samle ticket
            for i in range(0, 100):
                # Now some requests with valid tickets
                # Ensure no exception is raised
                ret_value = await tunnel.TunnelProtocol.getTicketFromUDS(
                    cfg, ticket.encode(), CALLER_HOST
                )
                # Ensure data returned is correct {host, port, notify} from mock
                self.assertEqual(ret_value, UDS_GET_TICKET_RESPONSE(*REMOTE_HOST))
                # Ensure mock was called with correct parameters
                print(m.call_args)
                # Check calling parameters, first one is the config, second one is the ticket, third one is the caller host
                # no kwargs are used
                self.assertEqual(m.call_args[0][0], cfg)
                self.assertEqual(
                    m.call_args[0][1], NOTIFY_TICKET.encode()
                )  # Same ticket, but bytes
                self.assertEqual(m.call_args[0][2], CALLER_HOST[0])

                print(ret_value)

            # mock should have been called 100 times
            self.assertEqual(m.call_count, 100)

    async def test_notify_end_to_uds_broker(self) -> None:
        _, cfg = fixtures.get_config()
        with mock.patch(
            'uds_tunnel.tunnel.TunnelProtocol._readFromUDS',
            new_callable=tools.AsyncMock,
        ) as m:
            m.side_effect = uds_response
            counter = mock.MagicMock()
            counter.sent = 123456789
            counter.recv = 987654321

            ticket = NOTIFY_TICKET.encode()
            for i in range(0, 100):
                await tunnel.TunnelProtocol.notifyEndToUds(cfg, ticket, counter)

                self.assertEqual(m.call_args[0][0], cfg)
                self.assertEqual(
                    m.call_args[0][1], NOTIFY_TICKET.encode()
                )  # Same ticket, but bytes
                self.assertEqual(m.call_args[0][2], 'stop')
                self.assertEqual(
                    m.call_args[0][3],
                    {'sent': str(counter.sent), 'recv': str(counter.recv)},
                )

            # mock should have been called 100 times
            self.assertEqual(m.call_count, 100)

    async def test_read_from_uds_broker(self) -> None:
        # Generate a listening http server for testing UDS
        # Tesst fine responses:
        for use_ssl in (True, False):
            async with tools.AsyncHttpServer(
                port=13579, response=b'{"result":"ok"}', use_ssl=use_ssl
            ) as server:
                # Get server configuration, and ensure server is running fine
                fake_uds_server = (
                    f'http{"s" if use_ssl else ""}://127.0.0.1:{server.port}/'
                )
                _, cfg = fixtures.get_config(
                    uds_server=fake_uds_server,
                    uds_verify_ssl=False,
                    listen_protocol='http',
                )
                self.assertEqual(
                    await TestTunnel.get(fake_uds_server),
                    '{"result":"ok"}',
                )
                # Now, tests _readFromUDS
                for i in range(100):
                    ret = await tunnel.TunnelProtocol._readFromUDS(
                        cfg, NOTIFY_TICKET.encode(), 'test', {'param': 'value'}
                    )
                    self.assertEqual(ret, {'result': 'ok'})

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
                # Open connection to tunnel
                async with TestTunnel.open_tunnel(cfg) as (reader, writer):
                    # Send data
                    writer.write(bad_cmd)
                    await writer.drain()
                    # Wait for response
                    readed = await reader.read(1024)
                    # Should return consts.ERROR_COMMAND or consts.ERROR_TIMEOUT
                    if len(bad_cmd) < 4:
                        self.assertEqual(readed, consts.RESPONSE_ERROR_TIMEOUT)
                    else:
                        self.assertEqual(readed, consts.RESPONSE_ERROR_COMMAND)

    # Helpers
    @staticmethod
    async def get(url: str) -> str:
        async with aiohttp.ClientSession() as session:
            options = {
                'ssl': False,
            }
            async with session.get(url, **options) as r:
                r.raise_for_status()
                return await r.text()

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
            family=socket.AF_INET6 if cfg.listen_ipv6 or ':' in cfg.listen_address else socket.AF_INET,
        )

    @staticmethod
    @contextlib.asynccontextmanager
    async def create_test_tunnel(callback: typing.Callable[[bytes], None]) -> typing.AsyncGenerator['config.ConfigurationType', None]:
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
                    m.return_value = UDS_GET_TICKET_RESPONSE(server.host, server.port)

                    tunnel_server = await TestTunnel.create_tunnel_server(cfg, ssl_ctx)
                    yield cfg
                    tunnel_server.close()
                    await tunnel_server.wait_closed()

    @staticmethod
    @contextlib.asynccontextmanager
    async def open_tunnel(
        cfg: 'config.ConfigurationType',
    ) -> typing.AsyncGenerator[typing.Tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """ opens an ssl socket to the tunnel server
        """
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

