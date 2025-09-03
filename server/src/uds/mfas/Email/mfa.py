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

import logging
import smtplib
import ssl
import typing
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _

from uds.core import exceptions, mfas, types
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.ui import gui
from uds.core.util import decorators, fields, validators

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class EmailMFA(mfas.MFA):
    type_name = _('Email Multi Factor')
    type_type = 'emailMFA'
    type_description = _('Email Multi Factor Authenticator')
    icon_file = 'mail.png'

    hostname = gui.TextField(
        length=128,
        label=_('SMTP Host'),
        order=1,
        tooltip=_(
            'SMTP Server hostname or IP address. If you are using a  '
            'non-standard port, add it after a colon, for example: '
            'smtp.gmail.com:587'
        ),
        required=True,
        tab=_('SMTP Server'),
    )

    security = gui.ChoiceField(
        label=_('Security'),
        tooltip=_('Security protocol to use'),
        choices=[
            gui.choice_item('tls', _('TLS')),
            gui.choice_item('ssl', _('SSL')),
            gui.choice_item('none', _('None')),
        ],
        order=2,
        required=True,
        tab=_('SMTP Server'),
    )
    username = gui.TextField(
        length=128,
        label=_('Username'),
        order=9,
        tooltip=_('User with access to SMTP server'),
        required=False,
        default='',
        tab=_('SMTP Server'),
    )
    password = gui.PasswordField(
        length=128,
        label=_('Password'),
        order=10,
        tooltip=_('Password of the user with access to SMTP server'),
        required=False,
        default='',
        tab=_('SMTP Server'),
    )

    email_subject = gui.TextField(
        length=128,
        default='Verification Code',
        label=_('Subject'),
        order=20,
        tooltip=_('Subject of the email'),
        required=True,
        tab=types.ui.Tab.CONFIG,
        old_field_name='emailSubject',
    )

    from_email = gui.TextField(
        length=128,
        label=_('From Email'),
        order=21,
        tooltip=_('Email address that will be used as sender'),
        required=True,
        tab=types.ui.Tab.CONFIG,
        old_field_name='fromEmail',
    )

    enable_html = gui.CheckBoxField(
        label=_('Enable HTML'),
        order=22,
        tooltip=_('Enable HTML in emails'),
        default=True,
        tab=types.ui.Tab.CONFIG,
        old_field_name='enableHTML',
    )

    login_without_mfa_policy = fields.login_without_mfa_policy_field()
    login_without_mfa_policy_networks = fields.login_without_mfa_policy_networks_field()
    allow_skip_mfa_from_networks = fields.allow_skip_mfa_from_networks_field()

    mail_txt = gui.TextField(
        length=1024,
        label=_('Mail text'),
        order=40,
        lines=4,
        tooltip=_('Text of the email. If empty, a default text will be used')
        + '\n'
        + _('Allowed variables are: ')
        + '{code}, {username}, {justUsername}. {ip}',
        required=True,
        default='',
        tab=types.ui.Tab.CONFIG,
        old_field_name='mailTxt',
    )

    mail_html = gui.TextField(
        length=1024,
        label=_('Mail HTML'),
        order=41,
        lines=4,
        tooltip=_('HTML of the email. If empty, a default HTML will be used')
        + '\n'
        + _('Allowed variables are: ')
        + '\n'
        + '{code}, {username}, {justUsername}, {ip}',
        required=False,
        default='',
        tab=types.ui.Tab.CONFIG,
        old_field_name='mailHtml',
    )

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """
        if not values:
            return

        # check hostname for stmp server si valid and is in the right format
        # that is a hostname or ip address with optional port
        # if hostname is not valid, we will raise an exception
        hostname = self.hostname.value.strip()
        if not hostname:
            raise exceptions.ui.ValidationError(_('Invalid SMTP hostname'))

        # Now check is valid format
        if ':' in hostname:
            host, port = validators.validate_host_port(hostname)
            self.hostname.value = f'{host}:{port}'
        else:
            host = self.hostname.value.strip()
            self.hostname.value = validators.validate_fqdn(host)

        # now check from email and to email
        self.from_email.value = validators.validate_email(self.from_email.value)

    def html(self, request: 'ExtendedHttpRequest', userid: str, username: str) -> str:
        return gettext('Check your mail. You will receive an email with the verification code')

    def allow_login_without_identifier(self, request: 'ExtendedHttpRequest') -> typing.Optional[bool]:
        return mfas.LoginAllowed.check_action(
            self.login_without_mfa_policy.value, request, self.login_without_mfa_policy_networks.value
        )

    def label(self) -> str:
        return 'OTP received via email'

    @decorators.threaded
    def send_verification_code_thread(self, request: 'ExtendedHttpRequest', identifier: str, code: str) -> None:
        # Send and email with the notification
        with self.login() as smtp:
            try:
                # Create message container
                msg = MIMEMultipart('alternative')
                msg['Subject'] = self.email_subject.value.strip()
                msg['From'] = self.from_email.value.strip()
                msg['To'] = identifier

                text = self.mail_txt.as_clean_str() or gettext(
                    'A login attemt has been made from {ip} to.\nTo continue, provide the verification code {code}'
                )
                html = self.mail_html.as_clean_str() or gettext(
                    '<p>A login attemt has been made from <b>{ip}</b>.</p><p>To continue, provide the verification code <b>{code}</b></p>'
                )
                username = request.user.name if request.user else ''
                msg.attach(
                    MIMEText(
                        text.format(
                            ip=request.ip, code=code, username=username, justUsername=username.split('@')[0]
                        ),
                        'plain',
                    )
                )

                if self.enable_html.value:
                    msg.attach(
                        MIMEText(
                            html.format(
                                ip=request.ip, code=code, username=username, justUsername=username.split('@')[0]
                            ),
                            'html',
                        )
                    )

                smtp.sendmail(self.from_email.value, identifier, msg.as_string())
            except smtplib.SMTPException as e:
                logger.error('Error sending email: %s', e)
                raise

    def send_code(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        identifier: str,
        code: str,
    ) -> mfas.MFA.RESULT:
        self.send_verification_code_thread(
            request,
            identifier,
            code,
        )
        return mfas.MFA.RESULT.OK

    def login(self) -> smtplib.SMTP:
        """
        Login to SMTP server
        """
        host = self.hostname.value.strip()
        if ':' in host:
            host, ports = host.split(':')
            port = int(ports)
        else:
            port = None

        if self.security.value in ('tls', 'ssl'):
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            if self.security.value == 'tls':
                if port:
                    smtp = smtplib.SMTP(
                        host,
                        port,
                    )
                else:
                    smtp = smtplib.SMTP(host)
                smtp.starttls(context=context)
            else:
                if port:
                    smtp = smtplib.SMTP_SSL(host, port, context=context)
                else:
                    smtp = smtplib.SMTP_SSL(host, context=context)
        else:
            if port:
                smtp = smtplib.SMTP(host, port)
            else:
                smtp = smtplib.SMTP(host)

        if self.username.value and self.password.value:
            smtp.login(self.username.value, self.password.value)

        return smtp

    def process(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        identifier: str,
        validity: int | None = None,
    ) -> 'mfas.MFA.RESULT':
        # if ip allowed to skip mfa, return allowed
        if mfas.LoginAllowed.check_ip_allowed(request, self.allow_skip_mfa_from_networks.value):
            return mfas.MFA.RESULT.ALLOWED
        return super().process(request, userid, username, identifier, validity)
