import typing
import re
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
            '* {username} - the username\n'
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
            '* {username} - the username\n'
            '* {justUsername} - the username without @....\n'
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
            '* {username} - the username\n'
            '* {justUsername} - the username without @....\n'
        ),
        required=False,
        tab=_('HTTP Server'),
    )

    smsEncoding = gui.ChoiceField(
        label=_('SMS encoding'),
        defaultValue='utf-8',
        order=5,
        tooltip=_('Encoding for SMS'),
        required=True,
        tab=_('HTTP Server'),
        values=('utf-8', 'iso-8859-1'),
    )

    smsAuthenticationMethod = gui.ChoiceField(
        label=_('SMS authentication method'),
        order=20,
        tooltip=_('Method for sending SMS'),
        required=True,
        tab=_('HTTP Authentication'),
        values={
            '0': _('None'),
            '1': _('HTTP Basic Auth'),
            '2': _('HTTP Digest Auth'),
        },
    )

    smsAuthenticationUserOrToken = gui.TextField(
        length=256,
        label=_('SMS authentication user or token'),
        order=21,
        tooltip=_('User or token for SMS authentication'),
        required=False,
        tab=_('HTTP Authentication'),
    )

    smsAuthenticationPassword = gui.PasswordField(
        length=256,
        label=_('SMS authentication password'),
        order=22,
        tooltip=_('Password for SMS authentication'),
        required=False,
        tab=_('HTTP Authentication'),
    )

    smsResponseOkRegex = gui.TextField(
        length=256,
        label=_('SMS response OK regex'),
        order=30,
        tooltip=_(
            'Regex for SMS response OK. If emty, the response is considered OK if status code is 200.'
        ),
        required=False,
        tab=_('HTTP Response'),
    )

    smsResponseErrorAction = gui.ChoiceField(
        label=_('SMS response error action'),
        order=31,
        defaultValue='0',
        tooltip=_('Action for SMS response error'),
        required=True,
        tab=_('HTTP Response'),
        values={
            '0': _('Allow user log in without MFA'),
            '1': _('Deny user log in'),
        },
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        return super().initialize(values)

    def composeSmsUrl(self, userId: str, userName: str, code: str, phone: str) -> str:
        url = self.smsSendingUrl.value
        url = url.replace('{code}', code)
        url = url.replace('{phone}', phone.replace('+', ''))
        url = url.replace('{+phone}', phone)
        url = url.replace('{username}', userName)
        url = url.replace('{justUsername}', userName.split('@')[0])
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

    def processResponse(self, response: requests.Response) -> mfas.MFA.RESULT:
        logger.debug('Response: %s', response)
        if not response.ok:
            if self.smsResponseErrorAction.value == '1':
                raise Exception(_('SMS sending failed'))
        elif self.smsResponseOkRegex.value.strip():
            logger.debug('Checking response OK regex: %s: (%s)', self.smsResponseOkRegex.value, re.search(self.smsResponseOkRegex.value, response.text))
            if not re.search(self.smsResponseOkRegex.value, response.text or ''):
                logger.error(
                    'SMS response error: %s',
                    response.text,
                )
                if self.smsResponseErrorAction.value == '1':
                    raise Exception('SMS response error')
            return mfas.MFA.RESULT.ALLOWED
        return mfas.MFA.RESULT.OK

    def sendSMS_GET(self, userId: str, username: str, url: str) -> mfas.MFA.RESULT:
        return self.processResponse(self.getSession().get(url))

    def getData(
        self, userId: str, username: str, url: str, code: str, phone: str
    ) -> bytes:
        data = ''
        if self.smsSendingParameters.value:
            data = (
                self.smsSendingParameters.value.replace('{code}', code)
                .replace('{phone}', phone.replace('+', ''))
                .replace('{+phone}', phone)
                .replace('{username}', username)
                .replace('{justUsername}', username.split('@')[0])
            )
        return data.encode(self.smsEncoding.value)

    def sendSMS_POST(
        self, userId: str, username: str, url: str, code: str, phone: str
    ) -> mfas.MFA.RESULT:
        # Compose POST data
        session = self.getSession()
        bdata = self.getData(userId, username, url, code, phone)
        # Add content-length header
        session.headers['Content-Length'] = str(len(bdata))

        return self.processResponse(session.post(url, data=bdata))

    def sendSMS_PUT(
        self, userId: str, username: str, url: str, code: str, phone: str
    ) -> mfas.MFA.RESULT:
        # Compose POST data
        data = ''
        bdata = self.getData(userId, username, url, code, phone)
        return self.processResponse(self.getSession().put(url, data=bdata))

    def sendSMS(
        self, userId: str, username: str, code: str, phone: str
    ) -> mfas.MFA.RESULT:
        url = self.composeSmsUrl(userId, username, code, phone)
        if self.smsSendingMethod.value == 'GET':
            return self.sendSMS_GET(userId, username, url)
        elif self.smsSendingMethod.value == 'POST':
            return self.sendSMS_POST(userId, username, url, code, phone)
        elif self.smsSendingMethod.value == 'PUT':
            return self.sendSMS_PUT(userId, username, url, code, phone)
        else:
            raise Exception('Unknown SMS sending method')

    def label(self) -> str:
        return gettext('MFA Code')

    def sendCode(
        self, userId: str, username: str, identifier: str, code: str
    ) -> mfas.MFA.RESULT:
        logger.debug(
            'Sending SMS code "%s" for user %s (userId="%s", identifier="%s")',
            code,
            username,
            userId,
            identifier,
        )
        return self.sendSMS(userId, username, code, identifier)
