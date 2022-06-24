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
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import typing

from django.utils.translation import gettext_noop as _

from uds.core import messaging
from uds.core.ui import gui
from uds.core.util import validators


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module

logger = logging.getLogger(__name__)

class EmailNotifier(messaging.Notifier):
    """
    Email notifier
    """

    typeName = _('Email notifications')
    # : Type used internally to identify this provider
    typeType = 'emailNotifications'
    # : Description shown at administration interface for this provider
    typeDescription = _('Email notifications')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    iconFile = 'email.png'

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
        values=[
            gui.choiceItem('tls', _('TLS')),
            gui.choiceItem('ssl', _('SSL')),
            gui.choiceItem('none', _('None')),
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
        defvalue='',
        tab=_('SMTP Server'),
    )
    password = gui.PasswordField(
        lenth=128,
        label=_('Password'),
        order=10,
        tooltip=_('Password of the user with access to SMTP server'),
        required=False,
        defvalue='',
        tab=_('SMTP Server'),
    )

    fromEmail = gui.TextField(
        length=128,
        label=_('From Email'),
        order=11,
        tooltip=_('Email address that will be used as sender'),
        required=True,
        tab=_('Config'),
    )

    toEmail = gui.TextField(
        length=128,
        label=_('To Email'),
        order=12,
        tooltip=_('Email address that will be used as recipient'),
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
            raise messaging.Notifier.ValidationException(_('Invalid SMTP hostname'))

        # Now check is valid format
        if ':' in hostname:
            host, port = validators.validateHostPortPair(hostname)
            self.hostname.value = '{}:{}'.format(host, port)
        else:
            host = self.hostname.cleanStr()
            self.hostname.value = validators.validateHostname(host, 128, asPattern=False)

        # now check from email and to email
        self.fromEmail.value = validators.validateEmail(self.fromEmail.value)
        self.toEmail.value = validators.validateEmail(self.toEmail.value)

        # Done

    def notify(self, group: str, identificator: str, level: messaging.NotificationLevel, message: str) -> None:
        # Send and email with the notification
        with self.login() as smtp:
            try:
                # Create message container
                msg = MIMEMultipart('alternative')
                msg['Subject'] = '{} - {}'.format(group, identificator)
                msg['From'] = self.fromEmail.value
                msg['To'] = self.toEmail.value

                part1 = MIMEText(message, 'plain')
                part2 = MIMEText(message, 'html')

                msg.attach(part1)

                if self.enableHTML.value:
                    msg.attach(part2)
                
                smtp.sendmail(self.fromEmail.value, self.toEmail.value, msg.as_string())
            except smtplib.SMTPException as e:
                logger.error('Error sending email: {}'.format(e))



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
                    smtp = smtplib.SMTP(host, port,)
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
