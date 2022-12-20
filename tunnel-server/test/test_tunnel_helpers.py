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
import logging

from unittest import IsolatedAsyncioTestCase, mock

from uds_tunnel import tunnel, consts

from .utils import fixtures
from .utils import tools, conf

logger = logging.getLogger(__name__)

def uds_response(
    _,
    ticket: bytes,
    msg: str,
    queryParams: typing.Optional[typing.Mapping[str, str]] = None,
) -> typing.Dict[str, typing.Any]:
    if msg == 'stop':
        return {}

    return conf.UDS_GET_TICKET_RESPONSE(*conf.REMOTE_HOST)


class TestTunnelHelpers(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Disable logging os slow tests
        logging.disable(logging.WARNING)
        return await super().asyncSetUp()

    async def test_get_ticket_from_uds_broker(self) -> None:
        _, cfg = fixtures.get_config()
        # Test some invalid tickets
        # Valid ticket are consts.TICKET_LENGTH bytes long, and must be A-Z, a-z, 0-9
        with mock.patch(
            'uds_tunnel.tunnel.TunnelProtocol._read_from_uds',
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
                    await tunnel.TunnelProtocol.get_ticket_from_uds(
                        cfg, ticket.encode(), conf.CALLER_HOST
                    )

            ticket = conf.NOTIFY_TICKET  # Samle ticket
            for i in range(0, 100):
                # Now some requests with valid tickets
                # Ensure no exception is raised
                ret_value = await tunnel.TunnelProtocol.get_ticket_from_uds(
                    cfg, ticket.encode(), conf.CALLER_HOST
                )
                # Ensure data returned is correct {host, port, notify} from mock
                self.assertEqual(ret_value, conf.UDS_GET_TICKET_RESPONSE(*conf.REMOTE_HOST))
                # Ensure mock was called with correct parameters
                print(m.call_args)
                # Check calling parameters, first one is the config, second one is the ticket, third one is the caller host
                # no kwargs are used
                self.assertEqual(m.call_args[0][0], cfg)
                self.assertEqual(
                    m.call_args[0][1], conf.NOTIFY_TICKET.encode()
                )  # Same ticket, but bytes
                self.assertEqual(m.call_args[0][2], conf.CALLER_HOST[0])

                print(ret_value)

            # mock should have been called 100 times
            self.assertEqual(m.call_count, 100)

    async def test_notify_end_to_uds_broker(self) -> None:
        _, cfg = fixtures.get_config()
        with mock.patch(
            'uds_tunnel.tunnel.TunnelProtocol._read_from_uds',
            new_callable=tools.AsyncMock,
        ) as m:
            m.side_effect = uds_response
            counter = mock.MagicMock()
            counter.sent = 123456789
            counter.recv = 987654321

            ticket = conf.NOTIFY_TICKET.encode()
            for i in range(0, 100):
                await tunnel.TunnelProtocol.notify_end_to_uds(cfg, ticket, counter)

                self.assertEqual(m.call_args[0][0], cfg)
                self.assertEqual(
                    m.call_args[0][1], conf.NOTIFY_TICKET.encode()
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
            for host in ('127.0.0.1', '::1'):
                logger.info('Testing with use_ssl=%s, host=%s', use_ssl, host)
                async with tools.AsyncHttpServer(
                    port=13579, response=b'{"result":"ok"}', use_ssl=use_ssl, host=host
                ) as server:
                    # Get server configuration, and ensure server is running fine
                    if host == '::1':
                        l, r = '[', ']'
                    else:
                        l, r = '', ''
                    fake_uds_server = (
                        f'http{"s" if use_ssl else ""}://{l}{host}{r}:{server.port}/'          
                    )
                    _, cfg = fixtures.get_config(
                        uds_server=fake_uds_server,
                        uds_verify_ssl=False,
                        listen_protocol='http',
                    )
                    self.assertEqual(
                        await tools.get(fake_uds_server),
                        '{"result":"ok"}',
                    )
                    # Now, tests _read_from_uds
                    for i in range(100):
                        ret = await tunnel.TunnelProtocol._read_from_uds(
                            cfg, conf.NOTIFY_TICKET.encode(), 'test', {'param': 'value'}
                        )
                        self.assertEqual(ret, {'result': 'ok'})

