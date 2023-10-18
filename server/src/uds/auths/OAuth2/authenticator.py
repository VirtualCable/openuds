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
import typing
import urllib.parse
from base64 import b64decode

from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _

import defusedxml.ElementTree as etree

import jwt

from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_der_x509_certificate

from uds.core import auths, exceptions, types
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui
from uds.web.views import auth

if typing.TYPE_CHECKING:
    from django.http import HttpRequest
    from uds.core.auths.groups_manager import GroupsManager


logger = logging.getLogger(__name__)


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
    )

    clientId = gui.TextField(
        length=64,
        label=_('Client ID'),
        order=2,
        tooltip=_('Obtained from App created on Azure for UDS Enterprise'),
        required=True,
    )
    clientSecret = gui.TextField(
        length=64,
        label=_('Client Secret'),
        order=3,
        tooltip=_('Obtained from App created on Azure for UDS Enteprise - Keys'),
        required=True,
    )
    publicKey = gui.TextField(
        length=16384,
        multiline=6,
        label=_('Public Key'),
        order=4,
        tooltip=_('Provided by Oauth2 provider'),
        required=True,
    )

    redirectionEndpoint = gui.TextField(
        length=64,
        label=_('Redirection endpoint'),
        order=90,
        tooltip=_('Redirection endpoint for OAuth2.  (Filled by UDS, fix this only if necesary!!)'),
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

    def initialize(self, values: typing.Optional[typing.Dict[str, typing.Any]]) -> None:
        if not values:
            return

        if ' ' in values['name']:
            raise exceptions.ValidationError(
                gettext('This kind of Authenticator does not support white spaces on field NAME')
            )
            
        if self.responseType.value == 'code' and self.tokenEndpoint.value.strip() == '':
            raise exceptions.ValidationError(
                gettext('Token endpoint is required for "code" response type')
            )

        request: 'HttpRequest' = values['_request']

        if self.redirectionEndpoint.value.strip() == '' and self.dbObj():
            self.redirectionEndpoint.value = request.build_absolute_uri(self.callbackUrl())

    def _getLoginURL(self, request: 'HttpRequest'):
        """
        :type request: django.http.request.HttpRequest
        """
        nonce: str = CryptoManager.manager().uuid()
        state: str = CryptoManager.manager().uuid()

        self.cache.put(state, nonce, 3600)

        param_dict = {
            'response_type': self.responseType.value,
            'response_mode': 'form_post',
            'scope': 'openid',
            'client_id': self.clientId.value,
            'redirect_uri': self.redirectionEndpoint.value,
            'nonce': nonce,
            'state': state,
        }

        params = urllib.parse.urlencode(param_dict)

        return self.authorizationEndpoint.value + '?' + params

    def authCallback(
        self,
        parameters: typing.Dict[str, typing.Any],
        gm: 'auths.GroupsManager',
        request: 'types.request.ExtendedHttpRequest',
    ) -> auths.AuthenticationResult:
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
