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
import asyncio
import os
import ssl
import typing
import socket
import aiohttp
from unittest import mock

from . import certs


class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


# simple async http server, will return 200 OK with the request path as body
class AsyncHttpServer:
    host: str
    port: int
    _server: typing.Optional[asyncio.AbstractServer]
    _response: typing.Optional[bytes]
    _ssl_ctx: typing.Optional[ssl.SSLContext]
    _ssl_cert_file: typing.Optional[str]

    def __init__(
        self,
        port: int,
        *,
        response: typing.Optional[bytes] = None,
        use_ssl: bool = False,
        host: str = '127.0.0.1',  # ip
    ) -> None:
        self.host = host
        self.port = port
        self._server = None
        self._response = response
        if use_ssl:
            self._ssl_ctx, self._ssl_cert_file, pwd = certs.sslContext(host)
        else:
            self._ssl_ctx = None
            self._ssl_cert_file = None

    # on end, remove certs
    def __del__(self) -> None:
        if self._ssl_cert_file:
            os.unlink(self._ssl_cert_file)

    async def _handle(self, reader, writer) -> None:
        data = await reader.read(2048)
        path: bytes = data.split()[1]
        if self._response is not None:
            path = self._response
        writer.write(
            b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s'
            % (len(path), path)
        )
        await writer.drain()

    async def __aenter__(self) -> 'AsyncHttpServer':
        if self._ssl_ctx is not None:
            family = socket.AF_INET6 if ':' in self.host else socket.AF_INET
            self._server = await asyncio.start_server(
                self._handle, self.host, self.port, ssl=self._ssl_ctx, family=family
            )
        else:
            self._server = await asyncio.start_server(
                self._handle, self.host, self.port
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


class AsyncTCPServer:
    host: str
    port: int
    _server: typing.Optional[asyncio.AbstractServer]
    _response: typing.Optional[bytes]
    _callback: typing.Optional[typing.Callable[[bytes], None]]

    def __init__(
        self,
        port: int,
        *,
        response: typing.Optional[bytes] = None,
        host: str = '127.0.0.1',  # ip
        callback: typing.Optional[typing.Callable[[bytes], None]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self._server = None
        self._response = response
        self._callback = callback

        self.data = b''

    async def _handle(self, reader, writer) -> None:
        while True:
            data = await reader.read(2048)
            if not data:
                break

            if self._callback:
                self._callback(data)

            if self._response is not None:
                data = self._response
                writer.write(data)
                await writer.drain()

    async def __aenter__(self) -> 'AsyncTCPServer':
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


async def get(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        options = {
            'ssl': False,
        }
        async with session.get(url, **options) as r:
            r.raise_for_status()
            return await r.text()
