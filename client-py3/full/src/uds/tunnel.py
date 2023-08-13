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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import socket
import socketserver
import ssl
import threading
import threading
import select
import typing
import logging

from . import tools

HANDSHAKE_V1 = b'\x5AMGB\xA5\x01\x00'
BUFFER_SIZE = 1024 * 16  # Max buffer length
LISTEN_ADDRESS = '127.0.0.1'

# ForwarServer states
TUNNEL_LISTENING, TUNNEL_OPENING, TUNNEL_PROCESSING, TUNNEL_ERROR = 0, 1, 2, 3


logger = logging.getLogger(__name__)

PayLoadType = typing.Optional[typing.Tuple[typing.Optional[bytes], typing.Optional[bytes]]]


class ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    remote: typing.Tuple[str, int]
    ticket: str
    stop_flag: threading.Event
    can_stop: bool
    timer: typing.Optional[threading.Timer]
    check_certificate: bool
    keep_listening: bool
    current_connections: int
    status: int

    def __init__(
        self,
        remote: typing.Tuple[str, int],
        ticket: str,
        timeout: int = 0,
        local_port: int = 0,
        check_certificate: bool = True,
        keep_listening: bool = False,
    ) -> None:
        # Negative values for timeout, means "accept always connections"
        # "but if no connection is stablished on timeout (positive)"
        # "stop the listener"
        # Note that this is for backwards compatibility, better use "keep_listening"
        if timeout < 0:
            keep_listening = True
            timeout = abs(timeout)

        super().__init__(server_address=(LISTEN_ADDRESS, local_port), RequestHandlerClass=Handler)
        self.remote = remote
        self.ticket = ticket
        self.check_certificate = check_certificate
        self.keep_listening = keep_listening
        self.stop_flag = threading.Event()  # False initial
        self.current_connections = 0

        self.status = TUNNEL_LISTENING
        self.can_stop = False

        timeout = timeout or 60
        self.timer = threading.Timer(abs(timeout), ForwardServer.__checkStarted, args=(self,))
        self.timer.start()

    def stop(self) -> None:
        if not self.stop_flag.is_set():
            logger.debug('Stopping servers')
            self.stop_flag.set()
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.shutdown()

    def connect(self) -> ssl.SSLSocket:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rsocket:
            logger.info('CONNECT to %s', self.remote)

            rsocket.connect(self.remote)

            rsocket.sendall(HANDSHAKE_V1)  # No response expected, just the handshake

            context = ssl.create_default_context()

            # Do not "recompress" data, use only "base protocol" compression
            context.options |= ssl.OP_NO_COMPRESSION
            # Macs with default installed python, does not support mininum tls version set to TLSv1.3
            # USe "brew" version instead, or uncomment next line and comment the next one
            # context.minimum_version = ssl.TLSVersion.TLSv1_2 if tools.isMac() else ssl.TLSVersion.TLSv1_3
            context.minimum_version = ssl.TLSVersion.TLSv1_3

            if tools.getCaCertsFile() is not None:
                context.load_verify_locations(tools.getCaCertsFile())  # Load certifi certificates

            # If ignore remote certificate
            if self.check_certificate is False:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                logger.warning('Certificate checking is disabled!')

            return context.wrap_socket(rsocket, server_hostname=self.remote[0])

    def check(self) -> bool:
        if self.status == TUNNEL_ERROR:
            return False

        logger.debug('Checking tunnel availability')

        try:
            with self.connect() as ssl_socket:
                ssl_socket.sendall(b'TEST')
                resp = ssl_socket.recv(2)
                if resp != b'OK':
                    raise Exception({'Invalid  tunnelresponse: {resp}'})
                logger.debug('Tunnel is available!')
                return True
        except Exception as e:
            logger.error('Error connecting to tunnel server %s: %s', self.server_address, e)
        return False

    @property
    def stoppable(self) -> bool:
        logger.debug('Is stoppable: %s', self.can_stop)
        return self.can_stop

    @staticmethod
    def __checkStarted(fs: 'ForwardServer') -> None:
        # As soon as the timer is fired, the server can be stopped
        # This means that:
        #  * If not connections are stablished, the server will be stopped
        #  * If no "keep_listening" is set, the server will not allow any new connections
        logger.debug('New connection limit reached')
        fs.timer = None
        fs.can_stop = True
        if fs.current_connections <= 0:
            fs.stop()


class Handler(socketserver.BaseRequestHandler):
    # Override Base type
    server: ForwardServer

    # server: ForwardServer
    def handle(self) -> None:
        self.server.status = TUNNEL_OPENING

        # If server processing is over time, and don't allow more connections
        if self.server.stoppable and not self.server.keep_listening:
            self.server.status = TUNNEL_ERROR
            logger.info('Rejected timedout connection')
            self.request.close()  # End connection without processing it
            return

        self.server.current_connections += 1

        # Open remote connection
        try:
            logger.debug('Ticket %s', self.server.ticket)
            with self.server.connect() as ssl_socket:
                # Send handhshake + command + ticket
                ssl_socket.sendall(b'OPEN' + self.server.ticket.encode())
                # Check response is OK
                data = ssl_socket.recv(2)
                if data != b'OK':
                    data += ssl_socket.recv(128)
                    raise Exception(f'Error received: {data.decode(errors="ignore")}')  # Notify error

                # All is fine, now we can tunnel data

                self.process(remote=ssl_socket)
        except Exception as e:
            logger.error(f'Error connecting to {self.server.remote!s}: {e!s}')
            self.server.status = TUNNEL_ERROR
            self.server.stop()
        finally:
            self.server.current_connections -= 1

        if self.server.current_connections <= 0 and self.server.stoppable:
            self.server.stop()

    # Processes data forwarding
    def process(self, remote: ssl.SSLSocket):
        self.server.status = TUNNEL_PROCESSING
        logger.debug('Processing tunnel with ticket %s', self.server.ticket)
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
            logger.debug('Finished tunnel with ticket %s', self.server.ticket)
        except Exception as e:
            pass


def _run(server: ForwardServer) -> None:
    logger.debug(
        'Starting forwarder: %s -> %s',
        server.server_address,
        server.remote,
    )
    server.serve_forever()
    logger.debug('Stoped forwarder %s -> %s', server.server_address, server.remote)


def forward(
    remote: typing.Tuple[str, int],
    ticket: str,
    timeout: int = 0,
    local_port: int = 0,
    check_certificate=True,
    keep_listening=True,
) -> ForwardServer:
    fs = ForwardServer(
        remote=remote,
        ticket=ticket,
        timeout=timeout,
        local_port=local_port,
        check_certificate=check_certificate,
        keep_listening=keep_listening,
    )
    # Starts a new thread
    threading.Thread(target=_run, args=(fs,)).start()

    return fs
