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
import contextlib
import json
import logging
import multiprocessing
import os
import random
import socket
import ssl
import string
import tempfile
import typing
import copy
from unittest import mock

import udstunnel
from uds_tunnel import config, consts, stats, tunnel

from . import certs, conf, fixtures, tools

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from asyncio.subprocess import Process


@contextlib.contextmanager
def create_config_file(
    listen_host: str,
    listen_port: int,
    **kwargs,
) -> typing.Generator[str, None, None]:
    cert, key, password = certs.selfSignedCert(listen_host, use_password=True)
    # Create the certificate file on /tmp
    cert_file: str = ''
    with tempfile.NamedTemporaryFile(prefix='cert-', mode='w', delete=False) as f:
        f.write(key)
        f.write(cert)
        cert_file = f.name

    # Config file for the tunnel, ignore readed

    values: typing.Dict[str, typing.Any] = copy.copy(kwargs)
    values.update(
        {
            'address': listen_host,
            'port': listen_port,
            'ipv6': ':' in listen_host,
            'loglevel': 'DEBUG',
            'ssl_certificate': cert_file,
            'ssl_certificate_key': '',
            'ssl_password': password,
            'ssl_ciphers': '',
            'ssl_dhparam': '',
        }
    )
    values, cfg = fixtures.get_config(
        **values,
    )
    # Write config file
    cfgfile: str = ''
    with tempfile.NamedTemporaryFile(prefix='conf-', mode='w', delete=False) as f:
        f.write(fixtures.TEST_CONFIG.format(**values))
        cfgfile = f.name

    try:
        yield cfgfile
    finally:
        pass
        # Remove the files if they exists
        # for filename in (cfgfile, cert_file):
        #    try:
        #        os.remove(filename)
        #    except Exception:
        #        pass


@contextlib.asynccontextmanager
async def create_tunnel_proc(
    listen_host: str,
    listen_port: int,
    remote_host: str,
    remote_port: int,
    *,
    response: typing.Optional[typing.Mapping[str, typing.Any]] = None,
    use_fake_http_server: bool = False,
) -> typing.AsyncGenerator[
    typing.Tuple['config.ConfigurationType', typing.Optional[asyncio.Queue[bytes]]],
    None,
]:
    """Creates a "tunnel proc" server, that is, a tunnel server that will be
       invoked by udstunnel subpoocesses.

    Args:
        listen_host (str): Host to listen on
        listen_port (int): Port to listen on
        remote_host (str): Remote host to connect to
        remote_port (int): Remote port to connect to
        response (typing.Optional[typing.Mapping[str, typing.Any]], optional): Response to send to the tunnel. Defaults to None.
        use_fake_http_server (bool, optional): If True, a fake http server will be used instead of a mock. Defaults to False.

    Yields:
        typing.AsyncGenerator[typing.Tuple[config.ConfigurationType, typing.Optional[asyncio.Queue[bytes]]], None]: A tuple with the configuration 
            and a queue with the data received by the "fake_http_server" if used, or None if not used
    """

    port = random.randint(20000, 30000)
    hhost = f'[{listen_host}]' if ':' in listen_host else listen_host
    args = {
        'uds_server': f'http://{hhost}:{port}/uds/rest',
    }
    # If use http server instead of mock
    # We will setup a different context provider
    if use_fake_http_server:
        resp = conf.UDS_GET_TICKET_RESPONSE(remote_host, remote_port)

        @contextlib.asynccontextmanager
        async def provider() -> typing.AsyncGenerator[typing.Optional[asyncio.Queue[bytes]], None]:
            async with create_fake_broker_server(listen_host, port, response=resp) as queue:
                try:
                    yield queue
                finally:
                    pass

    else:

        @contextlib.asynccontextmanager
        async def provider() -> typing.AsyncGenerator[typing.Optional[asyncio.Queue[bytes]], None]:
            with mock.patch(
                'uds_tunnel.tunnel.TunnelProtocol._read_from_uds',
                new_callable=tools.AsyncMock,
            ) as m:
                m.return_value = response
                try:
                    yield None
                finally:
                    pass

    with create_config_file(listen_host, listen_port, **args) as cfgfile:
        args = mock.MagicMock()
        # Config can be a file-like or a path
        args.config = cfgfile
        args.ipv6 = False  # got from config file

        # Load config here also for testing
        cfg = config.read(cfgfile)

        # Ensure response
        if response is None:
            response = conf.UDS_GET_TICKET_RESPONSE(remote_host, remote_port)

        async with provider() as possible_queue:
            # Stats collector
            gs = stats.GlobalStats()
            # Pipe to send data to tunnel
            own_end, other_end = multiprocessing.Pipe()

            udstunnel.setup_log(cfg)

            # Set running flag
            udstunnel.running.set()

            # Create the tunnel task
            task = asyncio.create_task(
                udstunnel.tunnel_proc_async(other_end, cfg, gs.ns)
            )

            # Create a small asyncio server that reads the handshake,
            # and sends the socket to the tunnel_proc_async using the pipe
            # the pipe message will be typing.Tuple[socket.socket, typing.Tuple[str, int]]
            # socket and address
            async def client_connected_cb(reader, writer):
                # Read the handshake
                data = await reader.read(1024)
                # For testing, we ignore the handshake value
                # Send the socket to the tunnel
                own_end.send(
                    (
                        writer.get_extra_info('socket').dup(),
                        writer.get_extra_info('peername'),
                    )
                )
                # Close the socket
                writer.close()

            server = await asyncio.start_server(
                client_connected_cb,
                listen_host,
                listen_port,
            )
            try:
                yield cfg, possible_queue
            finally:
                # Close the pipe (both ends)
                own_end.close()

                task.cancel()
                # wait for the task to finish
                await task

                server.close()
                await server.wait_closed()
                logger.info('Server closed')

                # Ensure log file are removed
                rootlog = logging.getLogger()
                for h in rootlog.handlers:
                    if isinstance(h, logging.FileHandler):
                        h.close()
                        # Remove the file if possible, do not fail
                        try:
                            os.unlink(h.baseFilename)
                        except Exception:
                            pass


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
        if cfg.ipv6 or ':' in cfg.listen_address
        else socket.AF_INET,
    )


