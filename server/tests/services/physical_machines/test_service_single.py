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

from . import fixtures

from ...utils.test import UDSTransactionTestCase


class TestService(UDSTransactionTestCase):
    def test_service_data(self) -> None:
        service = fixtures.create_service_single()

        self.assertEqual(service.host.value, fixtures.SERVICE_SINGLE_VALUES_DICT['host'])

    def test_service_is_available(self) -> None:
        """
        Test the provider
        """
        service = fixtures.create_service_single()
        self.assertTrue(service.is_avaliable())  # Always available

    def test_wakeup(self) -> None:
        # Patch security.secure_requests_session
        with mock.patch('uds.core.util.security.secure_requests_session') as secure_requests_session:
            service = (
                fixtures.create_service_single()
            )  # With only the IP, should not invoke secure_requests_session

            service.wakeup()
            secure_requests_session.assert_not_called()

            # Now, host = '127.0.0.1;01:23:45:67:89:ab', should invoke secure_requests_session
            service = fixtures.create_service_single(host='127.0.0.1;01:23:45:67:89:ab')
            service.wakeup()
            secure_requests_session.assert_called_once()

            # Now host is outside the range of provider wol, should not invoke secure_requests_session
            secure_requests_session.reset_mock()
            service = fixtures.create_service_single(host='127.1.0.1;01:23:45:67:89:ab')
            service.wakeup()
            secure_requests_session.assert_not_called()

    def test_get_unassigned(self) -> None:
        # without mac
        service = fixtures.create_service_single()
        self.assertEqual(service.get_unassigned_host(), (fixtures.SERVICE_SINGLE_VALUES_DICT['host'], ''))
        # with mac
        service = fixtures.create_service_single(host='127.0.0.1;01:23:45:67:89:ab')
        self.assertEqual(service.get_unassigned_host(), ('127.0.0.1', '01:23:45:67:89:ab'))
