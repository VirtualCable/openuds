from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from re import T
import smtplib
import ssl
import typing
import logging

from django.utils.translation import gettext_noop as _

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
        lenth=128,
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

        # Done

    def label(self) -> str:
        return 'OTP received via email'

    @decorators.threaded
    def doSendCode(self, request: 'ExtendedHttpRequest', identifier: str, code: str) -> None:
        # Send and email with the notification
        with self.login() as smtp:
            try:
                # Create message container
                msg = MIMEMultipart('alternative')
                msg['Subject'] = self.emailSubject.cleanStr()
                msg['From'] = self.fromEmail.cleanStr()
                msg['To'] = identifier

                msg.attach(MIMEText(f'A login attemt has been made from {request.ip}.\nTo continue, provide the verification code {code}', 'plain'))

                if self.enableHTML.value:
                    msg.attach(MIMEText(f'<p>A login attemt has been made from <b>{request.ip}</b>.</p><p>To continue, provide the verification code <b>{code}</b></p>', 'html'))

                smtp.sendmail(self.fromEmail.value, identifier, msg.as_string())
            except smtplib.SMTPException as e:
                logger.error('Error sending email: {}'.format(e))
                raise

    def sendCode(self, request: 'ExtendedHttpRequest', userId: str, username: str, identifier: str, code: str) -> mfas.MFA.RESULT:
        self.doSendCode(request, identifier, code,)
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
