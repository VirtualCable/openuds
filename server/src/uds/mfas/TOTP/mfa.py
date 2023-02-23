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
@author: Daniel Torregrosa
"""
import typing
import logging
import io
import base64

import pyotp
import qrcode

from django.utils.translation import gettext_noop as _, gettext

from uds import models
from uds.core import mfas
from uds.core.ui import gui

from uds.core.auths import exceptions

if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.util.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class TOTP_MFA(mfas.MFA):
    '''
    Validates OTP challenge against a proper configured Radius Server with OTP
    using 'Access-Challenge' response from Radius Server [RFC2865, RFC5080]
    '''

    typeName = _('TOTP Based MFA')
    typeType = 'TOTP_MFA'
    typeDescription = _('TOTP Based MFA (Google Authenticator, etc)')
    iconFile = 'totp.png'
    cacheTime = 1  # In this MFA type there are not code generation nor sending... so ? 1 minute or too short ?

    issuer = gui.TextField(
        length=64,
        label=_('Issuer'),
        defvalue='UDS Authenticator',
        order=1,
        tooltip=_('Issuer for OTP. Once it\'s created it can\'t be changed'),
        required=True,
        rdonly=True,  # This is not editable, as it is used to generate the QR code. Once generated, it can't be changed
    )

    validWindow = gui.NumericField(
        length=2,
        label=_('Valid Window'),
        defvalue=0,
        minValue=0,
        maxValue=10,
        order=31,
        tooltip=_('Number of valid codes before and after the current one'),
        required=True,
        tab=_('Config'),
    )
    networks = gui.MultiChoiceField(
        label=_('TOTP networks'),
        rdonly=False,
        rows=5,
        order=32,
        tooltip=_('Networks for TOTP authentication choices'),
        required=False,
        tab=_('Config'),
    )

    doNotAskForOTP = gui.ChoiceField(
        label=_('Requre HOTP for users within networks'),
        order=33,
        defaultValue='0',
        tooltip=_('Action for user without defined Radius Challenge'),
        required=True,
        values={
            '0': _('Allow user login (no MFA)'),
            '1': _('Require user to login with MFA'),
        },
        tab=_('Config'),
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        return super().initialize(values)

    @classmethod
    def initClassGui(cls) -> None:
        # Populate the networks list
        cls.networks.setValues(
            [
                gui.choiceItem(v.uuid, v.name)  # type: ignore
                for v in models.Network.objects.all().order_by('name')
            ]
        )

    def emptyIndentifierAllowedToLogin(
        self, request: 'ExtendedHttpRequest'
    ) -> typing.Optional[bool]:
        return None

    def askForOTP(self, request: 'ExtendedHttpRequest') -> bool:
        """
        Check if we need to ask for OTP for a given user

        Returns:
            True if we need to ask for OTP
        """
        def checkIp() -> bool:
            return any(
                i.contains(request.ip)
                for i in models.Network.objects.filter(uuid__in=self.networks.value)
            )

        if self.doNotAskForOTP.value == '0':
            return not checkIp()
        return True

    def label(self) -> str:
        return gettext('Authentication Code')

    def _userData(self, userId: str) -> typing.Tuple[str, bool]:
        # Get data from storage related to this user
        # Data contains the secret and if the user has already logged in already some time
        # so we show the QR code only once
        data: typing.Optional[typing.Tuple[str, bool]] = self.storage.getPickle(userId)
        if data is None:
            data = (pyotp.random_base32(), False)
            self._saveUserData(userId, data)
        return data

    def _saveUserData(self, userId: str, data: typing.Tuple[str, bool]) -> None:
        self.storage.putPickle(userId, data)

    def getTOTP(self, userId: str, username: str) -> pyotp.TOTP:
        return pyotp.TOTP(
            self._userData(userId)[0], issuer=self.issuer.value, name=username
        )

    def html(self, userId: str, request: 'ExtendedHttpRequest', username: str) -> str:
        # Get data from storage related to this user
        secret, qrShown = self._userData(userId)
        if qrShown:
            return _('Enter your authentication code')
        # Compose the QR code from provisioning URI
        totp = self.getTOTP(userId, username)
        uri = totp.provisioning_uri()
        img = qrcode.make(uri)
        imgByteStream = io.BytesIO()
        img.save(imgByteStream, format='PNG')
        # Convert to base64 to be used in html img tag
        imgByteArr = imgByteStream.getvalue()
        imgData = 'data:image/png;base64,' + base64.b64encode(imgByteArr).decode(
            'utf-8'
        )

        # Return HTML code to be shown to user
        return f'''
            <div style="text-align: center;">
                <img src="{imgData}" alt="QR Code" />
            </div>
            <div style="text-align: center;">
                <p>{_('Please, use your Authenticator to add your account. (i.e. Google Authenticator, Authy, ...)')}</p>
            </div>
        '''

    def process(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        validity: typing.Optional[int] = None,
    ) -> 'mfas.MFA.RESULT':
        if self.askForOTP(request) is False:
            return mfas.MFA.RESULT.ALLOWED

        # The data is provided by an external source, so we need to process anything on the request
        return mfas.MFA.RESULT.OK

    def validate(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        code: str,
        validity: typing.Optional[int] = None,
    ) -> None:
        if self.askForOTP(request) is False:
            return

        # Get data from storage related to this user
        secret, qrShown = self._userData(userId)

        # Validate code
        if not self.getTOTP(userId, username).verify(
            code, valid_window=self.validWindow.num()
        ):
            raise exceptions.MFAError(gettext('Invalid code'))

        if qrShown is False:
            self._saveUserData(
                userId, (secret, True)
            )  # Update user data to show QR code only once
