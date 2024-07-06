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

from tests.utils import MustBeOfType
from uds import models
from uds.core import types


from . import fixtures

from ...utils.test import UDSTransactionTestCase
from ...utils.helpers import limited_iterator

from uds.services.Xen.xen import types as xen_types

# We use transactions on some related methods (storage access, etc...)
class TestXenLinkedUserService(UDSTransactionTestCase):
    def setUp(self) -> None:
        fixtures.clean()
        fixtures.set_all_vm_state(xen_types.PowerState.HALTED)

    def test_userservice_linked_cache_l1(self) -> None:
        """
        Test the user service
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            userservice = fixtures.create_userservice_linked(service=service)
            publication = userservice.publication()
            publication._vmid = '1'

            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)

            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Ensure that in the event of failure, we don't loop forever
            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED, userservice._error_debug_info)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            # api.deploy_from_template, api.provision_vm, api.start_vm and api.get_vm_info should have been called
            api.deploy_from_template.assert_called_with(publication._vmid, MustBeOfType(str))
            api.provision_vm.assert_called_with(userservice._vmid)
            api.configure_vm.assert_called_with(userservice._vmid, mac_info=MustBeOfType(dict), memory=MustBeOfType(int))
            api.start_vm.assert_called_with(userservice._vmid)

    def test_userservice_linked_cache_l2(self) -> None:
        """
        Test the user service
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            userservice = fixtures.create_userservice_linked(service=service)

            publication = userservice.publication()
            publication._vmid = '1'

            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L2)

            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

                # If first item in queue is WAIT, we must "simulate" the wake up from os manager
                if userservice._queue[0] == types.services.Operation.WAIT:
                    userservice.process_ready_from_os_manager(None)

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            # api.deploy_from_template, api.provision_vm, api.start_vm and api.get_vm_info should have been called
            api.deploy_from_template.assert_called_with(publication._vmid, MustBeOfType(str))
            api.provision_vm.assert_called_with(userservice._vmid)
            api.configure_vm.assert_called_with(userservice._vmid, mac_info=MustBeOfType(dict), memory=MustBeOfType(int))
            api.start_vm.assert_called_with(userservice._vmid)
            api.shutdown_vm.assert_called_with(userservice._vmid)
            
    def test_userservice_linked_user(self) -> None:
        """
        Test the user service
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            service = fixtures.create_service_linked(provider=provider)
            userservice = fixtures.create_userservice_linked(service=service)

            publication = userservice.publication()
            publication._vmid = '1'

            state = userservice.deploy_for_user(models.User())

            self.assertEqual(state, types.states.TaskState.RUNNING)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()

            self.assertEqual(
                state,
                types.states.TaskState.FINISHED,
                f'Queue: {userservice._queue}, reason: {userservice._reason}, extra_info: {userservice._error_debug_info}',
            )

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            # api.deploy_from_template, api.provision_vm, api.start_vm and api.get_vm_info should have been called
            api.deploy_from_template.assert_called_with(publication._vmid, MustBeOfType(str))
            api.provision_vm.assert_called_with(userservice._vmid)
            api.configure_vm.assert_called_with(userservice._vmid, mac_info=MustBeOfType(dict), memory=MustBeOfType(int))
            api.start_vm.assert_called_with(userservice._vmid)

            # Ensure vm is stopped, because deployment should have started it (as api.start_machine was called)
            api.stop_vm(userservice._vmid)
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
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api)
            for graceful in [True, False]:
                service = fixtures.create_service_linked(provider=provider)
                userservice = fixtures.create_userservice_linked(service=service)
                service.try_soft_shutdown.value = graceful
                publication = userservice.publication()
                publication._vmid = '1'
                
                service.must_stop_before_deletion = False  # avoid stop before deletion, not needed for this test
                
                fixtures.set_all_vm_state(xen_types.PowerState.RUNNING)

                state = userservice.deploy_for_user(models.User())

                self.assertEqual(state, types.states.TaskState.RUNNING)

                # Invoke cancel
                api.reset_mock()
                state = userservice.cancel()

                self.assertEqual(state, types.states.TaskState.RUNNING)
                # Ensure DESTROY_VALIDATOR is in the queue
                self.assertIn(types.services.Operation.DESTROY_VALIDATOR, userservice._queue)

                for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                    state = userservice.check_state()

                # Now, should be finished without any problem, no call to api should have been done
                self.assertEqual(state, types.states.TaskState.FINISHED)
                self.assertEqual(len(api.mock_calls), 0)

                # Now again, but process check_queue a couple of times before cancel
                # we we have an _vmid
                state = userservice.deploy_for_user(models.User())
                self.assertEqual(state, types.states.TaskState.RUNNING)
                for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                    state = userservice.check_state()
                    if userservice._vmid:
                        break

                current_op = userservice._current_op()
                state = userservice.cancel()
                self.assertEqual(state, types.states.TaskState.RUNNING)
                self.assertEqual(userservice._queue[0], current_op)
                if graceful:
                    self.assertIn(types.services.Operation.SHUTDOWN, userservice._queue)
                    self.assertIn(types.services.Operation.SHUTDOWN_COMPLETED, userservice._queue)

                self.assertIn(types.services.Operation.STOP, userservice._queue)
                self.assertIn(types.services.Operation.STOP_COMPLETED, userservice._queue)
                self.assertIn(types.services.Operation.DELETE, userservice._queue)
                self.assertIn(types.services.Operation.DELETE_COMPLETED, userservice._queue)

                for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                    state = userservice.check_state()
                    if counter > 5:
                        fixtures.set_all_vm_state(xen_types.PowerState.HALTED)

                self.assertEqual(state, types.states.TaskState.FINISHED)

                if graceful:
                    api.shutdown_vm.assert_called()
                else:
                    api.stop_vm.assert_called()

    def test_userservice_basics(self) -> None:
        with fixtures.patched_provider():
            userservice = fixtures.create_userservice_linked()
            userservice.set_ip('1.2.3.4')
            self.assertEqual(userservice.get_ip(), '1.2.3.4')
