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
import re
import token
import typing
import urllib.parse
from base64 import b64decode
from weakref import ref

import defusedxml.ElementTree as etree
import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_der_x509_certificate
from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _

from uds.core import auths, consts, exceptions, types
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui
from uds.core.util import auth as auth_utils

if typing.TYPE_CHECKING:
    from django.http import HttpRequest

    from uds.core.auths.groups_manager import GroupsManager


logger = logging.getLogger(__name__)


class TokenInfo(typing.NamedTuple):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    scope: str
    info: typing.Dict[str, typing.Any]

    @staticmethod
    def fromJson(json: typing.Dict[str, typing.Any]) -> 'TokenInfo':
        return TokenInfo(
            access_token=json['access_token'],
            token_type=json['token_type'],
            expires_in=json['expires_in'],
            refresh_token=json['refresh_token'],
            scope=json['scope'],
            info=json.get('info', {}),
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
            {'id': 'code', 'text': _('Code')},
            {'id': 'token', 'text': _('Token')},
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
    
    # Attributes info fields
    userAttribute = gui.TextField(
        length=64,
        label=_('Username attribute'),
        order=100,
        tooltip=_('Attribute that contains the username'),
        required=True,
        tab=_('Attributes'),
    )
    groupsAttributes = gui.TextField(
        length=64,
        label=_('Groups attribute'),
        order=101,
        tooltip=_('Attribute that contains the groups'),
        required=True,
        tab=_('Attributes'),
    )
    

    def initialize(self, values: typing.Optional[typing.Dict[str, typing.Any]]) -> None:
        if not values:
            return

        if ' ' in values['name']:
            raise exceptions.ValidationError(
                gettext('This kind of Authenticator does not support white spaces on field NAME')
            )
            
        auth_utils.validateRegexField(self.userAttribute)
        auth_utils.validateRegexField(self.userAttribute)
            

        if self.responseType.value == 'code':
            if self.commonGroups.value.strip() == '':
                raise exceptions.ValidationError(gettext('Common groups is required for "code" response type'))
            if self.tokenEndpoint.value.strip() == '':
                raise exceptions.ValidationError(gettext('Token endpoint is required for "code" response type'))
            # infoEndpoint will not be necesary if the response of tokenEndpoint contains the user info

        request: 'HttpRequest' = values['_request']

        if self.redirectionEndpoint.value.strip() == '' and self.dbObj():
            self.redirectionEndpoint.value = request.build_absolute_uri(self.callbackUrl())

    def _getLoginURL(self, request: 'HttpRequest') -> str:
        """
        :type request: django.http.request.HttpRequest
        """
        nonce: str = CryptoManager.manager().uuid()
        state: str = CryptoManager.manager().uuid()

        self.cache.put(state, nonce, 3600)

        param_dict = {
            'response_type': self.responseType.value,
            'scope': self.scope.value,
            'client_id': self.clientId.value,
            'redirect_uri': self.redirectionEndpoint.value,
            'state': state,
        }

        # Nonce only is used
        if False:
            param_dict['nonce'] = nonce

        if False:
            param_dict['response_mode'] = 'form_post'  # ['query', 'fragment', 'form_post']

        params = urllib.parse.urlencode(param_dict)

        return self.authorizationEndpoint.value + '?' + params

    def _requestToken(self, request: 'HttpRequest', code: str) -> TokenInfo:
        param_dict = {
            'grant_type': 'authorization_code',
            'client_id': self.clientId.value,
            'client_secret': self.clientSecret.value,
            'redirect_uri': self.redirectionEndpoint.value,
            'code': code,
        }

        req = requests.post(self.tokenEndpoint.value, data=param_dict, timeout=consts.COMMS_TIMEOUT)

        if not req.ok:
            raise Exception('Error requesting token: {}'.format(req.text))

        return TokenInfo.fromJson(req.json())
    

    def authCallback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
    ) -> auths.AuthenticationResult:
        if self.responseType.value == 'code':
            return self.authCallbackCode(parameters, gm, request)
        return auths.SUCCESS_AUTH

    def logout(
        self,
        request: 'types.request.ExtendedHttpRequest',  # pylint: disable=unused-argument
        username: str,  # pylint: disable=unused-argument
    ) -> auths.AuthenticationResult:
        return auths.SUCCESS_AUTH

    def getJavascript(self, request: 'HttpRequest') -> typing.Optional[str]:
        """
        We will here compose the azure request and send it via http-redirect
        """
        return f'window.location="{self._getLoginURL(request)}";'

    def authCallbackCode(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
    ) -> auths.AuthenticationResult:
        # Check state
        state = parameters.get_params.get('state', '')
        if self.cache.get(state) is None:
            logger.warning('Invalid state received on OAuth2 callback')
            return auths.FAILED_AUTH

        # Remove state from cache
        self.cache.remove(state)

        # Get the code
        code = parameters.get_params.get('code', '')
        if code == '':
            logger.warning('Invalid code received on OAuth2 callback')
            return auths.FAILED_AUTH

        token = self._requestToken(request, code)
        
        userInfo: typing.Dict[str, typing.Any]
        
        if self.infoEndpoint.value.strip() == '':
            if not token.info:
                raise Exception('No user info received')
            userInfo = token.info
        else:
            # Get user info
            req = requests.get(self.infoEndpoint.value, headers={'Authorization': 'Bearer ' + token.access_token}, timeout=consts.COMMS_TIMEOUT)
            if not req.ok:
                raise Exception('Error requesting user info: {}'.format(req.text))
            userInfo = req.json()

        # Validate common groups
        groups = self.commonGroups.value.split(',')
        gm.validate(groups)

        # We don't mind about the token, we only need  to authenticate user
        # and if we are here, the user is authenticated, so we can return SUCCESS_AUTH
        return auths.AuthenticationResult(
            auths.AuthenticationSuccess.OK, username=parameters.get_params.get('username', '')
        )
