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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl
import typing
import collections.abc
import logging

from django.utils.translation import gettext_noop as _, gettext

from uds import models
from uds.core import mfas, exceptions
from uds.core.mfas.mfa import MFA
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.ui import gui
from uds.core.util import validators, decorators

if typing.TYPE_CHECKING:
    from uds.core.module import Module
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
        choices={
            'tls': _('TLS'),
            'ssl': _('SSL'),
            'none': _('None'),
        },
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
        order=3,
        tooltip=_('Subject of the email'),
        required=True,
        tab=_('Config'),
        old_field_name='emailSubject',
    )

    from_email = gui.TextField(
        length=128,
        label=_('From Email'),
        order=11,
        tooltip=_('Email address that will be used as sender'),
        required=True,
        tab=_('Config'),
        old_field_name='fromEmail',
    )

    enable_html = gui.CheckBoxField(
        label=_('Enable HTML'),
        order=13,
        tooltip=_('Enable HTML in emails'),
        default=True,
        tab=_('Config'),
        old_field_name='enableHTML',
    )

    allow_login_without_mfa = gui.ChoiceField(
        label=_('Policy for users without MFA support'),
        order=31,
        default='0',
        tooltip=_('Action for MFA response error'),
        required=True,
        choices=mfas.LoginAllowed.choices(),
        tab=_('Config'),
        old_field_name='allowLoginWithoutMFA',
    )

    allow_skip_mfa_from_networks = gui.MultiChoiceField(
        label=_('Allow skip MFA from networks'),
        readonly=False,
        rows=5,
        order=32,
        tooltip=_('Users within these networks will not be asked for OTP'),
        required=False,
        choices=lambda: [
            gui.choice_item(v.uuid, v.name)  # type: ignore
            for v in models.Network.objects.all().order_by('name')
        ],
        tab=_('Config'),
    )

    networks = gui.MultiChoiceField(
        label=_('Mail OTP Networks'),
        readonly=False,
        rows=5,
        order=32,
        tooltip=_('Networks for Email OTP authentication'),
        required=False,
        choices=lambda: [
            gui.choice_item(v.uuid, v.name)  # type: ignore
            for v in models.Network.objects.all().order_by('name')
        ],
        tab=_('Config'),
    )

    mail_txt = gui.TextField(
        length=1024,
        label=_('Mail text'),
        order=33,
        lines=4,
        tooltip=_('Text of the email. If empty, a default text will be used')
        + '\n'
        + _('Allowed variables are: ')
        + '{code}, {username}, {justUsername}. {ip}',
        required=True,
        default='',
        tab=_('Config'),
        old_field_name='mailTxt',
    )

    mail_html = gui.TextField(
        length=1024,
        label=_('Mail HTML'),
        order=34,
        lines=4,
        tooltip=_('HTML of the email. If empty, a default HTML will be used')
        + '\n'
        + _('Allowed variables are: ')
        + '\n'
        + '{code}, {username}, {justUsername}, {ip}',
        required=False,
        default='',
        tab=_('Config'),
        old_field_name='mailHtml',
    )

    def initialize(self, values: 'Module.ValuesType' = None):
        """
        We will use the "autosave" feature for form fields
        """
        if not values:
            return

        # check hostname for stmp server si valid and is in the right format
        # that is a hostname or ip address with optional port
        # if hostname is not valid, we will raise an exception
        hostname = self.hostname.as_clean_str()
        if not hostname:
            raise exceptions.ui.ValidationError(_('Invalid SMTP hostname'))

        # Now check is valid format
        if ':' in hostname:
            host, port = validators.validate_host_port(hostname)
            self.hostname.value = f'{host}:{port}'
        else:
            host = self.hostname.as_clean_str()
            self.hostname.value = validators.validate_fqdn(host)

        # now check from email and to email
        self.from_email.value = validators.validate_email(self.from_email.value)

    def html(self, request: 'ExtendedHttpRequest', userId: str, username: str) -> str:
        return gettext('Check your mail. You will receive an email with the verification code')

    def allow_login_without_identifier(self, request: 'ExtendedHttpRequest') -> typing.Optional[bool]:
        return mfas.LoginAllowed.check_action(self.allow_login_without_mfa.value, request, self.networks.value)

    def label(self) -> str:
        return 'OTP received via email'

    @decorators.threaded
    def send_verification_code_thread(self, request: 'ExtendedHttpRequest', identifier: str, code: str) -> None:
        # Send and email with the notification
        with self.login() as smtp:
            try:
                # Create message container
                msg = MIMEMultipart('alternative')
                msg['Subject'] = self.email_subject.as_clean_str()
                msg['From'] = self.from_email.as_clean_str()
                msg['To'] = identifier

                msg.attach(
                    MIMEText(
                        f'A login attemt has been made from {request.ip}.\nTo continue, provide the verification code {code}',
                        'plain',
                    )
                )

                if self.enable_html.value:
                    msg.attach(
                        MIMEText(
                            f'<p>A login attemt has been made from <b>{request.ip}</b>.</p><p>To continue, provide the verification code <b>{code}</b></p>',
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
        userId: str,
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
        host = self.hostname.as_clean_str()
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
        userId: str,
        username: str,
        identifier: str,
        validity: int | None = None,
    ) -> 'mfas.MFA.RESULT':
        # if ip allowed to skip mfa, return allowed
        if mfas.LoginAllowed.check_ip_allowed(request, self.allow_skip_mfa_from_networks.value):
            return mfas.MFA.RESULT.ALLOWED
        return super().process(request, userId, username, identifier, validity)
