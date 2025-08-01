# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
import abc
import typing
import logging
import codecs

from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.backends.db import SessionStore

from uds.core import consts, types
from uds.core.util.config import GlobalConfig
from uds.core.auths.auth import root_user
from uds.core.util import net
from uds.models import Authenticator, User
from uds.core.managers.crypto import CryptoManager

from ..core.exceptions.rest import AccessDenied


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


class Handler(abc.ABC):
    """
    REST requests handler base class
    """

    NAME: typing.ClassVar[typing.Optional[str]] = (
        None  # If name is not used, name will be the class name in lower case
    )
    PATH: typing.ClassVar[typing.Optional[str]] = (
        None  # Path for this method, so we can do /auth/login, /auth/logout, /auth/auths in a simple way
    )

    ROLE: typing.ClassVar[consts.UserRole] = (
        consts.UserRole.USER
    )  # By default, only users can access

    # For implementing help
    # A list of pairs of (path, help) for subpaths on this handler
    HELP_PATHS: typing.ClassVar[list[types.rest.doc.HelpDoc]] = []
    HELP_TEXT: typing.ClassVar[str] = 'No help available'

    _request: 'ExtendedHttpRequestWithUser'  # It's a modified HttpRequest
    _path: str
    _operation: str
    _params: dict[
        str, typing.Any
    ]  # This is a deserliazied object from request. Can be anything as 'a' or {'a': 1} or ....
    # These are the "path" split by /, that is, the REST invocation arguments
    _args: list[str]
    _kwargs: dict[str, typing.Any]  # This are the "path" split by /, that is, the REST invocation arguments
    _headers: dict[
        str, str
    ]  # Note: These are "output" headers, not input headers (input headers can be retrieved from request)
    _session: typing.Optional[SessionStore]
    _auth_token: typing.Optional[str]
    _user: 'User'

    # The dispatcher proceses the request and calls the method with the same name as the operation
    # currently, only 'get', 'post, 'put' y 'delete' are supported

    # possible future:'patch', 'head', 'options', 'trace'
    def __init__(
        self,
        request: 'ExtendedHttpRequestWithUser',
        path: str,
        method: str,
        params: dict[str, typing.Any],
        *args: str,
        **kwargs: typing.Any,
    ):
        self._request = request
        self._path = path
        self._operation = method
        self._params = params
        self._args = list(args)  # copy of args
        self._kwargs = kwargs
        self._headers = {}
        self._auth_token = None

        if self.ROLE.needs_authentication:
            try:
                self._auth_token = self._request.headers.get(consts.auth.AUTH_TOKEN_HEADER, '')
                self._session = SessionStore(session_key=self._auth_token)
                if 'REST' not in self._session:
                    raise Exception()  # No valid session, so auth_token is also invalid
            except Exception:  # Couldn't authenticate
                self._auth_token = None
                self._session = None

            if self._auth_token is None:
                raise AccessDenied()

            try:
                self._user = self.get_user()
            except Exception as e:
                # Maybe the user was deleted, so access is denied
                raise AccessDenied() from e

            if not self._user.can_access(self.ROLE):
                raise AccessDenied()
        else:
            self._user = User()  # Empty user for non authenticated handlers
            self._user.state = types.states.State.ACTIVE  # Ensure it's active

        if self._user and self._user.state != types.states.State.ACTIVE:
            raise AccessDenied()

    def headers(self) -> dict[str, str]:
        """
        Returns the headers of the REST request (all)
        """
        return self._headers

    def header(self, header_name: str) -> typing.Optional[str]:
        """
        Get's an specific header name from REST request

        Args:
            header_name: Name of header to retrieve

        Returns:
            Value of header or None if not found
        """
        return self._headers.get(header_name)

    def add_header(self, header: str, value: str) -> None:
        """
        Inserts a new header inside the headers list
        :param header: name of header to insert
        :param value: value of header
        """
        self._headers[header] = value

    def delete_header(self, header: str) -> None:
        """
        Removes an specific header from the headers list
        :param header: Name of header to remove
        """
        try:
            del self._headers[header]
        except Exception:  # nosec: intentionally ingoring exception
            pass  # If not found, just ignore it

    @property
    def request(self) -> 'ExtendedHttpRequestWithUser':
        """
        Returns the request object
        """
        return self._request

    @property
    def params(self) -> dict[str, typing.Any]:
        """
        Returns the params object
        """
        return self._params

    @property
    def args(self) -> list[str]:
        """
        Returns the args object
        """
        return self._args

    @property
    def session(self) -> 'SessionStore':
        if self._session is None:
            raise Exception('No session available')
        return self._session

    # Auth related
    def get_auth_token(self) -> typing.Optional[str]:
        """
        Returns the authentication token for this REST request
        """
        return self._auth_token

    @staticmethod
    def set_rest_auth(
        session: SessionBase,
        id_auth: int,
        username: str,
        password: str,
        locale: str,
        platform: str,
        scrambler: str,
    ) -> None:
        """
        Stores the authentication data inside current session
        :param session: session handler (Djano user session object)
        :param id_auth: Authenticator id (DB object id)
        :param username: Name of user (login name)
        :param locale: Assigned locale
        :param is_admin: If user is considered admin or not
        :param staff_member: If is considered as staff member
        """
        # crypt password and convert to base64
        passwd = codecs.encode(CryptoManager.manager().symmetric_encrypt(password, scrambler), 'base64').decode()

        session['REST'] = {
            'auth': id_auth,
            'username': username,
            'password': passwd,
            'locale': locale,
            'platform': platform,
        }

    def gen_auth_token(
        self,
        id_auth: int,
        username: str,
        password: str,
        locale: str,
        platform: str,
        scrambler: str,
    ) -> str:
        """
        Generates the authentication token from a session, that is basically
        the session key itself
        :param id_auth: Authenticator id (DB object id)
        :param username: Name of user (login name)
        :param locale: Assigned locale
        :param is_admin: If user is considered admin or not
        :param staf_member: If user is considered staff member or not
        """
        session = SessionStore()
        Handler.set_rest_auth(
            session,
            id_auth,
            username,
            password,
            locale,
            platform,
            scrambler,
        )
        session.save()
        self._auth_token = session.session_key
        self._session = session

        return typing.cast(str, self._auth_token)

    def clear_auth_token(self) -> None:
        """
        Cleans up the authentication token
        """
        self._auth_token = None
        if self._session:
            self._session.delete()
        self._session = None

    # Session related (from auth token)
    def recover_value(self, key: str) -> typing.Any:
        """
        Get REST session related value for a key
        """
        try:
            if self._session:
                # if key is password, its in base64, so decode it and return as bytes
                if key == 'password':
                    return codecs.decode(self._session['REST'][key], 'base64')
                return self._session['REST'].get(key)
            return None
        except Exception:
            return None

    def store_value(self, key: str, value: typing.Any) -> None:
        """
        Set a session key value
        """
        try:
            if self._session:
                # if key is password, its in base64, so encode it and store as str
                if key == 'password':
                    self._session['REST'][key] = codecs.encode(value, 'base64').decode()
                else:
                    self._session['REST'][key] = value
                self._session.accessed = True
                self._session.save()
        except Exception:
            logger.exception('Got an exception setting session value %s to %s', key, value)

    def is_ip_allowed(self) -> bool:
        try:
            return net.contains(GlobalConfig.ADMIN_TRUSTED_SOURCES.get(True), self._request.ip)
        except Exception:
            logger.warning(
                'Error checking truted ADMIN source: "%s" does not seems to be a valid network string. Using Unrestricted access.',
                GlobalConfig.ADMIN_TRUSTED_SOURCES.get(),
            )

        return True

    def is_admin(self) -> bool:
        """
        True if user of this REST request is administrator and SOURCE is valid admint trusted sources
        """
        return bool(self.recover_value('is_admin')) and self.is_ip_allowed()

    def is_staff_member(self) -> bool:
        """
        True if user of this REST request is member of staff
        """
        return bool(self.recover_value('staff_member')) and self.is_ip_allowed()

    def get_user(self) -> 'User':
        """
        If user is staff member, returns his Associated user on auth
        """
        # logger.debug('REST : %s', self._session)
        auth_id = self.recover_value('auth')
        username = self.recover_value('username')
        # Maybe it's root user??
        if (
            GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.as_bool(True)
            and username == GlobalConfig.SUPER_USER_LOGIN.get(True)
            and auth_id == -1
        ):
            return root_user()

        return Authenticator.objects.get(pk=auth_id).users.get(name=username)

    def get_param(self, *names: str) -> str:
        """
        Returns the first parameter found in the parameters (_params) list

        Args:
            *names: List of names to search

        Example:
            _params = {'username': 'uname_admin', 'name': 'name_admin'}
            get_param('name') will return 'admin'
            get_param('username', 'name') will return 'uname_admin'
            get_param('name', 'username') will return 'name_admin'
            get_param('other') will return ''
        """
        for name in names:
            if name in self._params:
                return self._params[name]
        return ''
