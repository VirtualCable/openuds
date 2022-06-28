import typing
import logging

from django.utils.translation import gettext_noop as _, gettext
import requests
import requests.auth

from uds.core import mfas
from uds.core.ui import gui

if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class SMSMFA(mfas.MFA):
    typeName = _('SMS Thought HTTP')
    typeType = 'smsHttpMFA'
    typeDescription = _('Simple SMS sending MFA using HTTP')
    iconFile = 'sms.png'

    smsSendingUrl = gui.TextField(
        length=128,
        label=_('URL pattern for SMS sending'),
        order=1,
        tooltip=_(
            'URL pattern for SMS sending. It can contain the following '
            'variables:\n'
            '* {code} - the code to send\n'
            '* {phone/+phone} - the phone number\n'
        ),
        required=True,
        tab=_('HTTP Server'),
    )

    ignoreCertificateErrors = gui.CheckBoxField(
        label=_('Ignore certificate errors'),
        order=2,
        tab=_('HTTP Server'),
        defvalue=False,
        tooltip=_(
            'If checked, the server certificate will be ignored. This is '
            'useful if the server uses a self-signed certificate.'
        ),
    )

    smsSendingMethod = gui.ChoiceField(
        label=_('SMS sending method'),
        order=3,
        tooltip=_('Method for sending SMS'),
        required=True,
        tab=_('HTTP Server'),
        values=('GET', 'POST', 'PUT'),
    )

    smsHeadersParameters = gui.TextField(
        length=4096,
        multiline=4,
        label=_('Headers for SMS requests'),
        order=4,
        tooltip=_(
            'Headers for SMS requests. It can contain the following '
            'variables:\n'
            '* {code} - the code to send\n'
            '* {phone/+phone} - the phone number\n'
            'Headers are in the form of "Header: Value". (without the quotes)'
        ),
        required=False,
        tab=_('HTTP Server'),
    )

    smsSendingParameters = gui.TextField(
        length=4096,
        multiline=5,
        label=_('Parameters for SMS POST/PUT sending'),
        order=4,
        tooltip=_(
            'Parameters for SMS sending via POST/PUT. It can contain the following '
            'variables:\n'
            '* {code} - the code to send\n'
            '* {phone/+phone} - the phone number\n'
        ),
        required=False,
        tab=_('HTTP Server'),
    )

    smsAuthenticationMethod = gui.ChoiceField(
        label=_('SMS authentication method'),
        order=6,
        tooltip=_('Method for sending SMS'),
        required=True,
        tab=_('HTTP Server'),
        values={
            '0': _('None'),
            '1': _('HTTP Basic Auth'),
            '2': _('HTTP Digest Auth'),
        },
    )

    smsAuthenticationUserOrToken = gui.TextField(
        length=256,
        label=_('SMS authentication user or token'),
        order=7,
        tooltip=_('User or token for SMS authentication'),
        required=False,
        tab=_('HTTP Server'),
    )

    smsAuthenticationPassword = gui.TextField(
        length=256,
        label=_('SMS authentication password'),
        order=8,
        tooltip=_('Password for SMS authentication'),
        required=False,
        tab=_('HTTP Server'),
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        return super().initialize(values)

    def composeSmsUrl(self, code: str, phone: str) -> str:
        url = self.smsSendingUrl.value
        url = url.replace('{code}', code)
        url = url.replace('{phone}', phone.replace('+', ''))
        url = url.replace('{+phone}', phone)
        return url

    def getSession(self) -> requests.Session:
        session = requests.Session()
        # 0 means no authentication
        if self.smsAuthenticationMethod.value == '1':
            session.auth = requests.auth.HTTPBasicAuth(
                username=self.smsAuthenticationUserOrToken.value,
                password=self.smsAuthenticationPassword.value,
            )
        elif self.smsAuthenticationMethod.value == '2':
            session.auth = requests.auth.HTTPDigestAuth(
                self.smsAuthenticationUserOrToken.value,
                self.smsAuthenticationPassword.value,
            )
        # Any other value means no authentication

        # Add headers. Headers are in the form of "Header: Value". (without the quotes)
        if self.smsHeadersParameters.value.strip():
            for header in self.smsHeadersParameters.value.split('\n'):
                if header.strip():
                    headerName, headerValue = header.split(':', 1)
                    session.headers[headerName.strip()] = headerValue.strip()
        return session

    def sendSMS_GET(self, url: str) -> None:
        response = self.getSession().get(url)
        if response.status_code != 200:
            raise Exception('Error sending SMS: ' + response.text)

    def sendSMS_POST(self, url: str, code: str, phone: str) -> None:
        # Compose POST data
        data = ''
        if self.smsSendingParameters.value:
            data = self.smsSendingParameters.value.replace('{code}', code).replace(
                '{phone}', phone.replace('+', '').replace('{+phone}', phone)
            )
        response = self.getSession().post(url, data=data.encode())
        if response.status_code != 200:
            raise Exception('Error sending SMS: ' + response.text)

    def sendSMS_PUT(self, url: str, code: str, phone: str) -> None:
        # Compose POST data
        data = ''
        if self.smsSendingParameters.value:
            data = self.smsSendingParameters.value.replace('{code}', code).replace(
                '{phone}', phone
            )
        response = self.getSession().put(url, data=data.encode())
        if response.status_code != 200:
            raise Exception('Error sending SMS: ' + response.text)

    def sendSMS(self, code: str, phone: str) -> None:
        url = self.composeSmsUrl(code, phone)
        if self.smsSendingMethod.value == 'GET':
            return self.sendSMS_GET(url)
        elif self.smsSendingMethod.value == 'POST':
            return self.sendSMS_POST(url, code, phone)
        elif self.smsSendingMethod.value == 'PUT':
            return self.sendSMS_PUT(url, code, phone)
        else:
            raise Exception('Unknown SMS sending method')

    def label(self) -> str:
        return gettext('MFA Code')

    def sendCode(self, userId: str, identifier: str, code: str) -> None:
        logger.debug('Sending code: %s', code)
        return
