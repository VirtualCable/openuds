# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import collections.abc
import logging
import time
import typing

from uds.core import consts, exceptions
from uds.core.auths.auth import authenticate
from uds.core.managers.crypto import CryptoManager
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig
from uds.core.util.model import process_uuid
from uds.models import Authenticator
from uds.REST import Handler
from uds.REST.utils import rest_result

logger = logging.getLogger(__name__)

# Enclosed methods under /auth path


class Login(Handler):
    """
    Responsible of user authentication
    """

    PATH = 'auth'
    ROLE = consts.UserRole.ANONYMOUS

    @staticmethod
    def result(
        result: str = 'error',
        token: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        # Valid kwargs are: error, scrambler
        return rest_result(result, token=token, **kwargs)

    def post(self) -> typing.Any:
        """
        This login uses parameters to generate auth token
        The alternative is to use the template tag inside "REST" that is called auth_token, that extracts an auth token from an user session
        We can use any of this forms due to the fact that the auth token is in fact a session key
        Parameters:
            mandatory:
                username:
                password:
                auth_id or auth or auth_label (authId and authSmallName for backwards compat, tbr): (must include at least one. If multiple are used, precedence is the list order)
            optional:
                platform: From what platform are we connecting. If not specified, will try to deduct it from user agent.
                Valid values:
                    Linux = 'Linux'
                    WindowsPhone = 'Windows Phone'
                    Windows = 'Windows'
                    Macintosh = 'MacOsX'
                    Android = 'Android'
                    iPad = 'iPad'
                    iPhone = 'iPhone'
                Defaults to:
                    Unknown = 'Unknown'

        Result:
            on success: { 'result': 'ok', 'auth': [auth_code] }
            on error: { 'result: 'error', 'error': [error string] }

        Locale comes on "Header", as any HTTP Request (Accept-Language header)
        Calls to any method of REST that must be authenticated needs to be called with "X-Auth-Token" Header added
        """
        # Checks if client is "blocked"
        fail_cache = Cache('RESTapi')
        fails = fail_cache.get(self._request.ip) or 0
        if fails > consts.system.ALLOWED_FAILS:
            logger.info(
                'Access to REST API %s is blocked for %s seconds since last fail',
                self._request.ip,
                GlobalConfig.LOGIN_BLOCK.as_int(),
            )
            raise exceptions.rest.AccessDenied('Too many fails')

        try:
            # if (
            #     'auth_id' not in self._params
            #     and 'authId' not in self._params
            #     and 'auth_id' not in self._params
            #     and 'authSmallName' not in self._params
            #     and 'authLabel' not in self._params
            #     and 'auth_label' not in self._params
            #     and 'auth' not in self._params
            # ):
            #     raise RequestError('Invalid parameters (no auth)')

            # Check if we have a valid auth
            if not any(
                i in self._params
                for i in ('auth_id', 'authId', 'authSmallName', 'authLabel', 'auth_label', 'auth')
            ):
                raise exceptions.rest.RequestError('Invalid parameters (no auth)')

            auth_id: typing.Optional[str] = self._params.get(
                'auth_id',
                self._params.get('authId', None),  # Old compat, alias
            )
            auth_label: typing.Optional[str] = self._params.get(
                'auth_label',
                self._params.get(
                    'authSmallName',  # Old compat name
                    self._params.get('authLabel', None),  # Old compat name
                ),
            )
            auth_name: typing.Optional[str] = self._params.get('auth', None)
            platform: str = self._params.get('platform', self._request.os.os.value[0])

            username: str = self._params['username']
            password: str = self._params['password']
            locale: str = self._params.get('locale', 'en')

            # Generate a random scrambler
            scrambler: str = CryptoManager.manager().random_string(32)
            if (
                auth_name == 'admin'
                or auth_label == 'admin'
                or auth_id == '00000000-0000-0000-0000-000000000000'
                or (not auth_id and not auth_name and not auth_label)
            ):
                if GlobalConfig.SUPER_USER_LOGIN.get(True) == username and CryptoManager.manager().check_hash(
                    password, GlobalConfig.SUPER_USER_PASS.get(True)
                ):
                    self.gen_auth_token(-1, username, password, locale, platform, scrambler)
                    return Login.result(result='ok', token=self.get_auth_token())
                return Login.result(error='Invalid credentials')

            # Will raise an exception if no auth found
            if auth_id:
                auth = Authenticator.objects.get(uuid=process_uuid(auth_id))
            elif auth_name:
                auth = Authenticator.objects.get(name__iexact=auth_name)
            else:
                auth = Authenticator.objects.get(small_name__iexact=auth_label)

            # No matter in fact the password, just not empty (so it can be encrypted, but will be invalid anyway)
            password = password or CryptoManager().random_string(32)

            logger.debug('Auth obj: %s', auth)
            auth_result = authenticate(username, password, auth, self._request)
            if auth_result.user is None:  # invalid credentials
                # Sleep a while here to "prottect"
                time.sleep(3)  # Wait 3 seconds if credentials fails for "protection"
                # And store in cache for blocking for a while if fails
                fail_cache.put(self._request.ip, fails + 1, GlobalConfig.LOGIN_BLOCK.as_int())

                return Login.result(error=auth_result.errstr or 'Invalid credentials')
            return Login.result(
                result='ok',
                token=self.gen_auth_token(
                    auth.id,
                    auth_result.user.name,
                    password,
                    locale,
                    platform,
                    scrambler,
                ),
                scrambler=scrambler,
            )

        except Exception as e:
            logger.error('Invalid credentials: %s: %s', self._params, e)
            pass

        return Login.result(error='Invalid credentials')


class Logout(Handler):
    """
    Responsible of user de-authentication
    """

    PATH = 'auth'
    ROLE = consts.UserRole.USER  # Must be logged in to logout :)

    def get(self) -> typing.Any:
        # Remove auth token
        self.clear_auth_token()
        return {'result': 'ok'}

    def post(self) -> typing.Any:
        return self.get()


class Auths(Handler):
    PATH = 'auth'
    ROLE = consts.UserRole.ANONYMOUS

    def auths(self) -> collections.abc.Iterable[dict[str, typing.Any]]:
        all_param: bool = self._params.get('all', 'false').lower() == 'true'
        auth: Authenticator
        for auth in Authenticator.objects.all():
            auth_type = auth.get_type()
            if all_param or (auth_type.is_custom() is False and auth_type.type_type not in ('IP',)):
                yield {
                    'authId': auth.uuid,  # Deprecated, use 'auth_id'
                    'auth_id': auth.uuid,
                    'authSmallName': str(auth.small_name),  # Deprecated
                    'authLabel': str(auth.small_name),  # Deprecated, use 'auth_label'
                    'auth_label': str(auth.small_name),
                    'auth': auth.name,
                    'type': auth_type.type_type,
                    'priority': auth.priority,
                    'isCustom': auth_type.is_custom(),  # Deprecated, use 'custom'
                    'custom': auth_type.is_custom(),
                }

    def get(self) -> list[dict[str, typing.Any]]:
        return list(self.auths())
