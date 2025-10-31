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


class TestOpenshiftPublication(UDSTransactionTestCase):
    def setUp(self) -> None:
        fixtures.clear()

    def test_publication_creation(self) -> None:
        """
        Test publication creation
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Mock the publication process
            api.get_vm_pvc_or_dv_name.return_value = ('test-pvc', 'pvc')
            api.get_pvc_size.return_value = '10Gi'
            api.create_vm_from_pvc.return_value = True
            api.wait_for_datavolume_clone_progress.return_value = True
            api.get_vm_info.return_value = fixtures.VMS[0]

            state = publication.publish()
            self.assertEqual(state, types.states.State.RUNNING)

            # Check that publication process was initiated
            api.get_vm_pvc_or_dv_name.assert_called()
            api.get_pvc_size.assert_called()
            api.create_vm_from_pvc.assert_called()

    def test_publication_creation_checker(self) -> None:
        """
        Test publication creation checker
        """
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Ensure api is a mock so we can set return_value
            api = typing.cast(mock.MagicMock, publication.service().api)

            # Test when VM is not found yet
            publication._waiting_name = True
            api.get_vm_info.return_value = None

            state = publication.op_create_checker()
            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Test when VM is found
            api.get_vm_info.return_value = fixtures.VMS[0]
            state = publication.op_create_checker()
            self.assertEqual(state, types.states.TaskState.FINISHED)

    def test_publication_completed(self) -> None:
        """
        Test publication completion
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Test with running VM
            running_vm = fixtures.VMS[0]
            running_vm.status = fixtures.openshift_types.VMStatus.RUNNING
            api.get_vm_info.return_value = running_vm

            publication.op_create_completed()
            api.stop_vm_instance.assert_called_with(publication._name)

            # Test with stopped VM
            stopped_vm = fixtures.VMS[0]
            stopped_vm.status = fixtures.openshift_types.VMStatus.STOPPED
            api.get_vm_info.return_value = stopped_vm
            api.reset_mock()

            publication.op_create_completed()
            api.stop_vm_instance.assert_not_called()

    def test_publication_destroy(self) -> None:
        """
        Test publication destruction
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service(provider=provider)
            publication = fixtures.create_publication(service=service)
            publication._name = 'test-vm'

            state = publication.destroy()
            self.assertEqual(state, types.states.State.RUNNING)

            # Check state should call delete
            state = publication.check_state()
            self.assertEqual(state, types.states.State.RUNNING)
            api.delete_vm_instance.assert_called_with('test-vm')

    def test_get_template_id(self) -> None:
        """
        Test template ID retrieval
        """
        service = fixtures.create_service()
        publication = fixtures.create_publication(service=service)
        publication._name = 'test-template'

        template_id = publication.get_template_id()
        self.assertEqual(template_id, 'test-template')