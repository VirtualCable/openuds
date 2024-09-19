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
import collections.abc
import dataclasses
import datetime
import enum
import typing


from django.utils.translation import gettext_noop as _

from uds.core.util import model


@dataclasses.dataclass
class TokenInfo:
    access_token: str
    token_type: str
    expires: datetime.datetime
    refresh_token: str
    scope: str
    info: dict[str, typing.Any]
    id_token: typing.Optional[str]

    @staticmethod
    def from_dict(dct: collections.abc.Mapping[str, typing.Any]) -> 'TokenInfo':
        # expires is -10 to avoid problems with clock sync
        return TokenInfo(
            access_token=dct['access_token'],
            token_type=dct['token_type'],
            expires=model.sql_now() + datetime.timedelta(seconds=dct['expires_in'] - 10),
            refresh_token=dct.get('refresh_token', ''),
            scope=dct['scope'],
            info=dct.get('info', {}),
            id_token=dct.get('id_token', None),
        )


class ResponseType(enum.StrEnum):
    CODE = 'code'
    PKCE = 'pkce'
    TOKEN = 'token'
    OPENID_TOKEN_ID = 'openid+token_id'
    OPENID_CODE = 'openid+code'

    @property
    def for_query(self) -> str:
        match self:
            case ResponseType.CODE:
                return 'code'
            case ResponseType.PKCE:
                return 'code'
            case ResponseType.TOKEN:
                return 'token'
            case ResponseType.OPENID_TOKEN_ID:
                return 'id_token'
            case ResponseType.OPENID_CODE:
                return 'code'

    @property
    def as_text(self) -> str:
        match self:
            case ResponseType.CODE:
                return _('Code (authorization code flow)')
            case ResponseType.PKCE:
                return _('PKCE (authorization code flow with PKCE)')
            case ResponseType.TOKEN:
                return _('Token (implicit flow)')
            case ResponseType.OPENID_TOKEN_ID:
                return _('OpenID Connect Token (implicit flow with OpenID Connect)')
            case ResponseType.OPENID_CODE:
                return _('OpenID Connect Code (authorization code flow with OpenID Connect)')
