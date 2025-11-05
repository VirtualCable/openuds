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

from tests.services.openshift import fixtures
from uds.core.types.states import TaskState
from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftDeployment(UDSTransactionTestCase):
    def _create_userservice(self):
        """
        Helper to create a userservice instance with a preset name for deployment operation tests.
        Returns:
            userservice: A userservice object with name 'test-vm'.
        """
        userservice = fixtures.create_userservice()
        userservice._name = 'test-vm'
        return userservice
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    # --- Create operation tests ---
    def test_op_create_success(self) -> None:
        """
        Test successful VM creation operation.
        Should clear the waiting_name flag after creation.
        """
        userservice = self._create_userservice()
        userservice._waiting_name = False
        api = userservice.service().api
        with mock.patch.object(api, 'get_vm_pvc_or_dv_name', return_value=('test-pvc', 'pvc')), \
             mock.patch.object(api, 'get_pvc_size', return_value='10Gi'), \
             mock.patch.object(api, 'create_vm_from_pvc', return_value=True), \
             mock.patch.object(api, 'wait_for_datavolume_clone_progress', return_value=True):
            userservice.op_create()
        self.assertFalse(userservice._waiting_name)

    def test_op_create_failure(self) -> None:
        """
        Test failed VM creation operation.
        Should set the waiting_name flag if creation fails.
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        userservice._waiting_name = False
        with mock.patch.object(api, 'get_vm_pvc_or_dv_name', return_value=('test-pvc', 'pvc')), \
             mock.patch.object(api, 'get_pvc_size', return_value='10Gi'), \
             mock.patch.object(api, 'create_vm_from_pvc', return_value=False):
            userservice.op_create()
        self.assertTrue(userservice._waiting_name)

    def test_op_create_checker_running(self) -> None:
        """
        Test create checker returns RUNNING when datavolume phase is pending.
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        with mock.patch.object(api, 'get_datavolume_phase', return_value='Pending'):
            state = userservice.op_create_checker()
        self.assertEqual(state, TaskState.RUNNING)

    def test_op_create_checker_finished(self) -> None:
        """
        Test create checker returns FINISHED when datavolume phase is succeeded and VM info is available.
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        with mock.patch.object(api, 'get_datavolume_phase', return_value='Succeeded'), \
             mock.patch.object(api, 'get_vm_info', return_value=fixtures.VMS[0]), \
             mock.patch.object(api, 'get_vm_instance_info', return_value=fixtures.VM_INSTANCES[0]):
            state = userservice.op_create_checker()
        self.assertEqual(state, TaskState.FINISHED)

    # --- Delete operation tests ---
    def test_op_delete_checker_finished(self) -> None:
        """
        Test delete checker returns FINISHED when VM info is None (deleted).
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        with mock.patch.object(api, 'get_vm_info', return_value=None):
            state = userservice.op_delete_checker()
        self.assertEqual(state, TaskState.FINISHED)

    def test_op_delete_checker_running(self) -> None:
        """
        Test delete checker returns RUNNING when VM info still exists.
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        with mock.patch.object(api, 'get_vm_info', return_value=fixtures.VMS[0]):
            state = userservice.op_delete_checker()
        self.assertEqual(state, TaskState.RUNNING)

    def test_op_delete_completed_checker(self) -> None:
        """
        Test delete completed checker always returns FINISHED.
        """
        userservice = self._create_userservice()
        state = userservice.op_delete_completed_checker()
        self.assertEqual(state, TaskState.FINISHED)

    # --- Cancel operation tests ---
    def test_op_cancel_checker_finished(self) -> None:
        """
        Test cancel checker returns FINISHED when VM info is None (cancelled).
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        with mock.patch.object(api, 'get_vm_info', return_value=None):
            state = userservice.op_cancel_checker()
        self.assertEqual(state, TaskState.FINISHED)

    def test_op_cancel_checker_running(self) -> None:
        """
        Test cancel checker returns RUNNING when VM info still exists.
        """
        userservice = self._create_userservice()
        api = userservice.service().api
        with mock.patch.object(api, 'get_vm_info', return_value=fixtures.VMS[0]):
            state = userservice.op_cancel_checker()
        self.assertEqual(state, TaskState.RUNNING)

    def test_op_cancel_completed_checker(self) -> None:
        """
        Test cancel completed checker always returns FINISHED.
        """
        userservice = self._create_userservice()
        state = userservice.op_cancel_completed_checker()
        self.assertEqual(state, TaskState.FINISHED)
