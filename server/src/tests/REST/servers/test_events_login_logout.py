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

from uds import models
from uds.core.util import log

from ...utils import rest, random_ip_v4, random_ip_v6, random_mac
from ...fixtures import servers as servers_fixtures

if typing.TYPE_CHECKING:
    from ...utils.test import UDSHttpResponse

logger = logging.getLogger(__name__)


class ServerEventsLoginLogoutTest(rest.test.RESTTestCase):
    """
    Test server functionality
    """

    server: 'models.Server'

    def setUp(self) -> None:
        super().setUp()
        self.server = servers_fixtures.createServer()

    def test_login(self) -> None:
        # REST path: servers/notify  (/uds/rest/...)
        # loginData = {
        #     'token': 'server token', # Must be present on all events
        #     'type': 'login',  # MUST BE PRESENT
        #     'userservice_uuid': 'uuid', # MUST BE PRESENT
        #     'username': 'username', # Optional
        # }
        # Returns:
        #
        # {
        #     'ip': src.ip,
        #     'hostname': src.hostname,
        #     'dead_line': deadLine,
        #     'max_idle': maxIdle,
        #     'session_id': session_id,
        # }
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'login',
                'userservice_uuid': self.user_service_managed.uuid,
                'username': 'local_user_name',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.user_service_managed.refresh_from_db()
        self.assertEqual(self.user_service_managed.in_use, True)
        result = response.json()['result']
        self.assertEqual(self.user_service_managed.src_ip, result['ip'])
        self.assertEqual(self.user_service_managed.src_hostname, result['hostname'])
        session = self.user_service_managed.sessions.first()
        if session is None:
            self.fail('Session not found')
        self.assertEqual(session.session_id, result['session_id'])
        self.assertEqual(self.user_service_managed.properties.get('last_username', ''), 'local_user_name')
        # Must not have ticket
        self.assertIsNone(result.get('ticket', None))

    def test_login_with_ticket(self) -> None:
        ticket_uuid = models.TicketStore.create({'userservice_uuid': self.user_service_managed.uuid, 'some_value': 'value'})
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'login',
                'username': 'local_user_name',
                'ticket': ticket_uuid,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['result']
        self.assertEqual(data['ticket']['some_value'], 'value')

    def test_login_fail(self) -> None:
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'login',
                'userservice_uuid': 'invalid uuid',
                'username': 'local_user_name',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.content)
        self.assertIsNotNone(response.json())
        self.assertIn('error', response.json())

    def test_logout(self) -> None:
        # REST path: servers/notify  (/uds/rest/...)
        # logoutData = {
        #     'token': 'server token', # Must be present on all events
        #     'type': 'login',  # MUST BE PRESENT
        #     'user_service': 'uuid', # MUST BE PRESENT
        #     'username': 'username', # Optional
        # }
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'logout',
                'user_service': self.user_service_managed.uuid,
                'username': 'local_user_name',
                'session_id': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_service_managed.in_use, False)

    def test_logout_fail(self) -> None:
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'login',
                'user_service': 'invalid uuid',
                'username': 'local_user_name',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.content)
        self.assertIsNotNone(response.json())
        self.assertIn('error', response.json())

        # No session id, shouls return error
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'logout',
                'user_service': self.user_service_managed.uuid,
                'username': 'local_user_name',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.content)
        self.assertIsNotNone(response.json())
        self.assertIn('error', response.json())

    def test_loging_logout(self) -> None:
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'login',
                'userservice_uuid': self.user_service_managed.uuid,
                'username': 'local_user_name',
            },
        )
        self.assertEqual(response.status_code, 200)
        session_id = response.json()['result']['session_id']
        self.assertIsNotNone(session_id)
        self.user_service_managed.refresh_from_db()
        self.assertEqual(self.user_service_managed.in_use, True)

        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'logout',
                'userservice_uuid': self.user_service_managed.uuid,
                'username': 'local_user_name',
                'session_id': session_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.user_service_managed.refresh_from_db()
        self.assertEqual(self.user_service_managed.in_use, False)

    def test_ticket(self) -> None:
        ticket_uuid = models.TicketStore.create({'userservice_uuid': self.user_service_managed.uuid, 'some_value': 'value'})
        response = self.client.rest_post(
            '/servers/event',
            data={
                'token': self.server.token,
                'type': 'ticket',
                'ticket': ticket_uuid,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['result']
        self.assertEqual(data['some_value'], 'value')