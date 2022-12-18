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
import logging
from unittest import IsolatedAsyncioTestCase, mock

from uds_tunnel import consts

from .utils import tuntools

logger = logging.getLogger(__name__)


class TestUDSTunnelApp(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Disable logging os slow tests
        logging.disable(logging.WARNING)
        return await super().asyncSetUp()

    async def test_tunnel_fail_cmd(self) -> None:
        consts.TIMEOUT_COMMAND = 0.1  # type: ignore  # timeout is a final variable, but we need to change it for testing speed
        for i in range(0, 100, 10):
            # Set timeout to 1 seconds
            bad_cmd = bytes(random.randint(0, 255) for _ in range(i))  # Some garbage
            logger.info(f'Testing invalid command with {bad_cmd!r}')
            for host in ('127.0.0.1', '::1'):
                # Remote is not really important in this tests, will fail before using it
                async with tuntools.create_tunnel_proc(
                    host, 7777, '127.0.0.1', 12345, workers=1
                ) as cfg:
                    # On full, we need the handshake to be done, before connecting
                    async with tuntools.open_tunnel_client(cfg, use_tunnel_handshake=True) as (creader, cwriter):
                        cwriter.write(bad_cmd)
                        await cwriter.drain()
                        # Read response              
                        data = await creader.read(1024)
                        # if len(bad_cmd) < consts.COMMAND_LENGTH, response will be RESPONSE_ERROR_TIMEOUT
                        if len(bad_cmd) >= consts.COMMAND_LENGTH:
                            self.assertEqual(data, consts.RESPONSE_ERROR_COMMAND)
                        else:
                            self.assertEqual(data, consts.RESPONSE_ERROR_TIMEOUT)
                        

