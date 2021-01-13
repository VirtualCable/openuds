# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import socket
import socketserver
import ssl
import threading
import time
import threading
import select
import typing
import logging

HANDSHAKE_V1 = b'\x5AMGB\xA5\x01\x00'
BUFFER_SIZE = 1024 * 16  # Max buffer length
DEBUG = True
LISTEN_ADDRESS = '0.0.0.0' if DEBUG else '127.0.0.1'

# ForwarServer states
TUNNEL_LISTENING, TUNNEL_OPENING, TUNNEL_PROCESSING, TUNNEL_ERROR = 0, 1, 2, 3

logger = logging.getLogger(__name__)

class ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    remote: typing.Tuple[str, int]
    ticket: str
    running: bool
    stop_flag: threading.Event
    timeout: int
    check_certificate: bool
    status: int

    def __init__(
        self,
        remote: typing.Tuple[str, int],
        ticket: str,
        timeout: int = 0,
        local_port: int = 0,
        check_certificate: bool = True,
    ) -> None:
        super().__init__(
            server_address=(LISTEN_ADDRESS, local_port), RequestHandlerClass=Handler
        )
        self.remote = remote
        self.ticket = ticket
        self.timeout = int(time.time()) + timeout if timeout else 0
        self.check_certificate = check_certificate
        self.stop_flag = threading.Event()  # False initial
        self.running = True

        self.status = TUNNEL_LISTENING

    def stop(self) -> None:
        if not self.stop_flag.is_set():
            self.stop_flag.set()
            self.running = False
            self.shutdown()


class Handler(socketserver.BaseRequestHandler):
    # Override Base type
    server: ForwardServer

    # server: ForwardServer
    def handle(self) -> None:
        # If server processing is timed out...
        if self.server.timeout and int(time.time()) > self.server.timeout:
            self.request.close()  # End connection without processing it
            return

        # Open remote connection
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rsocket:
                rsocket.connect(self.server.remote)

                context = ssl.create_default_context()

                with context.wrap_socket(
                    rsocket, server_hostname=self.server.remote[0]
                ) as ssl_socket:
                    # Send handhshake + command + ticket
                    ssl_socket.sendall(
                        HANDSHAKE_V1 + b'OPEN' + self.server.ticket.encode()
                    )
                    # Check response is OK
                    data = ssl_socket.recv(2)
                    if data != b'OK':
                        data += ssl_socket.recv(128)
                        raise Exception(data.decode())  # Notify error

                    # All is fine, now we can tunnel data
                    self.process(remote=ssl_socket)
        except Exception as e:
            # TODO log error connecting...
            if DEBUG:
                logger.exception('Processing')
            logger.error(f'Error connecting: {e!s}')
            self.server.status = TUNNEL_ERROR

    # Processes data forwarding
    def process(self, remote: ssl.SSLSocket):
        # Process data until stop requested or connection closed
        try:
            while not self.server.stop_flag.is_set():
                r, _w, _x = select.select([self.request, remote], [], [], 1.0)
                if self.request in r:
                    data = self.request.recv(BUFFER_SIZE)
                    if not data:
                        break
                    remote.sendall(data)
                if remote in r:
                    data = remote.recv(BUFFER_SIZE)
                    if not data:
                        break
                    self.request.sendall(data)
        except Exception as e:
            pass

def _run(server: ForwardServer) -> None:
    logger.debug('Starting server')
    server.serve_forever()
    logger.debug('Stoped server')

def forward(
    remote: typing.Tuple[str, int],
    ticket: str,
    timeout: int = 0,
    local_port: int = 0,
    check_certificate=True,
) -> ForwardServer:
    fs = ForwardServer(
        remote=remote,
        ticket=ticket,
        timeout=timeout,
        local_port=local_port,
        check_certificate=check_certificate,
    )
    # Starts a new thread
    threading.Thread(target=_run, args=(fs,)).start()

    return fs

if __name__ == "__main__":
    fs1 = forward(('fake.udsenterprise.com', 7777), '0'*64, local_port=49998)
    print(f'Listening on {fs1.server_address}')
    #fs2 = forward(('fake.udsenterprise.com', 7777), '1'*64, local_port=49999)
    #print(f'Listening on {fs2.server_address}')
#    time.sleep(30)
#    fs.stop()

