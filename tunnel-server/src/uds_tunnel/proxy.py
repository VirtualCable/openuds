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
import socket
import logging
import typing

from . import config
from . import tunnel

if typing.TYPE_CHECKING:
    from multiprocessing.managers import Namespace
    import ssl

logger = logging.getLogger(__name__)


class Proxy:
    cfg: 'config.ConfigurationType'
    ns: 'Namespace'
    finished: asyncio.Future

    def __init__(self, cfg: 'config.ConfigurationType', ns: 'Namespace') -> None:
        self.cfg = cfg
        self.ns = ns

    # Method responsible of proxying requests
    async def __call__(self, source: socket.socket, context: 'ssl.SSLContext') -> None:
        try:
            await self.proxy(source, context)
        except asyncio.CancelledError:
            pass  # Return on cancel
        except Exception as e:
            # get source ip address
            try:
                addr = source.getpeername()
            except Exception:
                addr = 'Unknown'
            logger.exception('Proxy error from %s: %s (%s--%s)', addr, e, source, context)

    async def proxy(self, source: socket.socket, context: 'ssl.SSLContext') -> None:
        loop = asyncio.get_running_loop()
        # Handshake correct in this point, upgrade the connection to TSL and let
        # the protocol controller do the rest
        self.finished = loop.create_future()

        # Upgrade connection to SSL, and use asyncio to handle the rest
        try:
            def factory() -> tunnel.TunnelProtocol:
                return tunnel.TunnelProtocol(self)
            # (connect accepted loop not present on AbastractEventLoop definition < 3.10), that's why we use ignore
            await loop.connect_accepted_socket(  # type: ignore
                factory, source, ssl=context
            )

            # Wait for connection to be closed
            await self.finished
            
            
        except asyncio.CancelledError:
            pass  # Return on cancel

        return
