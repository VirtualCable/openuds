# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 Virtual Cable S.L.
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
Author: Janier Rodríguez, jrodriguez at virtualcable dot es
"""
import typing
from unittest import mock

import pyotp

from uds.core import exceptions
from uds.mfas.TOTP.mfa import TOTP_MFA, TOTP_INTERVAL

from ..utils.test import UDSTestCase

LOGGER_NAME: typing.Final[str] = 'uds.mfas.TOTP.mfa'


class TOTPValidateTest(UDSTestCase):
    """
    Validation of TOTP codes and of the traces left to diagnose a rejected one
    """

    secret: str

    def setUp(self) -> None:
        self.secret = pyotp.random_base32()

    def _mfa(self) -> TOTP_MFA:
        mfa = TOTP_MFA(self.create_environment(), None)
        mfa.valid_window.value = 1
        return mfa

    def _request(self) -> typing.Any:
        return mock.MagicMock(ip='127.0.0.1')

    def _current_code(self) -> str:
        return pyotp.TOTP(self.secret, interval=TOTP_INTERVAL).now()

    def test_valid_code_passes_and_is_traced(self) -> None:
        mfa = self._mfa()
        code = self._current_code()

        with mock.patch.object(TOTP_MFA, 'ask_for_otp', return_value=True), mock.patch.object(
            TOTP_MFA, '_user_data', return_value=(self.secret, True)
        ):
            with self.assertLogs(LOGGER_NAME, level='INFO') as logs:
                mfa.validate(self._request(), 'user1', 'user1', 'ident', code)

        self.assertTrue(any('returned [True]' in line for line in logs.output))
        self.assertFalse(any(code in line for line in logs.output), 'The code must never be traced')

    def test_invalid_code_raises_and_is_traced(self) -> None:
        mfa = self._mfa()

        with mock.patch.object(TOTP_MFA, 'ask_for_otp', return_value=True), mock.patch.object(
            TOTP_MFA, '_user_data', return_value=(self.secret, True)
        ):
            with self.assertLogs(LOGGER_NAME, level='INFO') as logs:
                with self.assertRaises(exceptions.auth.MFAError):
                    mfa.validate(self._request(), 'user1', 'user1', 'ident', '000000')

        self.assertTrue(any('returned [False]' in line for line in logs.output))
        self.assertFalse(any("'000000'" in line for line in logs.output), 'The code must never be traced')

    def test_replayed_code_is_rejected_and_traced(self) -> None:
        mfa = self._mfa()
        code = self._current_code()

        with mock.patch.object(TOTP_MFA, 'ask_for_otp', return_value=True), mock.patch.object(
            TOTP_MFA, '_user_data', return_value=(self.secret, True)
        ):
            mfa.validate(self._request(), 'user1', 'user1', 'ident', code)

            with self.assertLogs(LOGGER_NAME, level='WARNING') as logs:
                with self.assertRaises(exceptions.auth.MFAError):
                    mfa.validate(self._request(), 'user1', 'user1', 'ident', code)

        self.assertTrue(any('already used' in line for line in logs.output))
        self.assertFalse(any(code in line for line in logs.output), 'The code must never be traced')

    def test_allowed_network_skips_validation_and_is_traced(self) -> None:
        mfa = self._mfa()

        with mock.patch.object(TOTP_MFA, 'ask_for_otp', return_value=False):
            with self.assertLogs(LOGGER_NAME, level='INFO') as logs:
                # An invalid code must be accepted: the network, not the code, is what allows the login
                mfa.validate(self._request(), 'user1', 'user1', 'ident', 'not-a-code')

        self.assertTrue(any('Validation skipped' in line for line in logs.output))
