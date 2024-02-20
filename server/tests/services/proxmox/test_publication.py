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
import datetime
import collections.abc
import itertools
from unittest import mock

from uds.core import types, ui, environment
from uds.services.OpenNebula.on.vm import remove_machine
from uds.services.Proxmox.publication import ProxmoxPublication

from . import fixtures

from ...utils.test import UDSTestCase
from ...utils import MustBeOfType


class TestProxmovPublication(UDSTestCase):

    def test_publication(self) -> None:
        with fixtures.patch_provider_api() as api:
            publication = fixtures.create_publication()

            state = publication.publish()
            self.assertEqual(state, types.states.State.RUNNING)
            api.clone_machine.assert_called_with(
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
            running_task = fixtures.TASK_STATUS._replace(status='running')

            api.get_task.return_value = running_task
            state = publication.check_state()
            self.assertEqual(state, types.states.State.RUNNING)
            # Now ensure task is finished
            api.get_task.return_value = fixtures.TASK_STATUS._replace(status='stopped', exitstatus='OK')
            self.assertEqual(publication.check_state(), types.states.State.FINISHED)
            # Now, error
            publication._state = types.states.State.RUNNING
            api.get_task.return_value = fixtures.TASK_STATUS._replace(
                status='stopped', exitstatus='ERROR, BOOM!'
            )
            self.assertEqual(publication.check_state(), types.states.State.ERROR)
            self.assertEqual(publication.error_reason(), 'ERROR, BOOM!')

            publication._vmid = str(fixtures.VMS_INFO[0].vmid)
            self.assertEqual(publication.machine(), fixtures.VMS_INFO[0].vmid)

    def test_publication_destroy(self) -> None:
        vmid = str(fixtures.VMS_INFO[0].vmid)
        with fixtures.patch_provider_api() as api:
            publication = fixtures.create_publication()
            # Destroy
            publication._state = types.states.State.RUNNING
            publication._vmid = vmid
            state = publication.destroy()
            self.assertEqual(state, types.states.State.RUNNING)
            self.assertEqual(publication._destroy_after, True)

            # Now, destroy again
            state = publication.destroy()
            publication._vmid = vmid
            self.assertEqual(state, types.states.State.RUNNING)
            self.assertEqual(publication._destroy_after, False)
            self.assertEqual(publication._operation, 'd')
            self.assertEqual(publication._state, types.states.State.RUNNING)
            api.remove_machine.assert_called_with(publication.service().machine.as_int())

            # Now, repeat with finished state at the very beginning
            api.remove_machine.reset_mock()
            publication._state = types.states.State.FINISHED
            publication._vmid = vmid
            self.assertEqual(publication.destroy(), types.states.State.RUNNING)
            self.assertEqual(publication._destroy_after, False)
            self.assertEqual(publication._operation, 'd')
            self.assertEqual(publication._state, types.states.State.RUNNING)
            api.remove_machine.assert_called_with(publication.service().machine.as_int())

            # And now, with error
            api.remove_machine.side_effect = Exception('BOOM!')
            publication._state = types.states.State.FINISHED
            publication._vmid = vmid
            self.assertEqual(publication.destroy(), types.states.State.ERROR)
            self.assertEqual(publication.error_reason(), 'BOOM!')

            # Ensure cancel calls destroy
            with mock.patch.object(publication, 'destroy') as destroy:
                publication.cancel()
                destroy.assert_called_with()
