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
from uds.core.types.states import TaskState
from tests.services.openshift import fixtures
from tests.utils.test import UDSTransactionTestCase

class TestOpenshiftUserServiceFixed(UDSTransactionTestCase):
    def _create_userservice_fixed(self):
        """
        Helper to create a fixed userservice instance for deployment_fixed operation tests.
        Returns:
            userservice: A fixed userservice object with name 'fixed-vm'.
        """
        userservice = fixtures.create_userservice_fixed()
        userservice._name = 'fixed-vm'
        return userservice
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()
        
    # --- Start operation tests ---
    def test_op_start_vm_running(self) -> None:
        """
        Test that op_start does not start VM if it is already running.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        vm_mock.status.is_off.return_value = False
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            with mock.patch.object(api, 'start_vm_instance') as start_mock:
                userservice.op_start()
                start_mock.assert_not_called()

    def test_op_start_vm_off(self) -> None:
        """
        Test that op_start starts VM if it is off.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        vm_mock.status.is_off.return_value = True
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            with mock.patch.object(api, 'start_vm_instance') as start_mock:
                userservice.op_start()
                start_mock.assert_called_once_with('fixed-vm')

    # --- Stop operation tests ---
    def test_op_stop_vm_off(self) -> None:
        """
        Test that op_stop does not stop VM if it is already off.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        vm_mock.status.is_off.return_value = True
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            with mock.patch.object(api, 'stop_vm_instance') as stop_mock:
                userservice.op_stop()
                stop_mock.assert_not_called()

    def test_op_stop_vm_running(self) -> None:
        """
        Test that op_stop stops VM if it is running.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        vm_mock.status.is_off.return_value = False
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            with mock.patch.object(api, 'stop_vm_instance') as stop_mock:
                userservice.op_stop()
                stop_mock.assert_called_once_with('fixed-vm')

    # --- Start checker tests ---
    def test_op_start_checker_running(self) -> None:
        """
        Test that op_start_checker returns RUNNING if VM status is not error.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        status_mock = mock.Mock()
        status_mock.is_error.return_value = False
        vm_mock = mock.Mock()
        vm_mock.status = status_mock
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            state = userservice.op_start_checker()
        self.assertEqual(state, TaskState.RUNNING)

    def test_op_start_checker_finished(self) -> None:
        """
        Test that op_start_checker returns FINISHED if VM status is RUNNING.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        from uds.services.OpenShift.openshift import types as opensh_types
        vm_mock.status = opensh_types.VMStatus.RUNNING
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            state = userservice.op_start_checker()
            self.assertEqual(state, TaskState.FINISHED)

    # --- Stop checker tests ---
    def test_op_stop_checker_running(self) -> None:
        """
        Test that op_stop_checker returns RUNNING if VM status is not error.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        status_mock = mock.Mock()
        status_mock.is_error.return_value = False
        vm_mock.status = status_mock
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            state = userservice.op_stop_checker()
        self.assertEqual(state, TaskState.RUNNING)

    def test_op_stop_checker_finished(self) -> None:
        """
        Test that op_stop_checker returns FINISHED if VM status is STOPPED.
        """
        userservice = self._create_userservice_fixed()
        api = userservice.service().provider().api
        vm_mock = mock.Mock()
        from uds.services.OpenShift.openshift import types as opensh_types
        vm_mock.status = opensh_types.VMStatus.STOPPED
        with mock.patch.object(api, 'get_vm_info', return_value=vm_mock):
            state = userservice.op_stop_checker()
            self.assertEqual(state, TaskState.FINISHED)


