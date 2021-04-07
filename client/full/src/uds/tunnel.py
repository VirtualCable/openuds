# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
from __future__ import unicode_literals

import socket
import ssl
import threading
import time
import random
import select
import logging

import six

if six.PY2:
    import SocketServer as socketserver  # pylint: disable=import-error
else:
    import socketserver # pylint: disable=import-error

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

    def __init__(
            self,
            remote,
            ticket,
            timeout,
            local_port,
            check_certificate,
        ):

        local_port = local_port or random.randrange(33000, 53000)

        socketserver.ThreadingTCPServer.__init__(
            self,
            server_address=(LISTEN_ADDRESS, local_port),
            RequestHandlerClass=Handler
        )
        self.remote = remote
        self.ticket = ticket
        # Negative values for timeout, means "accept always connections"
        # "but if no connection is stablished on timeout (positive)"
        # "stop the listener"
        self.timeout = int(time.time()) + timeout if timeout > 0 else 0
        self.check_certificate = check_certificate
        self.stop_flag = threading.Event()  # False initial
        self.current_connections = 0

        self.status = TUNNEL_LISTENING
        self.can_stop = False

        timeout = abs(timeout) or 60
        self.timer = threading.Timer(
            abs(timeout), ForwardServer.__checkStarted, args=(self,)
        )
        self.timer.start()

    def stop(self):
        if not self.stop_flag.is_set():
            logger.debug('Stopping servers')
            self.stop_flag.set()
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.shutdown()

    def connect(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rsocket:
            logger.info('CONNECT to %s', self.remote)

            rsocket.connect(self.remote)

            context = ssl.create_default_context()

            # Do not "recompress" data, use only "base protocol" compression
            context.options |= ssl.OP_NO_COMPRESSION

            # If ignore remote certificate
            if self.check_certificate is False:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                logger.warning('Certificate checking is disabled!')

            return context.wrap_socket(rsocket, server_hostname=self.remote[0])

    def check(self):
        if self.status == TUNNEL_ERROR:
            return False

        try:
            with self.connect() as ssl_socket:
                ssl_socket.sendall(HANDSHAKE_V1 + b'TEST')
                resp = ssl_socket.recv(2)
                if resp != b'OK':
                    raise Exception({'Invalid  tunnelresponse: {resp}'})
                return True
        except Exception as e:
            logger.error(
                'Error connecting to tunnel server %s: %s', self.server_address, e
            )
        return False

    @property
    def stoppable(self):
        logger.debug('Is stoppable: %s', self.can_stop)
        return self.can_stop or (self.timeout != 0 and int(time.time()) > self.timeout)

    @staticmethod
    def __checkStarted(fs):
        logger.debug('New connection limit reached')
        fs.timer = None
        fs.can_stop = True
        if fs.current_connections <= 0:
            fs.stop()


class Handler(socketserver.BaseRequestHandler):
    # server: ForwardServer
    def handle(self):
        self.server.status = TUNNEL_OPENING

        # If server processing is over time
        if self.server.stoppable:
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
                ssl_socket.sendall(HANDSHAKE_V1 + b'OPEN' + self.server.ticket.encode())
                # Check response is OK
                data = ssl_socket.recv(2)
                if data != b'OK':
                    data += ssl_socket.recv(128)
                    raise Exception(
                        'Error received: {}'.format(data.decode(errors="ignore"))
                    )  # Notify error

                # All is fine, now we can tunnel data
                self.process(remote=ssl_socket)
        except Exception as e:
            logger.error('Error connecting to %s', self.server.remote)
            self.server.status = TUNNEL_ERROR
            self.server.stop()
        finally:
            self.server.current_connections -= 1

        if self.server.current_connections <= 0 and self.server.stoppable:
            self.server.stop()

    # Processes data forwarding
    def process(self, remote):
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
            logger.debug('Finished tunnel with ticekt %s', self.server.ticket)
        except Exception as e:
            pass


def _run(server):
    logger.debug(
        'Starting forwarder: %s -> %s, timeout: %d',
        server.server_address,
        server.remote,
        server.timeout,
    )
    server.serve_forever()
    logger.debug('Stoped forwarder %s -> %s', server.server_address, server.remote)


def forward(
        remote,
        ticket,
        timeout=0,
        local_port=0,
        check_certificate=True,
    ):

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
