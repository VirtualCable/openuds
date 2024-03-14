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
import logging
import io
import base64

import pyotp
import qrcode

from django.utils.translation import gettext_noop as _, gettext

from uds import models
from uds.core.util.model import sql_datetime
from uds.core import mfas, exceptions, types
from uds.core.ui import gui

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest

logger = logging.getLogger(__name__)

TOTP_INTERVAL = 30  # Seconds between codes


class TOTP_MFA(mfas.MFA):
    '''
    Validates OTP challenge against a proper configured Radius Server with OTP
    using 'Access-Challenge' response from Radius Server [RFC2865, RFC5080]
    '''

    type_name = _('TOTP Based MFA')
    type_type = 'TOTP_MFA'
    type_description = _('TOTP Based MFA (Google Authenticator, etc)')
    icon_file = 'totp.png'

    issuer = gui.TextField(
        length=64,
        label=_('Issuer'),
        default='UDS Authenticator',
        order=1,
        tooltip=_('Issuer for OTP. Once it\'s created it can\'t be changed'),
        required=True,
        readonly=True,  # This is not editable, as it is used to generate the QR code. Once generated, it can't be changed
    )

    valid_window = gui.NumericField(
        length=2,
        label=_('Valid Window'),
        default=1,
        min_value=0,
        max_value=10,
        order=31,
        tooltip=_('Number of valid codes before and after the current one'),
        required=True,
        tab=_('Config'),
        old_field_name='validWindow',
    )
    networks = gui.MultiChoiceField(
        label=_('TOTP networks'),
        readonly=False,
        rows=5,
        order=32,
        tooltip=_('Users within these networks will not be asked for OTP'),
        required=False,
        choices=lambda: [
            gui.choice_item(v.uuid, v.name)
            for v in models.Network.objects.all().order_by('name')
        ],
        tab=_('Config'),
    )

    def initialize(self, values: 'types.core.ValuesType') -> None:
        return super().initialize(values)

    def allow_login_without_identifier(self, request: 'ExtendedHttpRequest') -> typing.Optional[bool]:
        return None

    def ask_for_otp(self, request: 'ExtendedHttpRequest') -> bool:
        """
        Check if we need to ask for OTP for a given user

        Returns:
            True if we need to ask for OTP
        """

        return not any(request.ip in i for i in models.Network.objects.filter(uuid__in=self.networks.value))

    def label(self) -> str:
        return gettext('Authentication Code')

    def _user_data(self, userId: str) -> tuple[str, bool]:
        # Get data from storage related to this user
        # Data contains the secret and if the user has already logged in already some time
        # so we show the QR code only once
        data: typing.Optional[tuple[str, bool]] = self.storage.read_pickled(userId)
        if data is None:
            data = (pyotp.random_base32(), False)
            self._save_user_data(userId, data)
        return data

    def _save_user_data(self, userId: str, data: tuple[str, bool]) -> None:
        self.storage.save_pickled(userId, data)

    def _remove_user_data(self, userId: str) -> None:
        self.storage.remove(userId)

    def get_totp(self, userId: str, username: str) -> pyotp.TOTP:
        return pyotp.TOTP(
            self._user_data(userId)[0],
            issuer=self.issuer.value,
            name=username,
            interval=TOTP_INTERVAL,
        )

    def html(self, request: 'ExtendedHttpRequest', userId: str, username: str) -> str:
        # Get data from storage related to this user
        qrShown = self._user_data(userId)[1]
        if qrShown:
            return _('Enter your authentication code')
        # Compose the QR code from provisioning URI
        totp = self.get_totp(userId, username)
        uri = totp.provisioning_uri()
        img: bytes = qrcode.make(uri)  # pyright: ignore
        imgByteStream = io.BytesIO()
        img.save(imgByteStream, format='PNG')  # type: ignore  # pylance complains abot format, but it is ok
        # Convert to base64 to be used in html img tag
        imgByteArr = imgByteStream.getvalue()
        imgData = 'data:image/png;base64,' + base64.b64encode(imgByteArr).decode('utf-8')

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
        if self.ask_for_otp(request) is False:
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
        if self.ask_for_otp(request) is False:
            return

        if self.cache.get(userId + code) is not None:
            raise exceptions.auth.MFAError(gettext('Code is already used. Wait a minute and try again.'))

        # Get data from storage related to this user
        secret, qrShown = self._user_data(userId)

        # Validate code
        if not self.get_totp(userId, username).verify(
            code, valid_window=self.valid_window.as_int(), for_time=sql_datetime()
        ):
            raise exceptions.auth.MFAError(gettext('Invalid code'))

        self.cache.put(userId + code, True, self.valid_window.as_int() * (TOTP_INTERVAL + 1))

        if qrShown is False:
            self._save_user_data(userId, (secret, True))  # Update user data to show QR code only once

    def reset_data(self, userId: str) -> None:
        self._remove_user_data(userId)
