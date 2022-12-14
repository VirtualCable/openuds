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
import tempfile
from unittest import mock

from . import certs

class AsyncMock(mock.MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


# simple async http server, will return 200 OK with the request path as body
class AsyncHttpServer:
    port: int
    _server: typing.Optional[asyncio.AbstractServer]
    _response: typing.Optional[bytes]
    _ssl_ctx: typing.Optional[ssl.SSLContext]

    def __init__(
        self, port: int, *, response: typing.Optional[bytes] = None, use_ssl: bool = False, 
        host: str = '127.0.0.1'  # ip
    ):
        self.port = port
        self._server = None
        self._response = response
        if use_ssl:
            # First, create server cert and key on temp dir
            tmpdir = tempfile.gettempdir()
            cert, key, password = certs.selfSignedCert('127.0.0.1')
            with open(f'{tmpdir}/tmp_cert.pem', 'w') as f:
                f.write(key)
                f.write(cert)
            # Create SSL context
            self._ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self._ssl_ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
            self._ssl_ctx.load_cert_chain(certfile=f'{tmpdir}/tmp_cert.pem', password=password)
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.set_ciphers(
                'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384'
            )
        else:
            self._ssl_ctx = None

    # on end, remove certs
    def __del__(self):
        tmpdir = tempfile.gettempdir()
        # os.remove(f'{tmpdir}/tmp_cert.pem')

    async def _handle(self, reader, writer):
        data = await reader.read(2048)
        path: bytes = data.split()[1]
        if self._response is not None:
            path = self._response
        writer.write(
            b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s'
            % (len(path), path)
        )
        await writer.drain()

    async def __aenter__(self):
        if self._ssl_ctx is not None:
            self._server = await asyncio.start_server(
                self._handle, '127.0.0.1', self.port, ssl=self._ssl_ctx
            )
        else:
            self._server = await asyncio.start_server(
                self._handle, '127.0.0.1', self.port
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

