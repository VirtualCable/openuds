"""
 Copyright (c) 2023 Adolfo Gómez García <dkmaster@dkmon.com>
 
 This software is released under the MIT License.
 https://opensource.org/licenses/MIT
"""

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
import typing
import logging

from . import consts, config

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from . import tunnel, stats


# Protocol
class TunnelClientProtocol(asyncio.Protocol):
    # Transport and other side of tunnel
    transport: 'asyncio.transports.Transport'
    receiver: 'tunnel.TunnelProtocol'
    destination: typing.Tuple[str, int]

    def __init__(
        self, receiver: 'tunnel.TunnelProtocol'
    ) -> None:
        # If no other side is given, we are the server part
        super().__init__()
        # transport is undefined until connection_made is called
        self.receiver = receiver
        self.notify_ticket = b''
        self.destination = ('', 0)

    def data_received(self, data: bytes):
        self.receiver.send(data)

    def connection_made(self, transport: 'asyncio.transports.BaseTransport') -> None:
        self.transport = typing.cast('asyncio.transports.Transport', transport)

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        # Ensure close other side if not server_side
        try:
            self.receiver.close_connection()
        except Exception:
            pass

    def send(self, data: bytes):
        self.transport.write(data)

    def close_connection(self):
        try:
            if not self.transport.is_closing():
                self.transport.close()
        except Exception:
            pass  # Ignore errors
