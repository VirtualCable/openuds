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
import collections.abc
import datetime
import urllib.parse
from base64 import b64decode

import defusedxml.ElementTree as etree
import jwt
import requests
from cryptography.x509 import load_pem_x509_certificate
from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _

from uds.core import auths, consts, exceptions, types
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui
from uds.core.util import fields, model, auth as auth_utils

if typing.TYPE_CHECKING:
    from django.http import HttpRequest

    from cryptography.x509 import Certificate

logger = logging.getLogger(__name__)

# Alphabet used for PKCE
PKCE_ALPHABET: typing.Final[str] = string.ascii_letters + string.digits + '-._~'
# Length of the State parameter
STATE_LENGTH: typing.Final[int] = 16


class TokenInfo(typing.NamedTuple):
    access_token: str
    token_type: str
    expires: datetime.datetime
    refresh_token: str
    scope: str
    info: dict[str, typing.Any]
    id_token: typing.Optional[str]

    @staticmethod
    def fromJson(json: dict[str, typing.Any]) -> 'TokenInfo':
        # expires is -10 to avoid problems with clock sync
        return TokenInfo(
            access_token=json['access_token'],
            token_type=json['token_type'],
            expires=model.getSqlDatetime() + datetime.timedelta(seconds=json['expires_in'] - 10),
            refresh_token=json['refresh_token'],
            scope=json['scope'],
            info=json.get('info', {}),
            id_token=json.get('id_token', None),
        )


