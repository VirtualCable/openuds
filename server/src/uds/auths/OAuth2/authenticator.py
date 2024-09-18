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
import logging
import hashlib
import secrets
import string
import typing
import dataclasses
import collections.abc
import datetime
import urllib.parse
from base64 import b64decode

import jwt
import requests
from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _

from uds.core import auths, consts, exceptions, types
from uds.core.ui import gui
from uds.core.util import fields, model, auth as auth_utils

if typing.TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

# Alphabet used for PKCE
PKCE_ALPHABET: typing.Final[str] = string.ascii_letters + string.digits + '-._~'
# Length of the State parameter
STATE_LENGTH: typing.Final[int] = 16


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

class OAuth2Authenticator(auths.Authenticator):
    """
    This class represents an OAuth2 Authenticator.
    """

    type_name = _('OAuth2 Authenticator')
    type_type = 'OAuth2Authenticator'
    type_description = _('OAuth2 Authenticator')
    icon_file = 'oauth2.png'

    authorization_endpoint = gui.TextField(
        length=256,
        label=_('Authorization endpoint'),
        order=10,
        tooltip=_('Authorization endpoint for OAuth2.'),
        required=True,
        tab=_('Server'),
    )
    client_id = gui.TextField(
        length=128,
        label=_('Client ID'),
        order=2,
        tooltip=_('Client ID for OAuth2.'),
        required=True,
        tab=_('Server'),
    )
    client_secret = gui.TextField(
        length=128,
        label=_('Client Secret'),
        order=3,
        tooltip=_('Client secret for OAuth2.'),
        required=True,
        tab=_('Server'),
    )
    scope = gui.TextField(
        length=128,
        label=_('Scope'),
        order=4,
        tooltip=_('Scope for OAuth2.'),
        required=True,
        tab=_('Server'),
    )
    common_groups = gui.TextField(
        length=128,
        label=_('Common Groups'),
        order=5,
        tooltip=_('User will be assigned to this groups once authenticated. Comma separated list of groups'),
        required=False,
        tab=_('Server'),
    )

    # Advanced options
    redirection_endpoint = gui.TextField(
        length=128,
        label=_('Redirection endpoint'),
        order=90,
        tooltip=_('Redirection endpoint for OAuth2.  (Filled by UDS)'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    response_type = gui.ChoiceField(
        label=_('Response type'),
        order=91,
        tooltip=_('Response type for OAuth2.'),
        required=True,
        default='code',
        choices=[
            {'id': 'code', 'text': _('Code (authorization code flow)')},
            {'id': 'pkce', 'text': _('PKCE (authorization code flow with PKCE)')},
            {'id': 'token', 'text': _('Token (implicit flow)')},
            {
                'id': 'openid+token_id',
                'text': _('OpenID Connect Token (implicit flow with OpenID Connect)'),
            },
            {
                'id': 'openid+code',
                'text': _('OpenID Connect Code (authorization code flow with OpenID Connect)'),
            },
        ],
        tab=types.ui.Tab.ADVANCED,
    )
    # In case of code, we need to get the token from the token endpoint
    token_endpoint = gui.TextField(
        length=128,
        label=_('Token endpoint'),
        order=92,
        tooltip=_('Token endpoint for OAuth2. Only required for "code" response type.'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    info_endpoint = gui.TextField(
        length=128,
        label=_('User information endpoint'),
        order=93,
        tooltip=_('User information endpoint for OAuth2. Only required for "code" response type.'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    public_key = gui.TextField(
        length=16384,
        lines=3,
        label=_('Public Key'),
        order=94,
        tooltip=_('Provided by Oauth2 provider'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    
    username_attr = fields.username_attr_field(order=100)
    groupname_attr = fields.groupname_attr_field(order=101)
    realname_attr = fields.realname_attr_field(order=102)

    def _get_public_keys(self) -> list[typing.Any]:  # In fact, any of the PublicKey types
        # Get certificates in self.publicKey.value, encoded as PEM
        # Return a list of certificates in DER format
        if self.public_key.value.strip() == '':
            return []

        return [cert.public_key() for cert in fields.get_certificates_from_field(self.public_key)]

    def _code_verifier_and_challenge(self) -> tuple[str, str]:
        """Generate a code verifier and a code challenge for PKCE

        Returns:
            tuple[str, str]: Code verifier and code challenge
        """
        code_verifier = ''.join(secrets.choice(PKCE_ALPHABET) for _ in range(128))
        code_challenge = (
            b64decode(hashlib.sha256(code_verifier.encode('ascii')).digest(), altchars=b'-_')
            .decode()
            .rstrip('=')  # remove padding
        )

        return code_verifier, code_challenge

    def _get_response_type_string(self) -> str:
        match self.response_type.value:
            case 'code':
                return 'code'
            case 'pkce':
                return 'code'
            case 'token':
                return 'token'
            case 'openid+token_id':
                return 'id_token'
            case 'openid+code':
                return 'code'
            case _:
                raise Exception('Invalid response type')

    def _get_login_url(self, request: 'HttpRequest') -> str:
        """
        :type request: django.http.request.HttpRequest
        """
        state: str = secrets.token_urlsafe(STATE_LENGTH)

        param_dict = {
            'response_type': self._get_response_type_string(),
            'client_id': self.client_id.value,
            'redirect_uri': self.redirection_endpoint.value,
            'scope': self.scope.value.replace(',', ' '),
            'state': state,
        }

        match self.response_type.value:
            case 'code' | 'token':
                # Code or token flow
                # Simply store state, no code_verifier, store "none" as code_verifier to later restore it
                self.cache.put(state, 'none', 3600)
            case 'openid+code' | 'openid+token_id':
                # OpenID flow
                nonce = secrets.token_urlsafe(STATE_LENGTH)
                self.cache.put(state, nonce, 3600)  # Store nonce
                # Fix scope
                param_dict['scope'] = 'openid ' + param_dict['scope']
                # Append nonce
                param_dict['nonce'] = nonce
                # Add response_mode
                param_dict['response_mode'] = 'form_post'  # ['query', 'fragment', 'form_post']

            case 'pkce':
                # PKCE flow
                codeVerifier, codeChallenge = self._code_verifier_and_challenge()
                param_dict['code_challenge'] = codeChallenge
                param_dict['code_challenge_method'] = 'S256'
                self.cache.put(state, codeVerifier, 3600)

            case _:
                raise Exception('Invalid response type')

        # Nonce only is used
        if False:
            param_dict['nonce'] = nonce

        if False:
            param_dict['response_mode'] = 'form_post'  # ['query', 'fragment', 'form_post']

        params = urllib.parse.urlencode(param_dict)

        return self.authorization_endpoint.value + '?' + params

    def _request_token(self, code: str, code_verifier: typing.Optional[str] = None) -> TokenInfo:
        """Request a token from the token endpoint using the code received from the authorization endpoint

        Args:
            code (str): Code received from the authorization endpoint

        Returns:
            TokenInfo: Token received from the token endpoint
        """
        param_dict = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id.value,
            'client_secret': self.client_secret.value,
            'redirect_uri': self.redirection_endpoint.value,
            'code': code,
        }
        if code_verifier:
            param_dict['code_verifier'] = code_verifier

        response = requests.post(
            self.token_endpoint.value, data=param_dict, timeout=consts.system.COMMS_TIMEOUT
        )
        logger.debug('Token request: %s %s', response.status_code, response.text)

        if not response.ok:
            raise Exception('Error requesting token: {}'.format(response.text))

        return TokenInfo.from_dict(response.json())

    def _request_info(self, token: 'TokenInfo') -> dict[str, typing.Any]:
        """Request user info from the info endpoint using the token received from the token endpoint

        If the token endpoint returns the user info, this method will not be used

        Args:
            token (TokenInfo): Token received from the token endpoint

        Returns:
            dict[str, typing.Any]: User info received from the info endpoint
        """
        userInfo: dict[str, typing.Any]

        if self.info_endpoint.value.strip() == '':
            if not token.info:
                raise Exception('No user info received')
            userInfo = token.info
        else:
            # Get user info
            req = requests.get(
                self.info_endpoint.value,
                headers={'Authorization': 'Bearer ' + token.access_token},
                timeout=consts.system.COMMS_TIMEOUT,
            )
            logger.debug('User info request: %s %s', req.status_code, req.text)

            if not req.ok:
                raise Exception('Error requesting user info: {}'.format(req.text))

            userInfo = req.json()
        return userInfo

    def _process_token(
        self, userInfo: collections.abc.Mapping[str, typing.Any], gm: 'auths.GroupsManager'
    ) -> types.auth.AuthenticationResult:
        # After this point, we don't mind about the token, we only need to authenticate user
        # and get some basic info from it

        username = ''.join(auth_utils.process_regex_field(self.username_attr.value, userInfo)).replace(' ', '_')
        if len(username) == 0:
            raise Exception('No username received')

        realName = ''.join(auth_utils.process_regex_field(self.realname_attr.value, userInfo))

        # Get groups
        groups = auth_utils.process_regex_field(self.groupname_attr.value, userInfo)
        # Append common groups
        groups.extend(self.common_groups.value.split(','))

        # store groups for this username at storage, so we can check it at a later stage
        self.storage.save_pickled(username, [realName, groups])

        # Validate common groups
        gm.validate(groups)

        # We don't mind about the token, we only need  to authenticate user
        # and if we are here, the user is authenticated, so we can return SUCCESS_AUTH
        return types.auth.AuthenticationResult(types.auth.AuthenticationState.SUCCESS, username=username)

    def _process_token_open_id(
        self, token_id: str, nonce: str, gm: 'auths.GroupsManager'
    ) -> types.auth.AuthenticationResult:
        # Get token headers, to extract algorithm
        info = jwt.get_unverified_header(token_id)
        logger.debug('Token headers: %s', info)

        # We may have multiple public keys, try them all
        # (We should only have one, but just in case)
        for key in self._get_public_keys():
            logger.debug('Key = %s', key)
            try:
                payload = jwt.decode(token, key=key, audience=self.client_id.value, algorithms=[info.get('alg', 'RSA256')])  # type: ignore
                # If reaches here, token is valid, raises jwt.InvalidTokenError otherwise
                logger.debug('Payload: %s', payload)
                if payload.get('nonce') != nonce:
                    logger.error('Nonce does not match: %s != %s', payload.get('nonce'), nonce)
                else:
                    logger.debug('Payload: %s', payload)
                    # All is fine, get user & look for groups

                # Process attributes from payload
                return self._process_token(payload, gm)
            except (jwt.InvalidTokenError, IndexError):
                # logger.debug('Data was invalid: %s', e)
                pass
            except Exception as e:
                logger.error('Error decoding token: %s', e)
                return types.auth.FAILED_AUTH

        # All keys tested, none worked
        logger.error('Invalid token received on OAuth2 callback')

        return types.auth.FAILED_AUTH

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        if not values:
            return

        if ' ' in values['name']:
            raise exceptions.ui.ValidationError(
                gettext('This kind of Authenticator does not support white spaces on field NAME')
            )

        auth_utils.validate_regex_field(self.username_attr)
        auth_utils.validate_regex_field(self.username_attr)

        if self.response_type.value in ('code', 'pkce', 'openid+code'):
            if self.common_groups.value.strip() == '':
                raise exceptions.ui.ValidationError(
                    gettext('Common groups is required for "code" response types')
                )
            if self.token_endpoint.value.strip() == '':
                raise exceptions.ui.ValidationError(
                    gettext('Token endpoint is required for "code" response types')
                )
            # infoEndpoint will not be necesary if the response of tokenEndpoint contains the user info

        if self.response_type.value == 'openid+token_id':
            # Ensure we have a public key
            if self.public_key.value.strip() == '':
                raise exceptions.ui.ValidationError(
                    gettext('Public key is required for "openid+token_id" response type')
                )

        if self.redirection_endpoint.value.strip() == '' and self.db_obj() and '_request' in values:
            request: 'HttpRequest' = values['_request']
            self.redirection_endpoint.value = request.build_absolute_uri(self.callback_url())

    def auth_callback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        groups_manager: 'auths.GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        match self.response_type.value:
            case 'code' | 'pkce':
                return self.auth_callback_code(parameters, groups_manager, request)
            case 'token':
                return self.auth_callback_token(parameters, groups_manager, request)
            case 'openid+code':
                return self.auth_callback_openid_code(parameters, groups_manager, request)
            case 'openid+token_id':
                return self.authcallback_openid_id_token(parameters, groups_manager, request)
            case _:
                raise Exception('Invalid response type')
        return auths.SUCCESS_AUTH

    def logout(
        self,
        request: 'types.requests.ExtendedHttpRequest',  # pylint: disable=unused-argument
        username: str,  # pylint: disable=unused-argument
    ) -> types.auth.AuthenticationResult:
        return types.auth.SUCCESS_AUTH

    def get_javascript(self, request: 'HttpRequest') -> typing.Optional[str]:
        """
        We will here compose the azure request and send it via http-redirect
        """
        return f'window.location="{self._get_login_url(request)}";'

    def get_groups(self, username: str, groups_manager: 'auths.GroupsManager') -> None:
        data = self.storage.read_pickled(username)
        if not data:
            return
        groups_manager.validate(data[1])

    def get_real_name(self, username: str) -> str:
        data = self.storage.read_pickled(username)
        if not data:
            return username
        return data[0]

    def auth_callback_code(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """Process the callback for code authorization flow"""
        state = parameters.get_params.get('state', '')
        # Remove state from cache
        code_verifier = self.cache.get(state)
        self.cache.remove(state)

        if not state or not code_verifier:
            logger.error('Invalid state received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Get the code
        code = parameters.get_params.get('code', '')
        if code == '':
            logger.error('Invalid code received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Restore code_verifier "none" to None
        if code_verifier == 'none':
            code_verifier = None

        token = self._request_token(code, code_verifier)
        return self._process_token(self._request_info(token), gm)

    def auth_callback_token(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """Process the callback for PKCE authorization flow"""
        state = parameters.get_params.get('state', '')
        stateValue = self.cache.get(state)
        self.cache.remove(state)

        if not state or not stateValue:
            logger.error('Invalid state received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Get the token, token_type, expires
        token = TokenInfo.from_dict(parameters.get_params)
        return self._process_token(self._request_info(token), gm)

    def auth_callback_openid_code(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """Process the callback for OpenID authorization flow"""
        state = parameters.post_params.get('state', '')
        nonce = self.cache.get(state)
        self.cache.remove(state)

        if not state or not nonce:
            logger.error('Invalid state received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Get the code
        code = parameters.post_params.get('code', '')
        if code == '':
            logger.error('Invalid code received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Get the token, token_type, expires
        token = self._request_token(code)

        if not token.id_token:
            logger.error('No id_token received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        return self._process_token_open_id(token.id_token, nonce, gm)

    def authcallback_openid_id_token(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """Process the callback for OpenID authorization flow"""
        state = parameters.post_params.get('state', '')
        nonce = self.cache.get(state)
        self.cache.remove(state)

        if not state or not nonce:
            logger.error('Invalid state received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Get the id_token
        id_token = parameters.post_params.get('id_token', '')
        if id_token == '':
            logger.error('Invalid id_token received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        return self._process_token_open_id(id_token, nonce, gm)
