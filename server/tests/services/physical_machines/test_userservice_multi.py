# -*- coding: utf-8 -*-

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
from unittest import mock

from uds import models
from uds.core import types

from . import fixtures

from ...utils.test import UDSTransactionTestCase

# from ...utils.generators import limited_iterator


# We use transactions on some related methods (storage access, etc...)
class TestUserServiceMulti(UDSTransactionTestCase):
    
    @mock.patch('uds.core.util.net.test_connectivity', return_value=True)
    def test_userservice(self, test_conn: mock.MagicMock) -> None:
        """
        Test the user service
        """
        userservice = fixtures.create_userservice_multi()

        # Does not supports cache
        self.assertEqual(
            userservice.deploy_for_cache(level=types.services.CacheLevel.L1), types.states.TaskState.ERROR
        )
        # Ensure check also returns error state
        self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)

        # Ensure has no token for this test
        self.assertEqual(userservice.deploy_for_user(mock.MagicMock()), types.states.TaskState.FINISHED)

        server = models.Server.objects.get(uuid=userservice._vmid)
        # Ensure is locked
        self.assertIsNotNone(server.locked_until)

        # Destroy it
        self.assertEqual(userservice.destroy(), types.states.TaskState.FINISHED)
        # Ensure is not locked
        server.refresh_from_db()
        self.assertIsNone(server.locked_until)

    @mock.patch('uds.core.util.net.test_connectivity', return_value=True)
    def test_userservice_set_ready(self, test_conn: mock.MagicMock) -> None:
        """
        Test the user service
        """
        userservice = fixtures.create_userservice_multi()

        # Ensure has no token for this test
        self.assertEqual(userservice.deploy_for_user(mock.MagicMock()), types.states.TaskState.FINISHED)

        # Ensure is locked
        server = models.Server.objects.get(uuid=userservice._vmid)
        self.assertIsNotNone(server.locked_until)

        # Set ready
        # patch service wakeup
        with mock.patch.object(userservice.service(), 'wakeup') as wakeup:
            self.assertEqual(userservice.set_ready(), types.states.TaskState.FINISHED)
            wakeup.assert_called_once_with(userservice._ip, userservice._mac)

    def test_userservice_assign(self) -> None:
        """
        Test the user service
        """
        userservice = fixtures.create_userservice_multi()
        server = models.Server.objects.first()
        if not server:
            self.fail('No server found')

        # Assign
        userservice.assign(server.uuid)
        self.assertEqual(userservice._vmid, server.uuid)

        # Ensure ip and mac are same as server
        self.assertEqual(userservice._ip, server.ip)
        self.assertEqual(userservice._mac, server.mac)

    @mock.patch('uds.core.util.net.test_connectivity', return_value=True)
    def test_userservice_without_token(self, test_conn: mock.MagicMock) -> None:
        """
        Test the user service
        """
        userservice = fixtures.create_userservice_multi()
        db_obj_mock = typing.cast(mock.MagicMock, userservice.db_obj)

        # Ensure has no token for this test
        userservice.service().token.value = ''
        self.assertEqual(userservice.deploy_for_user(mock.MagicMock()), types.states.TaskState.FINISHED)
        self.assertTrue(mock.call().set_in_use(True) in db_obj_mock.mock_calls)

    @mock.patch('uds.core.util.net.test_connectivity', return_value=True)
    def test_userservice_with_token(self, test_conn: mock.MagicMock) -> None:
        """
        Test the user service
        """
        userservice = fixtures.create_userservice_multi()
        db_obj_mock = typing.cast(mock.MagicMock, userservice.db_obj)

        # Ensure has no token for this test
        userservice.service().token.value = 'token_value'
        self.assertEqual(userservice.deploy_for_user(mock.MagicMock()), types.states.TaskState.FINISHED)
        self.assertFalse(mock.call().set_in_use(True) in db_obj_mock.mock_calls)
