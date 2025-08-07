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

from . import fixtures

from ...utils.test import UDSTransactionTestCase
from ...utils import MustBeOfType
from ...utils.helpers import limited_iterator

from uds.services.Xen.xen import types as xen_types

# USe transactional, used by publication access to db on "removal"
class TestXenPublication(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clean()

    def test_publication(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)

            state = publication.publish()
            # Wait until  types.services.Operation.CREATE_COMPLETED
            for _ in limited_iterator(
                lambda: publication._queue[0] != types.services.Operation.CREATE_COMPLETED, 10
            ):
                state = publication.check_state()

            self.assertEqual(state, types.states.State.RUNNING)
            api.clone_vm.assert_called_once_with(
                service.machine.value,
                publication._name,
                MustBeOfType(str),
            )
            # And should end in next call
            self.assertEqual(publication.check_state(), types.states.State.FINISHED)
            # Must have vmid, and must match machine() result
            self.assertEqual(publication.get_template_id(), publication._vmid)

    def test_publication_error(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Ensure state check returns error
            fixtures.TASK_INFO.result = 'ERROR, BOOM!'
            fixtures.TASK_INFO.status = xen_types.TaskStatus.FAILURE

            state = publication.publish()
            self.assertEqual(
                state,
                types.states.State.RUNNING,
                f'State is not running: publication._queue={publication._queue}',
            )

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, 128):
                state = publication.check_state()

            try:
                api.clone_vm.assert_called_once_with(
                    service.machine.value,
                    publication._name,
                    MustBeOfType(str),
                )
            except AssertionError:
                self.fail(f'Clone machine not called: {api.mock_calls}  //  {publication._queue}')
            self.assertEqual(state, types.states.State.ERROR)
            self.assertEqual(publication.error_reason(), 'ERROR, BOOM!')

    def test_publication_destroy(self) -> None:
        vmid = str(fixtures.VMS_INFO[0].opaque_ref)
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)
           
            service.must_stop_before_deletion = False  # avoid stop before deletion, not needed for this test

            # Destroy
            publication._vmid = vmid
            state = publication.destroy()
            self.assertEqual(state, types.states.State.RUNNING)
            api.delete_vm.assert_not_called()
            # check state should return RUNNING, and call api.delete_vm
            state = publication.check_state()
            self.assertEqual(state, types.states.State.RUNNING)
            # Should call api.delete_vm with the template id
            api.delete_vm.assert_called_once_with(publication.get_template_id())

            # Now, destroy again, should do nothing more
            state = publication.destroy()
            # Should not call again
            api.delete_vm.assert_called_once_with(publication.get_template_id())

            self.assertEqual(state, types.states.State.RUNNING)

    def test_publication_destroy_error(self) -> None:
        vmid = str(fixtures.VMS_INFO[0].opaque_ref)
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)
            
            service.must_stop_before_deletion = False  # avoid stop before deletion, not needed for this test

            # Now, destroy in fact will not return error, because it will
            # queue the operation if failed, but api.remove_machine will be called anyway
            publication._vmid = vmid
            api.delete_vm.side_effect = Exception('BOOM!')
            publication._vmid = vmid
            # destroy, in Xen, will call delete_vm on invocation (not queued), but deferred delete will enqueue it if errored
            # wo destroy will end find
            self.assertEqual(publication.destroy(), types.states.State.RUNNING)
            api.delete_vm.assert_not_called()
            # check state should return RUNNING, and call api.delete_vm
            state = publication.check_state()
            self.assertEqual(state, types.states.State.RUNNING)
            # Should call api.delete_vm with the template id
            # delete_vm should have been called once
            api.delete_vm.assert_called_with(publication.get_template_id())
            self.assertEqual(api.delete_vm.call_count, 1)

            # Ensure cancel calls destroy
            with mock.patch.object(publication, 'destroy') as destroy:
                publication.cancel()
                destroy.assert_called_with()
