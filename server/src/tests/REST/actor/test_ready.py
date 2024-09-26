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
import logging

from unittest import mock

from uds.core import consts, types
from uds.core.util.model import sql_stamp_seconds

from uds.osmanagers.Test.testing_osmanager import TestOSManager

from tests.utils import rest


logger = logging.getLogger(__name__)


class ActorReadyTest(rest.test.RESTActorTestCase):
    """
    Test actor functionality
    """

    def test_ready(self) -> None:
        """
        Test actor initialize v3 for managed actor
        """
        userservice = self.user_service_managed

        # To ready should be invoked and, in turn, ready_notified from to_ready
        for method in (TestOSManager.process_ready.__name__, TestOSManager.on_ready.__name__):
            actor_token = userservice.uuid
            userservice.set_in_use(True)
            userservice.set_os_state(types.states.State.PREPARING)
            with mock.patch.object(TestOSManager, method) as to_ready:
                response = self.client.post(
                    '/uds/rest/actor/v3/ready',
                    data={
                        'token': actor_token,
                        'ip': '1.2.3.4',
                        'secret': 'test_secret',
                        'port': 43910,
                    },
                    content_type='application/json',
                )

                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn('result', data)
                self.assertIn('stamp', data)
                self.assertIn('version', data)
                self.assertIn('build', data)

                self.assertEqual(data['version'], consts.system.VERSION)
                self.assertEqual(data['build'], consts.system.VERSION_STAMP)

                self.assertLess(abs(data['stamp'] - sql_stamp_seconds()), 2)  # May differ in miliseconds, but 0.999 + 0.001 = 1 :)

                result = data['result']
                for i in ('key', 'certificate', 'password', 'ciphers'):
                    self.assertIn(i, result)
                    self.assertIsInstance(result[i], str)
                    self.assertGreater(len(result[i]), 0 if i != 'ciphers' else -1)

                userservice.refresh_from_db()
                # We are not in use anymore, because "ready" means just initialized, so we are not in use
                self.assertEqual(userservice.in_use, False)
                self.assertEqual(userservice.os_state, types.states.State.USABLE)

                to_ready.assert_called_once_with(userservice)
