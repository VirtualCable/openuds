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
import io
import socket
import ssl
import logging
import multiprocessing
import tempfile
import threading
from unittest import IsolatedAsyncioTestCase, mock

from uds_tunnel import tunnel, consts
import udstunnel


from . import fixtures
from .utils import tools, certs, conf

if typing.TYPE_CHECKING:
    from uds_tunnel import config

logger = logging.getLogger(__name__)


class TestTunnel(IsolatedAsyncioTestCase):
    @staticmethod
    @contextlib.contextmanager
    def create_tunnel_thread(
        listen_host: str,
        listen_port: int,
        remote_host: str,
        remote_port: int,
        *,
        workers: int = 1
    ) -> typing.Generator[None, None, None]:
        # Create the ssl cert
        cert, key, password = certs.selfSignedCert(listen_host)
        # Create the certificate file on /tmp
        with tempfile.NamedTemporaryFile() as cert_file:
            cert_file.write(cert.encode())
            cert_file.write(key.encode())
            cert_file.flush()

            # Config file for the tunnel, ignore readed
            values, _ = fixtures.get_config(
                address=listen_host,
                port=listen_port,
                ssl_certificate=cert_file.name,
                ssl_certificate_key='',
                ssl_ciphers='',
                ssl_dhparam='',
                workers=workers,
            )
            args = mock.MagicMock()
            args.config = io.StringIO(fixtures.TEST_CONFIG.format(**values))
            args.ipv6 = ':' in listen_host

            with mock.patch(
                'uds_tunnel.tunnel.TunnelProtocol._readFromUDS',
                new_callable=tools.AsyncMock,
            ) as m:
                m.return_value = conf.UDS_GET_TICKET_RESPONSE(remote_host, remote_port)

                # Create a thread to run the tunnel, udstunnel.tunnel_main will block
                # until the tunnel is closed
                thread = threading.Thread(target=udstunnel.tunnel_main, args=(args,))
                thread.start()
                yield
                # Signal stop to thead
                udstunnel.do_stop = True

                # Wait for thread to finish
                thread.join()

    async def test_tunnel_full(self) -> None:
        with self.create_tunnel_thread(
            '127.0.0.1', 7777, '127.0.0.1', 12345, workers=1
        ):
            await asyncio.sleep(4)
