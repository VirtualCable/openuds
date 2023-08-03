# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import typing
from datetime import datetime
from time import mktime

# Date related constants
NEVER: typing.Final[datetime] = datetime(1972, 7, 1)
NEVER_UNIX: typing.Final[int] = int(mktime(NEVER.timetuple()))

# Max ip v6 string length representation, allowing ipv4 mapped addresses
MAX_IPV6_LENGTH: typing.Final[int] = 45
MAX_DNS_NAME_LENGTH: typing.Final[int] = 255

# Unknown mac address "magic" value
MAC_UNKNOWN: typing.Final[str] = '00:00:00:00:00:00'

# Default UDS Registerd Server listen port
SERVER_DEFAULT_LISTEN_PORT: typing.Final[int] = 43910

# REST Related constants
OK: typing.Final[
    str
] = 'ok'  # Constant to be returned when result is just "operation complete successfully"

# Maximum number of failures before blocking on REST API
ALLOWED_FAILS: typing.Final[int] = 5