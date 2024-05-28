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
from uds import models
from uds.core import types

from uds.services.OVirt.deployment_linked import Operation
from uds.services.OVirt.ovirt import types as ov_types

from . import fixtures

from ... import utils
from ...utils.test import UDSTransactionTestCase
from ...utils.helpers import limited_iterator


# We use transactions on some related methods (storage access, etc...)
class TestOVirtLinkedService(UDSTransactionTestCase):
    def setUp(self) -> None:
        # Set machine state for fixture to
        for vm in fixtures.VMS_INFO:
            vm.status = ov_types.VMStatus.DOWN

    def test_max_check_works(self) -> None:
        # Tests that the userservice does not gets stuck in a loop if cannot complete some operation
        with fixtures.patch_provider_api() as _api:
            userservice = fixtures.create_linked_userservice()

            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)

            for _ in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                state = userservice.check_state()
                # Ensure machine status is always DOWN, so the test does not end
                utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid).status = ov_types.VMStatus.DOWN

            self.assertEqual(state, types.states.TaskState.ERROR)
            self.assertGreater(
                userservice._get_checks_counter(), 0
            )  # Should have any configured value, but greater than 0

    def test_userservice_linked_cache_l1(self) -> None:
        """
        Test the user service for cache l1
        """
        with fixtures.patch_provider_api() as api:
            userservice = fixtures.create_linked_userservice()

            service = userservice.service()
            service.usb.value = 'native'  # With usb

            _publication = userservice.publication()

            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L1)

            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Ensure that in the event of failure, we don't loop forever
            for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                # this user service expects the machine to be started at some point, so after a few iterations, we set it to started
                # note that the user service has a counter for max "recheck" without any success, and if reached, it will fail
                if counter == 12:
                    vm = utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid)
                    vm.status = ov_types.VMStatus.UP
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            # Assarts has an vmid
            self.assertTrue(bool(userservice._vmid))

            # Assert several deploy api methods has been called, no matter args
            # tested on other tests
            api.get_storage_info.assert_called()
            api.deploy_from_template.assert_called()
            api.get_machine_info.assert_called()
            api.update_machine_mac.assert_called()
            api.fix_usb.assert_called()
            api.start_machine.assert_called()

    def test_userservice_linked_cache_l2(self) -> None:
        """
        Test the user service for cache level 2
        """
        with fixtures.patch_provider_api() as api:
            userservice = fixtures.create_linked_userservice()

            service = userservice.service()
            service.usb.value = 'native'  # With usb

            _publication = userservice.publication()

            state = userservice.deploy_for_cache(level=types.services.CacheLevel.L2)

            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Ensure that in the event of failure, we don't loop forever
            for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                # this user service expects the machine to be started at some point, so after a few iterations, we set it to started
                # note that the user service has a counter for max "recheck" without any success, and if reached, it will fail
                if counter == 12:
                    vm = utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid)
                    vm.status = ov_types.VMStatus.UP
                # Again, machine will be suspended for L2, so we set it to suspended after a few iterations more
                if counter == 24:
                    vm = utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid)
                    vm.status = ov_types.VMStatus.SUSPENDED
                state = userservice.check_state()

                # If first item in queue is WAIT, we must "simulate" the wake up from os manager
                if userservice._queue[0] == Operation.WAIT:
                    state = userservice.process_ready_from_os_manager(None)

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            # Assarts has an vmid
            self.assertTrue(bool(userservice._vmid))

            # Assert several deploy api methods has been called, no matter args
            # tested on other tests
            api.get_storage_info.assert_called()
            api.deploy_from_template.assert_called()
            api.get_machine_info.assert_called()
            api.update_machine_mac.assert_called()
            api.fix_usb.assert_called()
            api.start_machine.assert_called()

    def test_userservice_linked_user(self) -> None:
        """
        Test the user service for user deployment
        """
        with fixtures.patch_provider_api() as api:
            userservice = fixtures.create_linked_userservice()

            service = userservice.service()
            service.usb.value = 'native'  # With usb

            _publication = userservice.publication()

            state = userservice.deploy_for_user(models.User())

            self.assertEqual(state, types.states.TaskState.RUNNING)

            # Ensure that in the event of failure, we don't loop forever
            for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                # this user service expects the machine to be started at some point, so after a few iterations, we set it to started
                # note that the user service has a counter for max "recheck" without any success, and if reached, it will fail
                if counter == 12:
                    vm = utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid)
                    vm.status = ov_types.VMStatus.UP
                state = userservice.check_state()

            self.assertEqual(state, types.states.TaskState.FINISHED)

            self.assertEqual(userservice._name[: len(service.get_basename())], service.get_basename())
            self.assertEqual(len(userservice._name), len(service.get_basename()) + service.get_lenname())

            # Assarts has an vmid
            self.assertTrue(bool(userservice._vmid))

            # Assert several deploy api methods has been called, no matter args
            # tested on other tests
            api.get_storage_info.assert_called()
            api.deploy_from_template.assert_called()
            api.get_machine_info.assert_called()
            api.update_machine_mac.assert_called()
            api.fix_usb.assert_called()
            api.start_machine.assert_called()

    def test_userservice_cancel(self) -> None:
        """
        Test the user service
        """
        with fixtures.patch_provider_api() as api:
            for graceful in [True, False]:
                userservice = fixtures.create_linked_userservice()
                service = userservice.service()
                service.try_soft_shutdown.value = graceful
                _publication = userservice.publication()

                state = userservice.deploy_for_user(models.User())

                # This is one of the "wrost" cases (once CREATE is done i mean)
                # if cancelled/destroyed while CREATE, the operation is even easier, because
                # create will finish with machine stopped, and then, the machine will be removed
                self.assertEqual(state, types.states.TaskState.RUNNING)
                # skip create and use next in queue
                userservice._queue.pop(0)  # Remove create
                # And ensure vm is up
                utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid).status = (
                    ov_types.VMStatus.UP
                )

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

                counter = 0
                for counter in limited_iterator(lambda: state == types.states.TaskState.RUNNING, limit=128):
                    state = userservice.check_state()
                    # Ensure that, after a few iterations, the machine is removed (state is UNKNOWN)
                    # if counter == 5:
                    #     utils.search_item_by_attr(fixtures.VMS_INFO, 'id', userservice._vmid).status = ov_types.VMStatus.UNKNOWN

                self.assertEqual(
                    state, types.states.TaskState.FINISHED, f'Graceful: {graceful}, Counter: {counter}'
                )

                if graceful:
                    api.shutdown_machine.assert_called()
                else:
                    api.stop_machine.assert_called()

                api.remove_machine.assert_called()
