# pylint: disable=no-member   # ldap module gives errors to pylint
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from unittest import mock

from tests.utils.test import UDSTestCase
from uds.core import types

from . import fixtures

VALID_RESPONSE_TYPES: list[fixtures.ResponseType] = ['code', 'pkce', 'token', 'openid+token_id', 'openid+code']


class OAuthCodeFlowTest(UDSTestCase):
    def test_auth(self) -> None:
        with fixtures.create_authenticator('code') as oauth2:
            self.assertIsInstance(oauth2, fixtures.OAuth2Authenticator)

    def test_correct_callbacks(self) -> None:
        with fixtures.create_authenticator('code') as oauth2:
            oauth2.auth_callback_code = mock.MagicMock()
            oauth2.auth_callback_token = mock.MagicMock()
            oauth2.auth_callback_openid_code = mock.MagicMock()
            oauth2.auth_callback_openid_id_token = mock.MagicMock()

            TEST_DCT: dict[str, mock.MagicMock] = {
                'code': oauth2.auth_callback_code,
                'pkce': oauth2.auth_callback_code,
                'token': oauth2.auth_callback_token,
                'openid+code': oauth2.auth_callback_openid_code,
                'openid+token_id': oauth2.auth_callback_openid_id_token,
            }

            for response_type in VALID_RESPONSE_TYPES:
                expected_call = TEST_DCT[response_type]  # If not exists, raises KeyError

                oauth2.response_type.value = response_type
                # Reset all mocks first
                for call in TEST_DCT.values():
                    call.reset_mock()

                oauth2.auth_callback(mock.MagicMock(), mock.MagicMock(), mock.MagicMock())
                expected_call.assert_called_once()
                # Rest of the mocks should not have been called
                for call in TEST_DCT.values():
                    if call is not expected_call:
                        call.assert_not_called()

    def test_logout_url(self) -> None:
        for response_type in VALID_RESPONSE_TYPES:
            with fixtures.create_authenticator(response_type) as oauth2:
                oauth2.logout_url.value = 'https://logout.com?token={token}'
                with mock.patch.object(oauth2, '_retrieve_token_from_session', return_value='token_value'):
                    logout = oauth2.logout(mock.MagicMock(), 'not_used_username')
                    self.assertIsInstance(logout, types.auth.AuthenticationResult)
                    self.assertTrue(logout.success)
                    self.assertEqual(logout.url, 'https://logout.com?token=token_value')
