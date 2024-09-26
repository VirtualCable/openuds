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
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging
from unittest import mock

from uds import models

from uds.core.util import config
from uds.core.auths import callbacks

from tests.utils.test import UDSTestCase

from tests.fixtures import authenticators as authenticators_fixtures

if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AuthCallbackTest(UDSTestCase):
    auth: 'models.Authenticator'
    groups: list['models.Group']
    user: 'models.User'

    def setUp(self) -> None:
        super().setUp()

        self.auth = authenticators_fixtures.create_db_authenticator()
        self.groups = authenticators_fixtures.create_db_groups(self.auth, 5)
        self.user = authenticators_fixtures.create_db_users(self.auth, number_of_users=1, groups=self.groups[:3])[0]

    def test_no_callback(self) -> None:
        config.GlobalConfig.LOGIN_CALLBACK_URL.set('')  # Clean callback url

        with mock.patch('requests.post') as mock_post:
            callbacks.perform_login_callback(self.user)
            mock_post.assert_not_called()

    def test_callback_failed_url(self) -> None:
        config.GlobalConfig.LOGIN_CALLBACK_URL.set('http://localhost:1234')  # Sample non existent url
        callbacks.FAILURE_CACHE.set('notify_failure', 3)  # Already failed 3 times

        with mock.patch('requests.post') as mock_post:
            callbacks.perform_login_callback(self.user)
            mock_post.assert_not_called()

    def test_callback_fails_reteleadly(self) -> None:
        config.GlobalConfig.LOGIN_CALLBACK_URL.set('https://localhost:1234')

        with mock.patch('requests.post') as mock_post:
            mock_post.side_effect = Exception('Error')
            for _i in range(4):
                callbacks.perform_login_callback(self.user)
                
            self.assertEqual(mock_post.call_count, 3)

    def test_callback_change_groups(self) -> None:
        config.GlobalConfig.LOGIN_CALLBACK_URL.set('https://localhost:1234')
        
        all_groups = {group.name for group in self.groups}
        current_groups = {group.name for group in self.user.groups.all()}
        
        diff_groups = all_groups - current_groups

        with mock.patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = {
                'new_groups': list(diff_groups),
                'removed_groups': list(current_groups),
            }

            callbacks.perform_login_callback(self.user)

            self.assertEqual(mock_post.call_count, 1)
            self.assertEqual({group.name for group in self.user.groups.all()}, diff_groups)