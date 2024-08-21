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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import time
import typing

from django.conf import settings

if typing.TYPE_CHECKING:
    pass

# UDS Version related
VERSION: typing.Final[str] = '4.0.0'
VERSION_STAMP: typing.Final[str] = f'{time.strftime("%Y%m%d")}-devel'
# Minimal uds client version required to connect to this server
REQUIRED_CLIENT_VERSION: typing.Final[str] = '3.6.0'

# Max size of a rest request body
MAX_REQUEST_SIZE: typing.Final[int] = int(
    getattr(settings, 'MAX_REST_BODY_SIZE', 1024 * 1024 * 10)
)  # from settings, 10Mb by default

# Max ip v6 string length representation, allowing ipv4 mapped addresses
MAX_IPV6_LENGTH: typing.Final[int] = 45
MAX_DNS_NAME_LENGTH: typing.Final[int] = 255

# Maximum number of failures before blocking on REST API
ALLOWED_FAILS: typing.Final[int] = 5

# Servers communications constants (note, servers providing services TO UDS, not UDS servers)
USER_AGENT: typing.Final[str] = f'UDS/{VERSION}'
COMMS_TIMEOUT: typing.Final[int] = 5  # Timeout for communications with servers
MIN_SERVER_VERSION: typing.Final[str] = '4.0.0'
FAILURE_TIMEOUT: typing.Final[int] = 60  # In case of failure, wait this time before retrying (where applicable)

# Default length for Gui Text Fields
DEFAULT_TEXT_LENGTH: typing.Final[int] = 64

# Default maximum preparing services
DEFAULT_MAX_PREPARING_SERVICES: typing.Final[int] = 15

# Default wait time for rechecks, etc...
DEFAULT_WAIT_TIME: typing.Final[int] = 8  # seconds

# UDS Action url scheme
UDS_ACTION_SCHEME: typing.Final[str] = 'udsa://'

# Max sequence number for generators
MAX_SEQ: typing.Final[int] = 1000000000000000