@contextlib.asynccontextmanager
async def create_test_tunnel(
    *,
    callback: typing.Callable[[bytes], None],
    port: typing.Optional[int] = None,
    remote_port: typing.Optional[int] = None,
) -> typing.AsyncGenerator['config.ConfigurationType', None]:
    # Generate a listening server for testing tunnel
    # Prepare the end of the tunnel
    async with tools.AsyncTCPServer(
        port=remote_port or 54876, callback=callback
    ) as server:
        # Create a tunnel to localhost 13579
        # SSl cert for tunnel server
        with certs.ssl_context(server.host) as (ssl_ctx, _):
            _, cfg = fixtures.get_config(
                address=server.host,
                port=port or 7771,
                ipv6=':' in server.host,
            )
            with mock.patch(
                'uds_tunnel.tunnel.TunnelProtocol._read_from_uds',
                new_callable=tools.AsyncMock,
            ) as m:
                m.return_value = conf.UDS_GET_TICKET_RESPONSE(server.host, server.port)

                tunnel_server = await create_tunnel_server(cfg, ssl_ctx)
                try:
                    yield cfg
                finally:
                    tunnel_server.close()
                    await tunnel_server.wait_closed()


@contextlib.asynccontextmanager
async def create_fake_broker_server(
    host: str, port: int, *, response: typing.Mapping[str, typing.Any]
) -> typing.AsyncGenerator[asyncio.Queue[bytes], None]:
    # crate a fake broker server
    # Ignores request, and sends response

    resp: bytes = (
        b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n'
        + json.dumps(response).encode()
    )

    # Future to content the server request
    data: bytes = b''
    requests: asyncio.Queue[bytes] = asyncio.Queue()

    async def processor(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        nonlocal data
        while readed := await reader.read(1024):
            data += readed
            # If data ends in \r\n\r\n, we have the full request
            if data.endswith(b'\r\n\r\n'):
                requests.put_nowait(data)
                data = b''  # reset data for next
                break

        # send response
        writer.write(resp)
        await writer.drain()
        # And close
        writer.close()

    async with tools.AsyncTCPServer(
        host=host, port=port, response=resp, processor=processor
    ) as server:
        try:
            yield requests
        finally:
            pass  # nothing to do


@contextlib.asynccontextmanager
async def open_tunnel_client(
    cfg: 'config.ConfigurationType',
    use_tunnel_handshake: bool = False,
) -> typing.AsyncGenerator[
    typing.Tuple[asyncio.StreamReader, asyncio.StreamWriter], None
]:
    """opens an ssl socket to the tunnel server"""
    loop = asyncio.get_running_loop()
    family = (
        socket.AF_INET6 if cfg.ipv6 or ':' in cfg.listen_address else socket.AF_INET
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    if not use_tunnel_handshake:
        reader, writer = await asyncio.open_connection(
            cfg.listen_address, cfg.listen_port, ssl=context, family=family
        )
    else:
        # Open the socket, send handshake and then upgrade to ssl, non blocking
        sock = socket.socket(family, socket.SOCK_STREAM)
        # Set socket to non blocking
        sock.setblocking(False)
        await loop.sock_connect(sock, (cfg.listen_address, cfg.listen_port))
        await loop.sock_sendall(sock, consts.HANDSHAKE_V1)
        # upgrade to ssl
        reader, writer = await asyncio.open_connection(
            sock=sock, ssl=context, server_hostname=cfg.listen_address
        )
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()


@contextlib.asynccontextmanager
async def tunnel_app_runner(
    host: typing.Optional[str] = None,
    port: typing.Optional[int] = None,
    *,
    wait_for_port: bool = False,
    args: typing.Optional[typing.List[str]] = None,
    **kwargs: typing.Union[str, int, bool],
) -> typing.AsyncGenerator['Process', None]:
    # Ensure we are on src directory
    if os.path.basename(os.getcwd()) != 'src':
        os.chdir('src')

    host = host or '127.0.0.1'
    port = port or 7799
    # Execute udstunnel as application, using asyncio.create_subprocess_exec
    # First, create the configuration file
    with create_config_file(host, port, **kwargs) as config_file:
        args = args or ['-t', '-c', config_file]
        process = await asyncio.create_subprocess_exec(
            'python',
            '-m',
            'udstunnel',
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if wait_for_port:
            # Ensure port is listening
            await tools.wait_for_port(host, port)

        try:
            yield process
        finally:
            # Ensure the process is terminated
            if process.returncode is None:
                process.terminate()
                await process.wait()


def get_correct_ticket(length: int = consts.TICKET_LENGTH) -> bytes:
    return ''.join(
        random.choice(string.ascii_letters + string.digits) for _ in range(length)
    ).encode()
