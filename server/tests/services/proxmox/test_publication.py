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
from ...utils.generators import limited_iterator


# USe transactional, used by publication access to db on "removal"
class TestProxmovPublication(UDSTransactionTestCase):

    def test_publication(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)

            state = publication.publish()
            # Wait until  types.services.Operation.CREATE_COMPLETED
            for _ in limited_iterator(lambda: publication._queue[0] != types.services.Operation.CREATE_COMPLETED, 10):
                state = publication.check_state()
            
            self.assertEqual(state, types.states.State.RUNNING)
            api.clone_machine.assert_called_once_with(
                publication.service().machine.as_int(),
                MustBeOfType(int),
                MustBeOfType(str),
                MustBeOfType(str),
                False,
                None,
                publication.service().datastore.value,
                publication.service().pool.value,
                None,
            )
            # And should end in next call
            self.assertEqual(publication.check_state(), types.states.State.FINISHED)
            # Must have vmid, and must match machine() result
            self.assertEqual(publication.machine(), int(publication._vmid))
            
            
    def test_publication_error(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Ensure state check returns error
            api.get_task.return_value = fixtures.TASK_STATUS._replace(
                status='stopped', exitstatus='ERROR, BOOM!'
            )

            state = publication.publish()
            self.assertEqual(state, types.states.State.RUNNING, f'State is not running: publication._queue={publication._queue}')
            
            # Wait until  types.services.Operation.CREATE_COMPLETED
            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, 128):
                state = publication.check_state()
            
            try:
                api.clone_machine.assert_called_once_with(
                    publication.service().machine.as_int(),
                    MustBeOfType(int),
                    MustBeOfType(str),
                    MustBeOfType(str),
                    False,
                    None,
                    publication.service().datastore.value,
                    publication.service().pool.value,
                    None,
                )
            except AssertionError:
                self.fail(f'Clone machine not called: {api.mock_calls}  //  {publication._queue}')
            self.assertEqual(state, types.states.State.ERROR)
            self.assertEqual(publication.error_reason(), 'ERROR, BOOM!')


    def test_publication_destroy(self) -> None:
        vmid = str(fixtures.VMS_INFO[0].vmid)
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Destroy
            publication._vmid = vmid
            state = publication.destroy()
            self.assertEqual(state, types.states.State.RUNNING)
            api.remove_machine.assert_called_once_with(publication.machine())

            # Now, destroy again, should do nothing more
            state = publication.destroy()
            # Should not call again
            api.remove_machine.assert_called_once_with(publication.machine())

            self.assertEqual(state, types.states.State.RUNNING)


    def test_publication_destroy_error(self) -> None:
        vmid = str(fixtures.VMS_INFO[0].vmid)
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_linked(provider=provider)
            publication = fixtures.create_publication(service=service)

            # Now, destroy in fact will not return error, because it will
            # queue the operation if failed, but api.remove_machine will be called anyway
            publication._vmid = vmid
            api.remove_machine.side_effect = Exception('BOOM!')
            publication._vmid = vmid
            self.assertEqual(publication.destroy(), types.states.State.RUNNING)
            api.remove_machine.assert_called_once_with(publication.machine())

            # Ensure cancel calls destroy
            with mock.patch.object(publication, 'destroy') as destroy:
                publication.cancel()
                destroy.assert_called_with()
