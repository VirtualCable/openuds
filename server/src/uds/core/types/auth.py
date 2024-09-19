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
import dataclasses
import enum

from django.urls import reverse


if typing.TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http.request import QueryDict
    from uds.models import User


class AuthenticationState(enum.IntEnum):
    """
    Enumeration for authentication success
    """

    FAIL = 0
    SUCCESS = 1
    REDIRECT = 2


class AuthenticationInternalUrl(enum.StrEnum):
    """
    Enumeration for authentication success
    """

    LOGIN = 'page.login'
    LOGIN_LABEL = 'page.login.tag'
    LOGOUT = 'page.logout'

    def get_url(self) -> str:
        """
        Returns the url for the given internal url
        """
        return reverse(self.value)


@dataclasses.dataclass(frozen=True)
class AuthenticationResult:
    success: AuthenticationState
    url: typing.Optional[str] = None
    username: typing.Optional[str] = None


# Comodity values
FAILED_AUTH = AuthenticationResult(success=AuthenticationState.FAIL)
SUCCESS_AUTH = AuthenticationResult(success=AuthenticationState.SUCCESS)


@dataclasses.dataclass
class AuthCallbackParams:
    '''Parameters passed to auth callback stage2

    This are the parameters that will be passes to the authenticator callback
    '''

    https: bool
    host: str
    path: str
    port: str
    get_params: 'QueryDict'
    post_params: 'QueryDict'
    query_string: str

    @staticmethod
    def from_request(request: 'HttpRequest') -> 'AuthCallbackParams':
        return AuthCallbackParams(
            https=request.is_secure(),
            host=request.META['HTTP_HOST'],
            path=request.META['PATH_INFO'],
            port=request.META['SERVER_PORT'],
            get_params=request.GET.copy(),
            post_params=request.POST.copy(),
            query_string=request.META['QUERY_STRING'],
        )


@dataclasses.dataclass
class LoginResult:
    user: typing.Optional['User'] = None
    password: str = ''
    errstr: typing.Optional[str] = None
    errid: int = 0
    url: typing.Optional[str] = None


@dataclasses.dataclass
class SearchResultItem:
    id: str
    name: str

    def as_dict(self) -> typing.Dict[str, str]:
        return dataclasses.asdict(self)