class OAuth2Authenticator(auths.Authenticator):
    """
    This class represents an OAuth2 Authenticator.
    """

    typeName = _('OAuth2 Authenticator')
    typeType = 'OAuth2Authenticator'
    typeDescription = _('OAuth2 Authenticator')
    iconFile = 'oauth2.png'

    authorizationEndpoint = gui.TextField(
        length=64,
        label=_('Authorization endpoint'),
        order=10,
        tooltip=_('Authorization endpoint for OAuth2.'),
        required=True,
        tab=_('Server'),
    )
    clientId = gui.TextField(
        length=64,
        label=_('Client ID'),
        order=2,
        tooltip=_('Obtained from App created on Azure for UDS Enterprise'),
        required=True,
        tab=_('Server'),
    )
    clientSecret = gui.TextField(
        length=64,
        label=_('Client Secret'),
        order=3,
        tooltip=_('Obtained from App created on Azure for UDS Enteprise - Keys'),
        required=True,
        tab=_('Server'),
    )
    scope = gui.TextField(
        length=64,
        label=_('Scope'),
        order=4,
        tooltip=_('Scope for OAuth2.'),
        required=True,
        tab=_('Server'),
    )
    commonGroups = gui.TextField(
        length=64,
        label=_('Common Groups'),
        order=5,
        tooltip=_('User will be assigned to this groups once authenticated. Comma separated list of groups'),
        required=False,
        tab=_('Server'),
    )

    # Advanced options
    redirectionEndpoint = gui.TextField(
        length=64,
        label=_('Redirection endpoint'),
        order=90,
        tooltip=_('Redirection endpoint for OAuth2.  (Filled by UDS)'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    responseType = gui.ChoiceField(
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
    tokenEndpoint = gui.TextField(
        length=64,
        label=_('Token endpoint'),
        order=92,
        tooltip=_('Token endpoint for OAuth2. Only required for "code" response type.'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    infoEndpoint = gui.TextField(
        length=64,
        label=_('User information endpoint'),
        order=93,
        tooltip=_('User information endpoint for OAuth2. Only required for "code" response type.'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    publicKey = gui.TextField(
        length=16384,
        lines=3,
        label=_('Public Key'),
        order=94,
        tooltip=_('Provided by Oauth2 provider'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )

    userNameAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('User name attrs'),
        order=100,
        tooltip=_('Fields from where to extract user name'),
        required=True,
        tab=_('Attributes'),
    )

    groupNameAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('Group name attrs'),
        order=101,
        tooltip=_('Fields from where to extract the groups'),
        required=False,
        tab=_('Attributes'),
    )

    realNameAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('Real name attrs'),
        order=102,
        tooltip=_('Fields from where to extract the real name'),
        required=False,
        tab=_('Attributes'),
    )

    def _getPublicKeys(self) -> list[typing.Any]:  # In fact, any of the PublicKey types
        # Get certificates in self.publicKey.value, encoded as PEM
        # Return a list of certificates in DER format
        if self.publicKey.value.strip() == '':
            return []

        return [cert.public_key() for cert in fields.getCertificatesFromField(self.publicKey)]

    def _codeVerifierAndChallenge(self) -> typing.Tuple[str, str]:
        """Generate a code verifier and a code challenge for PKCE

        Returns:
            typing.Tuple[str, str]: Code verifier and code challenge
        """
        codeVerifier = ''.join(secrets.choice(PKCE_ALPHABET) for _ in range(128))
        codeChallenge = (
            b64decode(hashlib.sha256(codeVerifier.encode('ascii')).digest(), altchars=b'-_')
            .decode()
            .rstrip('=')  # remove padding
        )

        return codeVerifier, codeChallenge

    def _getResponseTypeString(self) -> str:
        match self.responseType.value:
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

    def _getLoginURL(self, request: 'HttpRequest') -> str:
        """
        :type request: django.http.request.HttpRequest
        """
        state: str = secrets.token_urlsafe(STATE_LENGTH)

        param_dict = {
            'response_type': self._getResponseTypeString(),
            'client_id': self.clientId.value,
            'redirect_uri': self.redirectionEndpoint.value,
            'scope': self.scope.value.replace(',', ' '),
            'state': state,
        }

        match self.responseType.value:
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
                codeVerifier, codeChallenge = self._codeVerifierAndChallenge()
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

        return self.authorizationEndpoint.value + '?' + params

    def _requestToken(self, code: str, code_verifier: typing.Optional[str] = None) -> TokenInfo:
        """Request a token from the token endpoint using the code received from the authorization endpoint

        Args:
            code (str): Code received from the authorization endpoint

        Returns:
            TokenInfo: Token received from the token endpoint
        """
        param_dict = {
            'grant_type': 'authorization_code',
            'client_id': self.clientId.value,
            'client_secret': self.clientSecret.value,
            'redirect_uri': self.redirectionEndpoint.value,
            'code': code,
        }
        if code_verifier:
            param_dict['code_verifier'] = code_verifier

        req = requests.post(self.tokenEndpoint.value, data=param_dict, timeout=consts.system.COMMS_TIMEOUT)
        logger.debug('Token request: %s %s', req.status_code, req.text)

        if not req.ok:
            raise Exception('Error requesting token: {}'.format(req.text))

        return TokenInfo.fromJson(req.json())

    def _requestInfo(self, token: 'TokenInfo') -> dict[str, typing.Any]:
        """Request user info from the info endpoint using the token received from the token endpoint

        If the token endpoint returns the user info, this method will not be used

        Args:
            token (TokenInfo): Token received from the token endpoint

        Returns:
            dict[str, typing.Any]: User info received from the info endpoint
        """
        userInfo: dict[str, typing.Any]

        if self.infoEndpoint.value.strip() == '':
            if not token.info:
                raise Exception('No user info received')
            userInfo = token.info
        else:
            # Get user info
            req = requests.get(
                self.infoEndpoint.value,
                headers={'Authorization': 'Bearer ' + token.access_token},
                timeout=consts.system.COMMS_TIMEOUT,
            )
            logger.debug('User info request: %s %s', req.status_code, req.text)

            if not req.ok:
                raise Exception('Error requesting user info: {}'.format(req.text))

            userInfo = req.json()
        return userInfo

    def _processToken(
        self, userInfo: typing.Mapping[str, typing.Any], gm: 'auths.GroupsManager'
    ) -> types.auth.AuthenticationResult:
        # After this point, we don't mind about the token, we only need to authenticate user
        # and get some basic info from it

        username = ''.join(auth_utils.processRegexField(self.userNameAttr.value, userInfo)).replace(' ', '_')
        if len(username) == 0:
            raise Exception('No username received')

        realName = ''.join(auth_utils.processRegexField(self.realNameAttr.value, userInfo))

        # Get groups
        groups = auth_utils.processRegexField(self.groupNameAttr.value, userInfo)
        # Append common groups
        groups.extend(self.commonGroups.value.split(','))

        # store groups for this username at storage, so we can check it at a later stage
        self.storage.putPickle(username, [realName, groups])

        # Validate common groups
        gm.validate(groups)

        # We don't mind about the token, we only need  to authenticate user
        # and if we are here, the user is authenticated, so we can return SUCCESS_AUTH
        return types.auth.AuthenticationResult(types.auth.AuthenticationState.SUCCESS, username=username)

    def _processTokenOpenId(
        self, token_id: str, nonce: str, gm: 'auths.GroupsManager'
    ) -> types.auth.AuthenticationResult:
        # Get token headers, to extract algorithm
        info = jwt.get_unverified_header(token_id)
        logger.debug('Token headers: %s', info)

        # We may have multiple public keys, try them all
        # (We should only have one, but just in case)
        for key in self._getPublicKeys():
            logger.debug('Key = %s', key)
            try:
                payload = jwt.decode(token, key=key, audience=self.clientId.value, algorithms=[info.get('alg', 'RSA256')])  # type: ignore
                # If reaches here, token is valid, raises jwt.InvalidTokenError otherwise
                logger.debug('Payload: %s', payload)
                if payload.get('nonce') != nonce:
                    logger.error('Nonce does not match: %s != %s', payload.get('nonce'), nonce)
                else:
                    logger.debug('Payload: %s', payload)
                    # All is fine, get user & look for groups

                # Process attributes from payload
                return self._processToken(payload, gm)
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
            raise exceptions.validation.ValidationError(
                gettext('This kind of Authenticator does not support white spaces on field NAME')
            )

        auth_utils.validateRegexField(self.userNameAttr)
        auth_utils.validateRegexField(self.userNameAttr)

        if self.responseType.value in ('code', 'pkce', 'openid+code'):
            if self.commonGroups.value.strip() == '':
                raise exceptions.validation.ValidationError(gettext('Common groups is required for "code" response types'))
            if self.tokenEndpoint.value.strip() == '':
                raise exceptions.validation.ValidationError(
                    gettext('Token endpoint is required for "code" response types')
                )
            # infoEndpoint will not be necesary if the response of tokenEndpoint contains the user info

        if self.responseType.value == 'openid+token_id':
            # Ensure we have a public key
            if self.publicKey.value.strip() == '':
                raise exceptions.validation.ValidationError(
                    gettext('Public key is required for "openid+token_id" response type')
                )

        request: 'HttpRequest' = values['_request']

        if self.redirectionEndpoint.value.strip() == '' and self.dbObj():
            self.redirectionEndpoint.value = request.build_absolute_uri(self.callbackUrl())

    def authCallback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        match self.responseType.value:
            case 'code' | 'pkce':
                return self.authCallbackCode(parameters, gm, request)
            case 'token':
                return self.authCallbackToken(parameters, gm, request)
            case 'openid+code':
                return self.authCallbackOpenIdCode(parameters, gm, request)
            case 'openid+token_id':
                return self.authCallbackOpenIdIdToken(parameters, gm, request)
            case _:
                raise Exception('Invalid response type')
        return auths.SUCCESS_AUTH

    def logout(
        self,
        request: 'types.request.ExtendedHttpRequest',  # pylint: disable=unused-argument
        username: str,  # pylint: disable=unused-argument
    ) -> types.auth.AuthenticationResult:
        return types.auth.SUCCESS_AUTH

    def getJavascript(self, request: 'HttpRequest') -> typing.Optional[str]:
        """
        We will here compose the azure request and send it via http-redirect
        """
        return f'window.location="{self._getLoginURL(request)}";'

    def getGroups(self, username: str, groupsManager: 'auths.GroupsManager'):
        data = self.storage.getPickle(username)
        if not data:
            return
        groupsManager.validate(data[1])

    def getRealName(self, username: str) -> str:
        data = self.storage.getPickle(username)
        if not data:
            return username
        return data[0]

    def authCallbackCode(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
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

        token = self._requestToken(code, code_verifier)
        return self._processToken(self._requestInfo(token), gm)

    def authCallbackToken(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """Process the callback for PKCE authorization flow"""
        state = parameters.get_params.get('state', '')
        stateValue = self.cache.get(state)
        self.cache.remove(state)

        if not state or not stateValue:
            logger.error('Invalid state received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        # Get the token, token_type, expires
        token = TokenInfo(
            access_token=parameters.get_params.get('access_token', ''),
            token_type=parameters.get_params.get('token_type', ''),
            expires=model.getSqlDatetime()
            + datetime.timedelta(seconds=int(parameters.get_params.get('expires_in', 0))),
            refresh_token=parameters.get_params.get('refresh_token', ''),
            scope=parameters.get_params.get('scope', ''),
            info={},
            id_token=None,
        )
        return self._processToken(self._requestInfo(token), gm)

    def authCallbackOpenIdCode(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
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
        token = self._requestToken(code)

        if not token.id_token:
            logger.error('No id_token received on OAuth2 callback')
            return types.auth.FAILED_AUTH

        return self._processTokenOpenId(token.id_token, nonce, gm)

    def authCallbackOpenIdIdToken(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
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

        return self._processTokenOpenId(id_token, nonce, gm)
