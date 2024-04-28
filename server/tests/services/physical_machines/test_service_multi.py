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

from uds import models
from uds.core.util import fields
from uds.core.util.model import sql_now

from . import fixtures

# from ...utils import MustBeOfType
from ...utils.test import UDSTransactionTestCase


class TestServiceMulti(UDSTransactionTestCase):
    def test_service_data(self) -> None:
        service = fixtures.create_service_multi()

        self.assertEqual(service.token.value, fixtures.SERVICE_MULTI_VALUES_DICT['token'])
        server_group = fields.get_server_group_from_field(service.server_group)
        self.assertTrue(server_group.servers.count() > 0)
        self.assertEqual(service.port.value, fixtures.SERVICE_MULTI_VALUES_DICT['port'])
        self.assertEqual(
            service.ignore_minutes_on_failure.value, fixtures.SERVICE_MULTI_VALUES_DICT['ignore_minutes_on_failure']
        )
        self.assertEqual(service.max_session_hours.value, fixtures.SERVICE_MULTI_VALUES_DICT['max_session_hours'])
        self.assertEqual(
            service.lock_on_external_access.value, fixtures.SERVICE_MULTI_VALUES_DICT['lock_on_external_access']
        )
        self.assertEqual(service.randomize_host.value, fixtures.SERVICE_MULTI_VALUES_DICT['randomize_host'])

    def test_service_is_available(self) -> None:
        """
        Test the provider
        """
        service = fixtures.create_service_multi()
        self.assertTrue(service.is_avaliable())  # Always available

    def test_wakeup(self) -> None:
        # Patch security.secure_requests_session
        with mock.patch('uds.core.util.security.secure_requests_session') as secure_requests_session:
            service = (
                fixtures.create_service_multi()
            )  # With only the IP, should not invoke secure_requests_session

            service.wakeup('127.0.0.1', '')
            secure_requests_session.assert_not_called()

            # Now, host = '127.0.0.1;01:23:45:67:89:ab', should invoke secure_requests_session
            service.wakeup('127.0.0.1', '01:23:45:67:89:ab')
            secure_requests_session.assert_called_once()

            # Now host is outside the range of provider wol, should not invoke secure_requests_session
            secure_requests_session.reset_mock()
            service.wakeup('127.1.0.1', '01:23:45:67:89:ab')
            secure_requests_session.assert_not_called()

    def test_get_valid_id(self) -> None:
        service = fixtures.create_service_multi()
        ip, mac = fixtures.SERVER_GROUP_IPS_MACS[0]
        uuid = models.Server.objects.get(ip=ip).uuid
        for tests in [
            [ip],
            [mac],
            [ip, mac],
            [mac, ip],
        ]:
            service.lock_on_external_access.value = True
            self.assertEqual(service.get_valid_id(tests), uuid)
            # Should return None if lock_on_external_access is false
            service.lock_on_external_access.value = False
            self.assertIsNone(service.get_valid_id(tests))

        self.lock_on_external_access = True  # Restore default value
        # Test with invalid mac
        self.assertIsNone(service.get_valid_id(['01:23:45:67:89:ab']))
        # Test with invalid ip
        self.assertIsNone(service.get_valid_id(['127.1.1.1']))

    def test_process_login(self) -> None:
        service = fixtures.create_service_multi()
        ip, _mac = fixtures.SERVER_GROUP_IPS_MACS[0]
        uuid = models.Server.objects.get(ip=ip).uuid

        # process login, should invoke lock_server if lock_on_external_access is True
        with mock.patch.object(service, 'lock_server') as assign:
            service.lock_on_external_access.value = False
            service.process_login(uuid, True)
            assign.assert_not_called()

            service.lock_on_external_access.value = True
            service.process_login(uuid, True)
            assign.assert_called_once()

    def test_process_logout(self) -> None:
        service = fixtures.create_service_multi()
        ip, _mac = fixtures.SERVER_GROUP_IPS_MACS[0]
        uuid = models.Server.objects.get(ip=ip).uuid

        # process logout, should invoke release_server ALWAYS
        # This is so because will only be invoked if no userservice is present
        # (if any userservice has the server, the actor will process the logout using the userservice, not the service itself)
        with mock.patch.object(service, 'unlock_server') as release:
            service.lock_on_external_access.value = False
            service.process_logout(uuid, True)
            release.assert_called_once()

            release.reset_mock()
            service.lock_on_external_access.value = True
            service.process_logout(uuid, True)
            release.assert_called_once()

    def test_lock_server(self) -> None:
        service = fixtures.create_service_multi()
        ip, _mac = fixtures.SERVER_GROUP_IPS_MACS[0]
        server = models.Server.objects.get(ip=ip)

        self.assertTrue(server.locked_until is None)

        service.lock_server(server.uuid)
        # Server should be locked now
        server.refresh_from_db()
        self.assertIsNotNone(server.locked_until)

    def test_unlock_server(self) -> None:
        service = fixtures.create_service_multi()
        ip, _mac = fixtures.SERVER_GROUP_IPS_MACS[0]
        server = models.Server.objects.get(ip=ip)

        server.locked_until = sql_now()
        server.save(update_fields=['locked_until'])

        service.unlock_server(server.uuid)
        server.refresh_from_db()
        self.assertIsNone(server.locked_until)
