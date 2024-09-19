#
# Copyright (c) 2024 Virtual Cable S.L.U.
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

import contextlib
import typing
from uds.core.environment import Environment
from uds.core.util import security

from uds.auths.OAuth2.authenticator import OAuth2Authenticator
from uds.auths.OAuth2.types import ResponseType

KEYS: typing.Final[list[tuple[str, str]]] = [
    security.generate_rsa_keypair()
    for _ in range(3)
]

PUBLIC_KEYS: typing.Final[list[str]] = [key[1] for key in KEYS]

DATA_TEMPLATE: dict[str, str] = {
    'name': 'oauth2',
    'authorization_endpoint': 'https://auth_endpoint.com',
    'client_id': 'client_id',
    'client_secret': 'client_secret',
    'scope': 'openid email profile',  # Default scopes
    'common_groups': 'common_group',
    'redirection_endpoint': 'https://redirect_endpoint.com',
    'response_type': 'code',
    'token_endpoint': 'https://oauth2.googleapis.com/token',
    'info_endpoint': 'https://openidconnect.googleapis.com/v1/userinfo',
    'public_key': '\n'.join(PUBLIC_KEYS),
    'logout_url': 'https://logout.com?token={token}',
    'username_attr': 'username_attr',
    'groupname_attr': 'groupname_attr',
    'realname_attr': 'realname_attr',
}

@contextlib.contextmanager
def create_authenticator(response_type: ResponseType) -> typing.Iterator[OAuth2Authenticator]:
    with Environment.temporary_environment() as env:
        data = DATA_TEMPLATE.copy()
        data['response_type'] = str(response_type)
        instance = OAuth2Authenticator(environment=env, values=data)
        yield instance
