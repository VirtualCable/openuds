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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging

from unittest import mock

from uds.core.util import log

from ...utils import rest, random_ip_v4, random_ip_v6, random_mac
from ...fixtures import servers as servers_fixtures

if typing.TYPE_CHECKING:
    from ...utils.test import UDSHttpResponse

logger = logging.getLogger(__name__)


class ServerEventsLogTest(rest.test.RESTTestCase):
    """
    Test server functionality
    """

    def test_event_log(self) -> None:
        # REST path: servers/notify  (/uds/rest/...)
        # Log data:
        # logData = {
        #     'token': 'server token', # Must be present on all events
        #     'type': 'log',
        #     'user_service': 'optional userService uuid', if not present, is a log for the server of the token
        #     'level': 'debug|info'|'warning'|'error',
        #     'message': 'message',
        # }
        server = servers_fixtures.createServer()
        userService = self.user_service_managed

        # Mock the "log.doLog" method (uds.core.util.log.doLog)
        with mock.patch('uds.core.managers.log.manager.LogManager.doLog') as doLog:
            # Now notify to server
            response = self.client.rest_post(
                '/servers/event',
                data={
                    'token': server.token,
                    'type': 'log',
                    'level': 'info',
                    'message': 'test message',
                },
            )
            self.assertEqual(response.status_code, 200)
            # First call shout have
            doLog.assert_any_call(server, log.LogLevel.INFO, 'test message', log.LogSource.SERVER, None)

            # Now notify to an userService
            response = self.client.rest_post(
                'servers/event',
                data={
                    'token': server.token,
                    'userservice_uuid': userService.uuid,
                    'type': 'log',
                    'level': 'info',
                    'message': 'test message userservice',
                },
            )

            self.assertEqual(response.status_code, 200)
            doLog.assert_any_call(
                userService, log.LogLevel.INFO, 'test message userservice', log.LogSource.SERVER, None
            )

    def test_event_log_fail(self) -> None:
        server = servers_fixtures.createServer()
        data = {
            'token': server.token,
            'type': 'log',
            'level': 'info',
            'message': 'test',
        }

        for field, value in (
            ('token', None),
            ('type', 'invalid'),
            # Invalid level should log as "other"
            ('message', None),
        ):
            fail_data = data.copy()
            if value is None:
                del fail_data[field]
            else:
                fail_data[field] = value

            response = self.client.rest_post(
                '/servers/event',
                data=fail_data,
            )
            if field == 'token':
                self.assertEqual(response.status_code, 400, f'Error on field {field}')
            else:
                self.assertEqual(response.status_code, 200, f'Error on field {field}')
                self.assertIsNotNone(response.content, f'Error not found for field {field}')
                self.assertIsNotNone(response.json(), f'Error not found for field {field}')
                self.assertIn('error', response.json(), f'Error not found for field {field}')
