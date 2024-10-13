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
import re
import logging

from django.utils.translation import gettext_noop as _, gettext

import requests.auth

from uds import models
from uds.core import mfas, types
from uds.core.ui import gui
from uds.core.util import fields, security

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest

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

    url_pattern: https://myserver.com/sendsms
    ignore_certificate_errors: False  (check certificate errors)
    http_method: 1 (POST)
    headers_parameters:
       Auth: 1234567890
       Content-Type: application/x-www-form-urlencoded
       NonsenseExtraHeader: This is a nonsense example header
    parameters: phone={phone}&message={message}
    encoding: 0 (UTF-8)
    auth_method: 0 (No authentication, already done in the headers field)
    auth_user_or_token: (empty)
    auth_password: (empty)
    valid_response_re: {"status": "ok"}  (This is a regex. Only 2xx,3xx responses will be considered ok)
    response_error_action: 1 (Deny login)
    login_without_mfa_policy: 1 (If MFA Field (in our example, phone) is not provided, deny login)

    # following fields are not used in this example
    login_without_mfa_policy_networks
    allow_skip_mfa_from_networks
    """

    type_name = _('SMS via HTTP')
    type_type = 'smsHttpMFA'
    type_description = _('Simple SMS sending MFA using HTTP/HTTPS')
    icon_file = 'sms.png'

    url_pattern = gui.TextField(
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
        old_field_name='sendingUrl',
    )

    ignore_certificate_errors = gui.CheckBoxField(
        label=_('Ignore certificate errors'),
        order=2,
        default=False,
        tooltip=_(
            'If checked, the server certificate will be ignored. This is '
            'useful if the server uses a self-signed certificate.'
        ),
        tab=_('HTTP Server'),
        old_field_name='ignoreCertificateErrors',
    )

    http_method = gui.ChoiceField(
        label=_('SMS sending method'),
        order=3,
        tooltip=_('Method for sending SMS'),
        required=True,
        choices=('GET', 'POST', 'PUT'),
        tab=_('HTTP Server'),
        old_field_name='sendingMethod',
    )

    headers_parameters = gui.TextField(
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
        old_field_name='headersParameters',
    )

    parameters = gui.TextField(
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
        old_field_name='sendingParameters',
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

    auth_method = gui.ChoiceField(
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
        old_field_name='authenticationMethod',
    )

    auth_user_or_token = gui.TextField(
        length=256,
        label=_('SMS authentication user or token'),
        order=21,
        tooltip=_('User or token for SMS authentication'),
        required=False,
        tab=_('HTTP Authentication'),
        old_field_name='authenticationUserOrToken',
    )

    auth_password = gui.PasswordField(
        length=256,
        label=_('SMS authentication password'),
        order=22,
        tooltip=_('Password for SMS authentication'),
        required=False,
        tab=_('HTTP Authentication'),
    )

    valid_response_re = gui.TextField(
        length=256,
        label=_('SMS response OK regex'),
        order=30,
        tooltip=_('Regex for SMS response OK. If empty, the response is considered OK if status code is 200.'),
        required=False,
        tab=_('HTTP Response'),
        old_field_name='responseOkRegex',
    )

    response_error_action = gui.ChoiceField(
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
        tab=types.ui.Tab.CONFIG,
        old_field_name='responseErrorAction',
    )

    login_without_mfa_policy = fields.login_without_mfa_policy_field()
    login_without_mfa_policy_networks = fields.login_without_mfa_policy_networks_field()
    allow_skip_mfa_from_networks = fields.allow_skip_mfa_from_networks_field()

    def initialize(self, values: 'types.core.ValuesType') -> None:
        return super().initialize(values)

    def build_sms_url(
        self,
        userid: str,  # pylint: disable=unused-argument
        username: str,
        code: str,
        phone: str,
    ) -> str:
        url = self.url_pattern.value
        url = url.replace('{code}', code)
        url = url.replace('{phone}', phone.replace('+', ''))
        url = url.replace('{+phone}', phone)
        url = url.replace('{username}', username)
        url = url.replace('{justUsername}', username.split('@')[0])
        return url

    def ask_for_otp(self, request: 'ExtendedHttpRequest') -> bool:
        """
        Check if we need to ask for OTP for a given user

        Returns:
            True if we need to ask for OTP
        """
        return not any(
            request.ip in i
            for i in models.Network.objects.filter(uuid__in=self.login_without_mfa_policy_networks.value)
        )

    def get_session(self) -> requests.Session:
        session = security.secure_requests_session(verify=self.ignore_certificate_errors.as_bool())
        # 0 means no authentication
        if self.auth_method.value == '1':
            session.auth = requests.auth.HTTPBasicAuth(
                username=self.auth_user_or_token.value,
                password=self.auth_password.value,
            )
        elif self.auth_method.value == '2':
            session.auth = requests.auth.HTTPDigestAuth(
                self.auth_user_or_token.value,
                self.auth_password.value,
            )
        # Any other value means no authentication

        # Add headers. Headers are in the form of "Header: Value". (without the quotes)
        if self.headers_parameters.value.strip():
            for header in self.headers_parameters.value.split('\n'):
                if header.strip():
                    header_name, header_value = header.split(':', 1)
                    session.headers[header_name.strip()] = header_value.strip()
        return session

    def allow_login_without_identifier(self, request: 'ExtendedHttpRequest') -> typing.Optional[bool]:
        return mfas.LoginAllowed.check_action(
            self.login_without_mfa_policy.value, request, self.login_without_mfa_policy_networks.value
        )

    def process(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        identifier: str,
        validity: typing.Optional[int] = None,
    ) -> 'mfas.MFA.RESULT':
        # if ip allowed to skip mfa, return allowed
        if mfas.LoginAllowed.check_ip_allowed(request, self.allow_skip_mfa_from_networks.value):
            return mfas.MFA.RESULT.ALLOWED

        return super().process(request, userid, username, identifier, validity)

    def process_response(self, request: 'ExtendedHttpRequest', response: requests.Response) -> mfas.MFA.RESULT:
        logger.debug('Response: %s', response)
        if not response.ok:
            logger.warning(
                'SMS sending failed: code: %s, content: %s',
                response.status_code,
                response.text,
            )
            if not mfas.LoginAllowed.check_action(
                self.response_error_action.value, request, self.login_without_mfa_policy_networks.value
            ):
                raise Exception(_('SMS sending failed'))
            return mfas.MFA.RESULT.ALLOWED  # Allow login, NO MFA code was sent
        if self.valid_response_re.value.strip():
            logger.debug(
                'Checking response OK regex: %s: (%s)',
                self.valid_response_re.value,
                re.search(self.valid_response_re.value, response.text),
            )
            if not re.search(self.valid_response_re.value, response.text or ''):
                logger.error(
                    'SMS response error: %s',
                    response.text,
                )
                if not mfas.LoginAllowed.check_action(
                    self.response_error_action.value, request, self.login_without_mfa_policy_networks.value
                ):
                    raise Exception(_('SMS response error'))
                return mfas.MFA.RESULT.ALLOWED
        return mfas.MFA.RESULT.OK

    def _build_data(
        self,
        request: 'ExtendedHttpRequest',  # pylint: disable=unused-argument
        userid: str,  # pylint: disable=unused-argument
        username: str,
        url: str,  # pylint: disable=unused-argument
        code: str,
        phone: str,
    ) -> bytes:
        data = ''
        if self.parameters.value:
            data = (
                self.parameters.value.replace('{code}', code)
                .replace('{phone}', phone.replace('+', ''))
                .replace('{+phone}', phone)
                .replace('{username}', username)
                .replace('{justUsername}', username.split('@')[0])
            )
        return data.encode(self.encoding.value)

    def _send_sms_using_get(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,  # pylint: disable=unused-argument
        username: str,  # pylint: disable=unused-argument
        url: str,
    ) -> mfas.MFA.RESULT:
        return self.process_response(request, self.get_session().get(url))

    def _send_sms_using_post(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        url: str,
        code: str,
        phone: str,
    ) -> mfas.MFA.RESULT:
        # Compose POST data
        session = self.get_session()
        bdata = self._build_data(request, userid, username, url, code, phone)
        # Add content-length header
        session.headers['Content-Length'] = str(len(bdata))

        return self.process_response(request, session.post(url, data=bdata))

    def _send_sms_using_put(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        url: str,
        code: str,
        phone: str,
    ) -> mfas.MFA.RESULT:
        # Compose POST data
        bdata = self._build_data(request, userid, username, url, code, phone)
        return self.process_response(request, self.get_session().put(url, data=bdata))

    def _send_sms(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        code: str,
        phone: str,
    ) -> mfas.MFA.RESULT:
        url = self.build_sms_url(userid, username, code, phone)
        if self.http_method.value == 'GET':
            return self._send_sms_using_get(request, userid, username, url)
        if self.http_method.value == 'POST':
            return self._send_sms_using_post(request, userid, username, url, code, phone)
        if self.http_method.value == 'PUT':
            return self._send_sms_using_put(request, userid, username, url, code, phone)
        raise Exception('Unknown SMS sending method')

    def label(self) -> str:
        return gettext('MFA Code')

    def html(self, request: 'ExtendedHttpRequest', userid: str, username: str) -> str:
        return gettext('Check your phone. You will receive an SMS with the verification code')

    def send_code(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        identifier: str,
        code: str,
    ) -> mfas.MFA.RESULT:
        logger.debug(
            'Sending SMS code "%s" for user %s (userid="%s", identifier="%s")',
            code,
            username,
            userid,
            identifier,
        )
        return self._send_sms(request, userid, username, code, identifier)
