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
from uds.core import types
from uds.services.Proxmox.deployment_linked import Operation

from . import fixtures

from ...utils.test import UDSTransactionTestCase
from ...utils.generators import limited_iterator


# We use transactions on some related methods (storage access, etc...)
class TestProxmovLinkedService(UDSTransactionTestCase):
    def setUp(self) -> None:
        # Set machine state for fixture to started
        fixtures.VMS_INFO = [
            fixtures.VMS_INFO[i]._replace(status='stopped') for i in range(len(fixtures.VMS_INFO))
        ]
        

    def test_userservice_linked_cache_l1(self) -> None:
        """
        Test the user service
        """
        with fixtures.patch_provider_api() as api:
            userservice = fixtures.create_userservice_linked()
            service = userservice.service()
            publication = userservice.publication()
            publication._vmid = '1'

            state = userservice.deploy_for_cache(level=1)

            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Ensure that in the event of failure, we don't loop forever
            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            vmid = int(userservice._vmid)

            api.clone_machine.assert_called_with(
                publication.machine(),
                mock.ANY,
                userservice._name,
                mock.ANY,
                True,
                None,
                service.datastore.value,
                service.pool.value,
                None,
            )

            # api.get_task should have been invoked at least once
            self.assertTrue(api.get_task.called)

            api.enable_machine_ha.assert_called()

            api.set_machine_mac.assert_called_with(vmid, userservice._mac)
            api.get_machine_pool_info.assert_called_with(vmid, service.pool.value, force=True)
            api.start_machine.assert_called_with(vmid)

    def test_userservice_linked_cache_l2_no_ha(self) -> None:
        """
        Test the user service
        """
        with fixtures.patch_provider_api() as api:
            userservice = fixtures.create_userservice_linked()
            service = userservice.service()
            service.ha.value = '__'  # Disabled

            # Set machine state for fixture to started
            fixtures.VMS_INFO = [
                fixtures.VMS_INFO[i]._replace(status='running') for i in range(len(fixtures.VMS_INFO))
            ]

            publication = userservice.publication()
            publication._vmid = '1'

            state = userservice.deploy_for_cache(level=2)

            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            vmid = int(userservice._vmid)

            api.clone_machine.assert_called_with(
                publication.machine(),
                mock.ANY,
                userservice._name,
                mock.ANY,
                True,
                None,
                service.datastore.value,
                service.pool.value,
                None,
            )

            # api.get_task should have been invoked at least once
            self.assertTrue(api.get_task.called)

            # Shoud not have been called since HA is disabled
            api.enable_machine_ha.assert_not_called()

            api.set_machine_mac.assert_called_with(vmid, userservice._mac)
            api.get_machine_pool_info.assert_called_with(vmid, service.pool.value, force=True)
            # Now, called should not have been called because machine is running
            # api.start_machine.assert_called_with(vmid)
            # Stop machine should have been called
            api.shutdown_machine.assert_called_with(vmid)

    def test_userservice_linked_user(self) -> None:
        """
        Test the user service
        """
        with fixtures.patch_provider_api() as api:
            userservice = fixtures.create_userservice_linked()
            service = userservice.service()

            publication = userservice.publication()
            publication._vmid = '1'

            state = userservice.deploy_for_user(models.User())

            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            vmid = int(userservice._vmid)

            api.clone_machine.assert_called_with(
                publication.machine(),
                mock.ANY,
                userservice._name,
                mock.ANY,
                True,
                None,
                service.datastore.value,
                service.pool.value,
                None,
            )

            # api.get_task should have been invoked at least once
            self.assertTrue(api.get_task.called)

            api.enable_machine_ha.assert_called()

            api.set_machine_mac.assert_called_with(vmid, userservice._mac)
            api.get_machine_pool_info.assert_called_with(vmid, service.pool.value, force=True)
            api.start_machine.assert_called_with(vmid)
            
            # Set ready state with the valid machine
            state = userservice.set_ready()
            # Machine is stopped, so task must be RUNNING (opossed to FINISHED)
            self.assertEqual(state, types.states.TaskState.RUNNING)
            
            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=32):
                state = userservice.check_state()
                
            # Should be finished now
            self.assertEqual(state, types.states.TaskState.FINISHED)

    def test_userservice_cancel(self) -> None:
        """
        Test the user service
        """
        with fixtures.patch_provider_api() as _api:
            for graceful in [True, False]:
                userservice = fixtures.create_userservice_linked()
                service = userservice.service()
                service.try_soft_shutdown.value = graceful
                publication = userservice.publication()
                publication._vmid = '1'

                # Set machine state for fixture to started
                fixtures.VMS_INFO = [
                    fixtures.VMS_INFO[i]._replace(status='running') for i in range(len(fixtures.VMS_INFO))
                ]

                state = userservice.deploy_for_user(models.User())

                self.assertEqual(state, types.states.TaskState.RUNNING)

                current_op = userservice._get_current_op()

                # Invoke cancel
                state = userservice.cancel()

                self.assertEqual(state, types.states.TaskState.RUNNING)

                self.assertEqual(
                    userservice._queue,
                    [current_op]
                    + ([Operation.GRACEFUL_STOP] if graceful else [])
                    + [Operation.STOP, Operation.REMOVE, Operation.FINISH],
                )

                for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                    state = userservice.check_state()
                    if counter > 5:
                        # Set machine state for fixture to stopped
                        fixtures.VMS_INFO = [
                            fixtures.VMS_INFO[i]._replace(status='stopped')
                            for i in range(len(fixtures.VMS_INFO))
                        ]

                self.assertEqual(state, types.states.TaskState.FINISHED)

                if graceful:
                    _api.shutdown_machine.assert_called()
                else:
                    _api.stop_machine.assert_called()
