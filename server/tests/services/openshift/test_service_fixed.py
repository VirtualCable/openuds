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

from tests.services.openshift import fixtures

from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftServiceFixed(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    def test_service_fixed_data(self) -> None:
        """
        Test fixed service data
        """
        service = fixtures.create_service_fixed()

        self.assertEqual(service.token.value, fixtures.SERVICE_FIXED_VALUES_DICT['token'])
        self.assertEqual(service.machines.value, fixtures.SERVICE_FIXED_VALUES_DICT['machines'])
        self.assertEqual(service.on_logout.value, fixtures.SERVICE_FIXED_VALUES_DICT['on_logout'])
        self.assertEqual(service.randomize.value, fixtures.SERVICE_FIXED_VALUES_DICT['randomize'])
        self.assertEqual(service.maintain_on_error.value, fixtures.SERVICE_FIXED_VALUES_DICT['maintain_on_error'])

    def test_service_fixed_is_available(self) -> None:
        """
        Test fixed service availability
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_fixed(provider=provider)

            self.assertTrue(service.is_available())
            api.test.assert_called_with()

            # Test with cached data
            api.test.return_value = False
            self.assertTrue(service.is_available())

            # Clear cache and test again
            service.provider().is_available.cache_clear()  # type: ignore
            self.assertFalse(service.is_available())
            api.test.assert_called_with()

    def test_service_fixed_methods(self) -> None:
        """
        Test fixed service methods
        """
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_fixed(provider=provider)

            # Test get machines
            machines = list(service.enumerate_assignables())
            self.assertEqual(len(machines), 3)
            self.assertEqual(machines[0], 'vm-3')
            self.assertEqual(machines[1], 'vm-4')
            self.assertEqual(machines[2], 'vm-5')

            # Test get machine name
            machine_name = service.get_name('vm-3')
            self.assertEqual(machine_name, 'vm-3')

            # Test sanitized name
            sanitized = service.sanitized_name('Test VM 1')
            self.assertEqual(sanitized, 'test-vm-1')

    def test_service_fixed_assignment(self) -> None:
        """
        Test fixed service assignment
        """
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_fixed(provider=provider)

            # Test assign from empty
            user = fixtures.create_user()  # Create a valid User instance
            userservice_instance = fixtures.create_userservice_fixed(service=service)
            assigned: typing.Optional[str] = service.assign_from_assignables(assignable_id='', user=user, userservice_instance=userservice_instance)
            self.assertEqual(assigned, 'vm-3')

            # Test with existing assignments
            assigned: typing.Optional[str] = service.assign_from_assignables(assignable_id='vm-3', user=user, userservice_instance=userservice_instance)
            self.assertEqual(assigned, 'vm-4')

            # Test with all assigned
            assigned: typing.Optional[str] = service.assign_from_assignables(assignable_id='vm-3,vm-4,vm-5', user=user, userservice_instance=userservice_instance)
            self.assertIsNone(assigned)