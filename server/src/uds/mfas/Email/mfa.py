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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
from re import T
import smtplib
import ssl
import typing
import logging

from django.utils.translation import gettext_noop as _, gettext

from uds import models
from uds.core import mfas
from uds.core.ui import gui
from uds.core.util import validators, decorators

if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.util.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class EmailMFA(mfas.MFA):
    typeName = _('Email Multi Factor')
    typeType = 'emailMFA'
    typeDescription = _('Email Multi Factor Authenticator')
    iconFile = 'mail.png'

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
        values={
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
        defvalue='',
        tab=_('SMTP Server'),
    )
    password = gui.PasswordField(
        length=128,
        label=_('Password'),
        order=10,
        tooltip=_('Password of the user with access to SMTP server'),
        required=False,
        defvalue='',
        tab=_('SMTP Server'),
    )

    emailSubject = gui.TextField(
        length=128,
        defvalue='Verification Code',
        label=_('Subject'),
        order=3,
        tooltip=_('Subject of the email'),
        required=True,
        tab=_('Config'),
    )

    fromEmail = gui.TextField(
        length=128,
        label=_('From Email'),
        order=11,
        tooltip=_('Email address that will be used as sender'),
        required=True,
        tab=_('Config'),
    )

    enableHTML = gui.CheckBoxField(
        label=_('Enable HTML'),
        order=13,
        tooltip=_('Enable HTML in emails'),
        defvalue=True,
        tab=_('Config'),
    )

    allowLoginWithoutMFA = gui.ChoiceField(
        label=_('Policy for users without MFA support'),
        order=31,
        defaultValue='0',
        tooltip=_('Action for MFA response error'),
        required=True,
        values={
            '0': _('Allow user login'),
            '1': _('Deny user login'),
            '2': _('Allow user to login if it IP is in the networks list'),
            '3': _('Deny user to login if it IP is in the networks list'),
        },
        tab=_('Config'),
    )

    networks = gui.MultiChoiceField(
        label=_('Mail OTP Networks'),
        rdonly=False,
        rows=5,
        order=32,
        tooltip=_('Networks for Email OTP authentication'),
        required=False,
        tab=_('Config'),
    )

    mailTxt = gui.TextField(
        length=1024,
        label=_('Mail text'),
        order=33,
        multiline=4,
        tooltip=_('Text of the email. If empty, a default text will be used') + '\n' + _('Allowed variables are: ') + '{code}, {username}, {justUsername}. {ip}',
        required=True,
        defvalue='',
        tab=_('Config'),
    )

    mailHtml = gui.TextField(
        length=1024,
        label=_('Mail HTML'),
        order=34,
        multiline=4,
        tooltip=_('HTML of the email. If empty, a default HTML will be used')+ '\n' + _('Allowed variables are: ') + '{code}, {username}, {justUsername}, {ip}',
        required=False,
        defvalue='',
        tab=_('Config'),
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
        hostname = self.hostname.cleanStr()
        if not hostname:
            raise EmailMFA.ValidationException(_('Invalid SMTP hostname'))

        # Now check is valid format
        if ':' in hostname:
            host, port = validators.validateHostPortPair(hostname)
            self.hostname.value = '{}:{}'.format(host, port)
        else:
            host = self.hostname.cleanStr()
            self.hostname.value = validators.validateHostname(
                host, 128, asPattern=False
            )

        # now check from email and to email
        self.fromEmail.value = validators.validateEmail(self.fromEmail.value)

    def html(self, request: 'ExtendedHttpRequest', userId: str, username: str) -> str:
        return gettext(
            'Check your mail. You will receive an email with the verification code'
        )

    @classmethod
    def initClassGui(cls) -> None:
        # Populate the networks list
        cls.networks.setValues(
            [
                gui.choiceItem(v.uuid, v.name)
                for v in models.Network.objects.all().order_by('name')
                if v.uuid
            ]
        )

    def checkAction(self, action: str, request: 'ExtendedHttpRequest') -> bool:
        def checkIp() -> bool:
            return any(
                i.ipInNetwork(request.ip)
                for i in models.Network.objects.filter(uuid__in=self.networks.value)
            )

        if action == '0':
            return True
        elif action == '1':
            return False
        elif action == '2':
            return checkIp()
        elif action == '3':
            return not checkIp()
        else:
            return False

    def emptyIndentifierAllowedToLogin(
        self, request: 'ExtendedHttpRequest'
    ) -> typing.Optional[bool]:
        return self.checkAction(self.allowLoginWithoutMFA.value, request)

    def label(self) -> str:
        return 'OTP received via email'

    @decorators.threaded
    def doSendCode(
        self, request: 'ExtendedHttpRequest', identifier: str, code: str
    ) -> None:
        # Send and email with the notification
        with self.login() as smtp:
            try:
                # Create message container
                msg = MIMEMultipart('alternative')
                msg['Subject'] = self.emailSubject.cleanStr()
                msg['From'] = self.fromEmail.cleanStr()
                msg['To'] = identifier

                text = self.mailTxt.cleanStr() or gettext(
                    'A login attemt has been made from {ip} to.\nTo continue, provide the verification code {code}'
                )
                html = self.mailHtml.cleanStr() or gettext(
                    '<p>A login attemt has been made from <b>{ip}</b>.</p><p>To continue, provide the verification code <b>{code}</b></p>'
                )
                username = request.user.name if request.user else ''
                msg.attach(
                    MIMEText(
                        text.format(ip=request.ip, code=code, username=username, justUsername=username.split('@')[0]),
                        'plain',
                    )
                )

                if self.enableHTML.value:
                    msg.attach(
                        MIMEText(
                            html.format(ip=request.ip, code=code, username=username, justUsername=username.split('@')[0]),
                            'html',
                        )
                    )

                smtp.sendmail(self.fromEmail.value, identifier, msg.as_string())
            except smtplib.SMTPException as e:
                logger.error('Error sending email: {}'.format(e))
                raise

    def sendCode(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        code: str,
    ) -> mfas.MFA.RESULT:
        # If failed to send the code, we will raise the exception
        self.doSendCode(
            request,
            identifier,
            code,
        )
        return mfas.MFA.RESULT.OK

    def login(self) -> smtplib.SMTP:
        """
        Login to SMTP server
        """
        host = self.hostname.cleanStr()
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
