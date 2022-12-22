# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing

DEBUG = True

CONFIGFILE: typing.Final[str] = '/etc/udstunnel.conf' if not DEBUG else 'udstunnel.conf'
LOGFORMAT: typing.Final[str] = (
    '%(levelname)s %(asctime)s %(message)s'
    if not DEBUG
    else '%(levelname)s %(asctime)s %(name)s:%(funcName)s %(lineno)d %(message)s'
)

# MAX Length of read buffer for proxyed requests
BUFFER_SIZE: typing.Final[int] = 1024 * 16
# Handshake for conversation start
HANDSHAKE_V1: typing.Final[bytes] = b'\x5AMGB\xA5\x01\x00'
# Ticket length
TICKET_LENGTH: typing.Final[int] = 48
# Max Admin password length (stats basically right now)
PASSWORD_LENGTH: typing.Final[int] = 64
# Bandwidth calc time lapse
BANDWIDTH_TIME: typing.Final[int] = 10

# Commands LENGTH (all same length)
COMMAND_LENGTH: typing.Final[int] = 4

VERSION: typing.Final[str] = 'v2.0.0'
USER_AGENT: typing.Final[str] = f'UDSTunnel/{VERSION}'

# Valid commands
COMMAND_OPEN: typing.Final[bytes] = b'OPEN'
COMMAND_TEST: typing.Final[bytes] = b'TEST'
COMMAND_STAT: typing.Final[bytes] = b'STAT'  # full stats
COMMAND_INFO: typing.Final[bytes] = b'INFO'  # Basic stats, currently same as FULL

RESPONSE_ERROR_TICKET: typing.Final[bytes] = b'ERROR_TICKET'
RESPONSE_ERROR_COMMAND: typing.Final[bytes] = b'ERROR_COMMAND'
RESPONSE_ERROR_TIMEOUT: typing.Final[bytes] = b'TIMEOUT'
RESPONSE_FORBIDDEN: typing.Final[bytes] = b'FORBIDDEN'

RESPONSE_OK: typing.Final[bytes] = b'OK'

# Backlog for listen socket
BACKLOG = 1024
