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

from uds.core import types

from tests.services.openshift import fixtures

from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftUserServiceFixed(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    def test_userservice_fixed_initialization(self) -> None:
        """
        Test fixed user service initialization
        """
        userservice = fixtures.create_userservice_fixed()
        userservice._name = 'vm-3'

        self.assertEqual(userservice._name, 'vm-3')
        self.assertEqual(userservice.service().type_type, types.services.ServiceType.VDI)

    def test_userservice_fixed_lifecycle(self) -> None:
        """
        Test fixed user service lifecycle
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_fixed(provider=provider)
            userservice = fixtures.create_userservice_fixed(service=service)
            userservice._name = 'vm-3'

            # Test initial deployment
            fake_user = fixtures.create_user()
            state = userservice.deploy_for_user(fake_user)
            self.assertEqual(state, types.states.State.RUNNING)

            # Test check state when VM is running
            api.get_vm_instance_info.return_value = fixtures.VM_INSTANCES[2]  # vm-3 is running
            state = userservice.check_state()
            self.assertEqual(state, types.states.State.RUNNING)

            # Test get IP and MAC
            ip = userservice.get_ip()
            self.assertEqual(ip, '192.168.1.3')
            
            mac = userservice._mac
            self.assertEqual(mac, '00:11:22:33:44:03')

    def test_userservice_fixed_operations(self) -> None:
        """
        Test fixed user service operations
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_fixed(provider=provider)
            userservice = fixtures.create_userservice_fixed(service=service)
            userservice._name = 'vm-3'

            # Test start operation
            userservice.op_start()
            api.start_vm_instance.assert_called_with('vm-3')

            # Test stop operation
            userservice.op_stop()
            api.stop_vm_instance.assert_called_with('vm-3')

            # Test shutdown operation
            userservice.op_shutdown()
            api.stop_vm_instance.assert_called_with('vm-3')

    def test_userservice_fixed_error_handling(self) -> None:
        """
        Test fixed user service error handling
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_fixed(provider=provider)
            userservice = fixtures.create_userservice_fixed(service=service)
            userservice._name = 'vm-3'

            # Test when VM is not found
            api.get_vm_instance_info.return_value = None
            state = userservice.check_state()
            self.assertEqual(state, types.states.State.ERROR)

            # Test error reason
            reason = userservice.error_reason()
            self.assertIn('not found', reason)

    def test_userservice_fixed_serialization(self) -> None:
        """
        Test fixed user service serialization
        """
        userservice = fixtures.create_userservice_fixed()
        userservice._name = 'vm-3'
        userservice.set_ip('192.168.1.3')
        userservice._mac = '00:11:22:33:44:03'

        # Test get name
        self.assertEqual(userservice.get_name(), 'vm-3')
        
        # Test get unique id
        self.assertEqual(userservice.get_unique_id(), 'vm-3')