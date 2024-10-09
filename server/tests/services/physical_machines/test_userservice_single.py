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
from unittest import mock

from uds.core import types

from . import fixtures

from ...utils.test import UDSTransactionTestCase

# from ...utils.generators import limited_iterator


# We use transactions on some related methods (storage access, etc...)
class TestUserServiceSingle(UDSTransactionTestCase):
    def test_userservice(self) -> None:
        """
        Test the user service
        """
        userservice = fixtures.create_userservice_single()
        service = userservice.service()

        self.assertEqual(userservice.deploy_for_user(mock.MagicMock()), types.states.TaskState.FINISHED)
        self.assertEqual(userservice.check_state(), types.states.TaskState.FINISHED)

        self.assertEqual(userservice.get_ip(), service.host.value)
        self.assertEqual(userservice.get_name(), f'{userservice.get_ip()}:0')
        self.assertEqual(userservice.get_unique_id(), f'{userservice.get_ip()}:0')

        # patch service wakeup to ensure it's called
        with mock.patch.object(service, 'wakeup') as wakeup:
            userservice.set_ready()
            wakeup.assert_called_with()

        self.assertEqual(userservice.destroy(), types.states.TaskState.FINISHED)
        self.assertEqual(userservice.cancel(), types.states.TaskState.FINISHED)

        # deploy for cache should return error
        state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)
        self.assertEqual(state, types.states.TaskState.ERROR)
        self.assertEqual(userservice.check_state(), types.states.TaskState.ERROR)
        self.assertEqual(userservice.error_reason(), userservice._reason)
