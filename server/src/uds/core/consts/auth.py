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
import typing

# Constants for Visibility
VISIBLE: typing.Final[str] = 'v'
HIDDEN: typing.Final[str] = 'h'
DISABLED: typing.Final[str] = 'd'

# net_filter
# Note: this are STANDARD values used on "default field" networks on REST API
# Named them for better reading, but cannot be changed, since they are used on REST API
NO_FILTERING: typing.Final[str] = 'n'
ALLOW: typing.Final[str] = 'a'
DENY: typing.Final[str] = 'd'

# Cookie for mfa and csrf field
MFA_COOKIE_NAME: typing.Final[str] = 'mfa_status'
CSRF_FIELD: typing.Final[str] = 'csrfmiddlewaretoken'

# Headers
# Auth token
AUTH_TOKEN_HEADER: typing.Final[str] = 'X-Auth-Token'
# Meta header for auth token, not used
# AUTH_TOKEN_HEADER: typing.Final[str] = 'HTTP_X_AUTH_TOKEN'  # nosec: this is not a password

X_FORWARDED_FOR_HEADER: typing.Final[str] = 'X-Forwarded-For'

# Session related
SESSION_USER_KEY: typing.Final[str] = 'uk'
SESSION_PASS_KEY: typing.Final[str] = 'pk'  # nosec: this is not a password but a cookie to store encrypted data
SESSION_EXPIRY_KEY: typing.Final[str] = 'ek'
SESSION_AUTHORIZED_KEY: typing.Final[str] = 'ak'
SESSION_IP_KEY: typing.Final[str] = 'session_ip'

# Cookie length and root "fake" id
UDS_COOKIE_LENGTH: typing.Final[int] = 48
ROOT_ID: typing.Final[int] = -20091204  # Any negative number will do the trick
