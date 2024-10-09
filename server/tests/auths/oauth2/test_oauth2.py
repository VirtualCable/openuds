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
from urllib.parse import urlparse, parse_qs
from base64 import b64encode
from hashlib import sha256
from unittest import mock

from tests.utils.test import UDSTestCase
from uds.auths.OAuth2.authenticator import OAuth2Authenticator
from uds.core import types

from . import fixtures

from uds.auths.OAuth2 import types as oauth2_types, consts as oauth2_consts


class OAuth2Test(UDSTestCase):
    def test_auth(self) -> None:
        with fixtures.create_authenticator(oauth2_types.ResponseType.CODE) as oauth2:
            self.assertIsInstance(oauth2, fixtures.OAuth2Authenticator)

    def test_correct_callbacks(self) -> None:
        with fixtures.create_authenticator(oauth2_types.ResponseType.CODE) as oauth2:
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

            for response_type in oauth2_types.ResponseType:
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
        for response_type in oauth2_types.ResponseType:
            with fixtures.create_authenticator(response_type) as oauth2:
                oauth2.logout_url.value = 'https://logout.com?token={token}'
                with mock.patch.object(oauth2, OAuth2Authenticator.retrieve_token.__name__, return_value='token_value'):
                    logout = oauth2.logout(mock.MagicMock(), 'not_used_username')
                    self.assertIsInstance(logout, types.auth.AuthenticationResult)
                    self.assertTrue(logout.success)
                    self.assertEqual(logout.url, 'https://logout.com?token=token_value')

    def test_get_login_url_code(self) -> None:
        for kind in oauth2_types.ResponseType:
            with fixtures.create_authenticator(kind) as oauth2:
                url = oauth2.get_login_url()
                self.assertIsInstance(url, str)
                # Parse URL and ensure it's correct
                auth_url_info = urlparse(url)
                configured_url_info = urlparse(oauth2.authorization_endpoint.value, kind.as_text)
                query = parse_qs(auth_url_info.query)
                configures_scopes = set(oauth2.scope.value.split())

                self.assertEqual(auth_url_info.scheme, configured_url_info.scheme, kind.as_text)
                self.assertEqual(auth_url_info.netloc, configured_url_info.netloc, kind.as_text)
                self.assertEqual(auth_url_info.path, configured_url_info.path, kind.as_text)
                self.assertEqual(query['response_type'], [kind.for_query], kind.as_text)
                self.assertEqual(query['client_id'], [oauth2.client_id.value], kind.as_text)
                self.assertEqual(query['redirect_uri'], [oauth2.redirection_endpoint.value], kind.as_text)
                scopes = set(query['scope'][0].split())

                code_challenge = ''
                if kind == oauth2_types.ResponseType.PKCE:
                    self.assertEqual(query['code_challenge_method'], ['S256'], kind.as_text)
                    code_challenge = query['code_challenge'][0]
                    self.assertIsInstance(code_challenge, str, kind.as_text)

                # All configured scopes should be present
                self.assertTrue(configures_scopes.issubset(scopes), kind.as_text)

                # And if openid variant, scope should contain openid
                if kind in (oauth2_types.ResponseType.OPENID_CODE, oauth2_types.ResponseType.OPENID_ID_TOKEN):
                    self.assertIn('openid', scopes, kind.as_text)

                state = query['state'][0]
                self.assertIsInstance(state, str, kind.as_text)
                # state is in base64, so it will take a bit more than 16 characters
                # Exactly every 6 bits will take 8 bits, so we need to divide by 6 and multiply by 8
                # Adjusting to the upper integer
                expected_length = (oauth2_consts.STATE_LENGTH * 8 + 5) // 6
                self.assertEqual(len(state), expected_length, kind.as_text)
                # oauth2 cache should contain the state
                state_value = oauth2.cache.get(state)
                self.assertIsNotNone(state_value, kind.as_text)
                
                # If pkce, we need to check the code_challenge. code_verifier is stored in the state
                if kind == oauth2_types.ResponseType.PKCE:
                    calc_code_challenge = (
                        b64encode(sha256(state_value.encode()).digest(), altchars=b'-_')
                        .decode()
                        .rstrip('=')  # remove padding
                    )

                    self.assertEqual(calc_code_challenge, code_challenge, kind.as_text)
                
