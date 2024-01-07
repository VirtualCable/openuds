# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import collections.abc
import re
import logging

from django.utils.translation import gettext_noop as _, gettext

import requests.auth

from uds import models
from uds.core import mfas
from uds.core.ui import gui
from uds.core.util import security

if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.types.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class SMSMFA(mfas.MFA):
    """
    Simple explnation of this class:

    Basically, this is an interface to sending SMS messages to a phone number with the code to be used in the MFA process.
    The Code will be check by UDS, and is generated also by UDS.

    Basically, we will describe the HTTP Requeset needed to send the SMS, and the response we expect to get.

    Example, we have a service, that provides us a method of sending an SMS with the following:
    * URL: https://myserver.com/sendsms
    * Method: POST
    * content-type: application/x-www-form-urlencoded
    * Parameters: phone={phone}&message={message}
    * Headers:
      - Authorization header: "Auth: 1234567890"
      - Content-Type header: "application/x-www-form-urlencoded"
      - NonsenseExtraHeader: "This is a nonsense example header"

    If sms is sent, the response will be:
    * Status code: 200
    * Content-Type: application/json
    * Content: {"status": "ok"}

    The fields will have the following values:

    sendingUrl: https://myserver.com/sendsms
    ignoreCertificateErrors: False  (check certificate errors)
    sendingMethod: 1 (POST)
    headersParameters:
       Auth: 1234567890
       Content-Type: application/x-www-form-urlencoded
       NonsenseExtraHeader: This is a nonsense example header
    sendingParameters: phone={phone}&message={message}
    encoding: 0 (UTF-8)
    authenticationMethod: 0 (No authentication, already done in the headers field)
    authenticationUserOrToken: (empty)
    authenticationPassword: (empty)
    responseOkRegex: {"status": "ok"}  (This is a regex. Only 2xx,3xx responses will be considered ok)
    responseErrorAction: 1 (Deny login)
    allowLoginWithoutMFA: 1 (If MFA Field (in our example, phone) is not provided, deny login)
    networks: (empty) (If not empty, only users from this networks will be allowed to use this MFA)


    """

    type_name = _('SMS via HTTP')
    type_type = 'smsHttpMFA'
    type_description = _('Simple SMS sending MFA using HTTP/HTTPS')
    icon_file = 'sms.png'

    sendingUrl = gui.TextField(
        length=128,
        label=_('URL pattern for SMS sending'),
        order=1,
        tooltip=_(
            'URL pattern for SMS sending. It can contain the following '
            'variables:\n'
            '* {code} - the code to send\n'
            '* {phone/+phone} - the phone number\n'
            '* {username} - the username\n'
            '* {justUsername} - the username without @....'
        ),
        required=True,
        tab=_('HTTP Server'),
    )

    ignoreCertificateErrors = gui.CheckBoxField(
        label=_('Ignore certificate errors'),
        order=2,
        default=False,
        tooltip=_(
            'If checked, the server certificate will be ignored. This is '
            'useful if the server uses a self-signed certificate.'
        ),
        tab=_('HTTP Server'),
    )

    sendingMethod = gui.ChoiceField(
        label=_('SMS sending method'),
        order=3,
        tooltip=_('Method for sending SMS'),
        required=True,
        choices=('GET', 'POST', 'PUT'),
        tab=_('HTTP Server'),
    )

    headersParameters = gui.TextField(
        length=4096,
        lines=4,
        label=_('Headers for SMS requests'),
        order=4,
        tooltip=_(
            'Headers for SMS requests. It can contain the following '
            'variables:\n'
            '* {code} - the code to send\n'
            '* {phone/+phone} - the phone number\n'
            '* {username} - the username\n'
            '* {justUsername} - the username without @....\n'
            'Headers are in the form of "Header: Value". (without the quotes)'
        ),
        required=False,
        tab=_('HTTP Server'),
    )

    sendingParameters = gui.TextField(
        length=4096,
        lines=5,
        label=_('Parameters for SMS POST/PUT sending'),
        order=4,
        tooltip=_(
            'Parameters for SMS sending via POST/PUT. It can contain the following '
            'variables:\n'
            '* {code} - the code to send\n'
            '* {phone/+phone} - the phone number\n'
            '* {username} - the username\n'
            '* {justUsername} - the username without @....'
        ),
        required=False,
        tab=_('HTTP Server'),
    )

    encoding = gui.ChoiceField(
        label=_('SMS encoding'),
        default='utf-8',
        order=5,
        tooltip=_('Encoding for SMS'),
        required=True,
        choices=('utf-8', 'utf-16', 'iso-8859-1'),
        tab=_('HTTP Server'),
    )

    authenticationMethod = gui.ChoiceField(
        label=_('SMS authentication method'),
        order=20,
        tooltip=_('Method for sending SMS'),
        required=True,
        choices={
            '0': _('None'),
            '1': _('HTTP Basic Auth'),
            '2': _('HTTP Digest Auth'),
        },
        tab=_('HTTP Authentication'),
    )

    authenticationUserOrToken = gui.TextField(
        length=256,
        label=_('SMS authentication user or token'),
        order=21,
        tooltip=_('User or token for SMS authentication'),
        required=False,
        tab=_('HTTP Authentication'),
    )

    authenticationPassword = gui.PasswordField(
        length=256,
        label=_('SMS authentication password'),
        order=22,
        tooltip=_('Password for SMS authentication'),
        required=False,
        tab=_('HTTP Authentication'),
    )

    responseOkRegex = gui.TextField(
        length=256,
        label=_('SMS response OK regex'),
        order=30,
        tooltip=_('Regex for SMS response OK. If empty, the response is considered OK if status code is 200.'),
        required=False,
        tab=_('HTTP Response'),
    )

    responseErrorAction = gui.ChoiceField(
        label=_('SMS response error action'),
        order=31,
        default='0',
        tooltip=_('Action for SMS response error'),
        required=True,
        choices={
            '0': _('Allow user login'),
            '1': _('Deny user login'),
            '2': _('Allow user to login if its IP is in the networks list'),
            '3': _('Deny user to login if its IP is in the networks list'),
        },
        tab=_('Config'),
    )

    allowLoginWithoutMFA = gui.ChoiceField(
        label=_('User without MFA policy'),
        order=33,
        default='0',
        tooltip=_('Action for SMS response error'),
        required=True,
        choices=mfas.LoginAllowed.choices(),
        tab=_('Config'),
    )

    networks = gui.MultiChoiceField(
        label=_('SMS networks'),
        readonly=False,
        rows=5,
        order=32,
        tooltip=_('Networks for SMS authentication'),
        required=False,
        tab=_('Config'),
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        return super().initialize(values)

    def initGui(self) -> None:
        # Populate the networks list
        self.networks.setChoices(
            [gui.choiceItem(v.uuid, v.name) for v in models.Network.objects.all().order_by('name') if v.uuid]
        )

    def composeSmsUrl(
        self,
        userId: str,  # pylint: disable=unused-argument
        userName: str,
        code: str,
        phone: str,
    ) -> str:
        url = self.sendingUrl.value
        url = url.replace('{code}', code)
        url = url.replace('{phone}', phone.replace('+', ''))
        url = url.replace('{+phone}', phone)
        url = url.replace('{username}', userName)
        url = url.replace('{justUsername}', userName.split('@')[0])
        return url

    def getSession(self) -> requests.Session:
        session = security.secureRequestsSession(verify=self.ignoreCertificateErrors.isTrue())
        # 0 means no authentication
        if self.authenticationMethod.value == '1':
            session.auth = requests.auth.HTTPBasicAuth(
                username=self.authenticationUserOrToken.value,
                password=self.authenticationPassword.value,
            )
        elif self.authenticationMethod.value == '2':
            session.auth = requests.auth.HTTPDigestAuth(
                self.authenticationUserOrToken.value,
                self.authenticationPassword.value,
            )
        # Any other value means no authentication

        # Add headers. Headers are in the form of "Header: Value". (without the quotes)
        if self.headersParameters.value.strip():
            for header in self.headersParameters.value.split('\n'):
                if header.strip():
                    headerName, headerValue = header.split(':', 1)
                    session.headers[headerName.strip()] = headerValue.strip()
        return session

    def allow_login_without_identifier(self, request: 'ExtendedHttpRequest') -> typing.Optional[bool]:
        return mfas.LoginAllowed.check_action(self.allowLoginWithoutMFA.value, request, self.networks.value)

    def processResponse(self, request: 'ExtendedHttpRequest', response: requests.Response) -> mfas.MFA.RESULT:
        logger.debug('Response: %s', response)
        if not response.ok:
            logger.warning(
                'SMS sending failed: code: %s, content: %s',
                response.status_code,
                response.text,
            )
            if not mfas.LoginAllowed.check_action(self.responseErrorAction.value, request, self.networks.value):
                raise Exception(_('SMS sending failed'))
            return mfas.MFA.RESULT.ALLOWED  # Allow login, NO MFA code was sent
        if self.responseOkRegex.value.strip():
            logger.debug(
                'Checking response OK regex: %s: (%s)',
                self.responseOkRegex.value,
                re.search(self.responseOkRegex.value, response.text),
            )
            if not re.search(self.responseOkRegex.value, response.text or ''):
                logger.error(
                    'SMS response error: %s',
                    response.text,
                )
                if not mfas.LoginAllowed.check_action(
                    self.responseErrorAction.value, request, self.networks.value
                ):
                    raise Exception(_('SMS response error'))
                return mfas.MFA.RESULT.ALLOWED
        return mfas.MFA.RESULT.OK

    def getData(
        self,
        request: 'ExtendedHttpRequest',  # pylint: disable=unused-argument
        userId: str,  # pylint: disable=unused-argument
        username: str,
        url: str,  # pylint: disable=unused-argument
        code: str,
        phone: str,
    ) -> bytes:
        data = ''
        if self.sendingParameters.value:
            data = (
                self.sendingParameters.value.replace('{code}', code)
                .replace('{phone}', phone.replace('+', ''))
                .replace('{+phone}', phone)
                .replace('{username}', username)
                .replace('{justUsername}', username.split('@')[0])
            )
        return data.encode(self.encoding.value)

    def sendSMS_GET(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,  # pylint: disable=unused-argument
        username: str,  # pylint: disable=unused-argument
        url: str,
    ) -> mfas.MFA.RESULT:
        return self.processResponse(request, self.getSession().get(url))

    def sendSMS_POST(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        url: str,
        code: str,
        phone: str,
    ) -> mfas.MFA.RESULT:
        # Compose POST data
        session = self.getSession()
        bdata = self.getData(request, userId, username, url, code, phone)
        # Add content-length header
        session.headers['Content-Length'] = str(len(bdata))

        return self.processResponse(request, session.post(url, data=bdata))

    def sendSMS_PUT(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        url: str,
        code: str,
        phone: str,
    ) -> mfas.MFA.RESULT:
        # Compose POST data
        bdata = self.getData(request, userId, username, url, code, phone)
        return self.processResponse(request, self.getSession().put(url, data=bdata))

    def sendSMS(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        code: str,
        phone: str,
    ) -> mfas.MFA.RESULT:
        url = self.composeSmsUrl(userId, username, code, phone)
        if self.sendingMethod.value == 'GET':
            return self.sendSMS_GET(request, userId, username, url)
        if self.sendingMethod.value == 'POST':
            return self.sendSMS_POST(request, userId, username, url, code, phone)
        if self.sendingMethod.value == 'PUT':
            return self.sendSMS_PUT(request, userId, username, url, code, phone)
        raise Exception('Unknown SMS sending method')

    def label(self) -> str:
        return gettext('MFA Code')

    def html(self, request: 'ExtendedHttpRequest', userId: str, username: str) -> str:
        return gettext('Check your phone. You will receive an SMS with the verification code')

    def send_code(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        code: str,
    ) -> mfas.MFA.RESULT:
        logger.debug(
            'Sending SMS code "%s" for user %s (userId="%s", identifier="%s")',
            code,
            username,
            userId,
            identifier,
        )
        return self.sendSMS(request, userId, username, code, identifier)
