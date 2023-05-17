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
import socket
import logging
import multiprocessing
from unittest import IsolatedAsyncioTestCase, mock

from udstunnel import process_connection
from uds_tunnel import tunnel, consts

from .utils import tuntools

logger = logging.getLogger(__name__)


class TestTunnel(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Disable logging os slow tests
        logging.disable(logging.WARNING)
        return await super().asyncSetUp()

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
            logger.info(f'Testing invalid command with {bad_cmd!r}')
            async with tuntools.create_test_tunnel(callback=lambda x: None, port=7770, remote_port=54555, command_timeout=0.1) as cfg:
                logger_mock = mock.MagicMock()
                with mock.patch('uds_tunnel.tunnel.logger', logger_mock):
                    # Open connection to tunnel
                    async with tuntools.open_tunnel_client(cfg) as (reader, writer):
                        # Send data
                        writer.write(bad_cmd)
                        await writer.drain()
                        # Wait for response
                        readed = await reader.read(1024)
                        # Logger should have been called once with error
                        logger_mock.error.assert_called()

                        if len(bad_cmd) < 4:
                            # Response shout have been timeout
                            self.assertEqual(readed, consts.RESPONSE_ERROR_TIMEOUT)
                            # And logger should have been called with timeout
                            self.assertIn('TIMEOUT', logger_mock.error.call_args[0][0])
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
        # Not async test, executed on main thread without event loop
        # Pipe for testing
        own_conn, other_conn = multiprocessing.Pipe()

        # Some random data to send on each test, all invalid
        # 0 bytes will make timeout to be reached
        for i in [i for i in range(10)] + [i for i in range(100, 10000, 100)]:
            # Create a simple socket for testing
            rsock, wsock = socket.socketpair()
            # Set read timeout to 1 seconds
            rsock.settimeout(3)

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

    def test_valid_handshake(self) -> None:
        # Not async test
        # Pipe for testing
        own_conn, other_conn = multiprocessing.Pipe()

        # Create a simple socket for testing
        rsock, wsock = socket.socketpair()
        # Set read timeout to 1 seconds
        rsock.settimeout(3)

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

