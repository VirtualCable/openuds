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

from uds.core import types, ui
from . import fixtures

from ...utils.test import UDSTransactionTestCase


class TestProxmovFixedService(UDSTransactionTestCase):

    def test_service_is_available(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_fixed(provider=provider)

            self.assertTrue(service.is_avaliable())
            api.test.assert_called_with()
            # With data cached, even if test fails, it will return True
            api.test.return_value = False
            self.assertTrue(service.is_avaliable())

            # Data is cached, so we need to reset it
            api.test.reset_mock()
            service.provider().is_available.cache_clear()  # type: ignore
            # Now should return False as we have reset the cache
            self.assertFalse(service.is_avaliable())
            api.test.assert_called_with()

    def test_service_methods_1(self) -> None:
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_fixed(provider=provider)

            self.assertEqual(service.get_machine_info(2).name, fixtures.VMS_INFO[1].name)

            # is_available is already tested, so we will skip it

            # Enumerate assignables
            locate_vm: typing.Callable[[str], typing.Any] = lambda vmid: next(
                (x for x in fixtures.VMS_INFO if x.vmid == int(vmid)), fixtures.VMS_INFO[0]
            )

            self.assertEqual(
                list(service.enumerate_assignables()),
                [
                    ui.gui.choice_item(locate_vm(x).vmid, locate_vm(x).name or '')
                    for x in typing.cast(list[str], fixtures.SERVICE_FIXED_VALUES_DICT['machines'])
                ],
            )

            vmid: str = typing.cast(list[str], fixtures.SERVICE_FIXED_VALUES_DICT['machines'])[0]
            # Assign from assignables
            with mock.patch('uds.services.Proxmox.service_fixed.ProxmoxUserServiceFixed') as userservice:
                userservice_instance = userservice.return_value
                userservice_instance.assign.return_value = 'OK'
                self.assertEqual(
                    service.assign_from_assignables(vmid, mock.MagicMock(), userservice_instance), 'OK'
                )
                userservice_instance.assign.assert_called_with(vmid)

                # vmid should be already assigned, so it will return an error (call error of userservice_instance)
                self.assertEqual(
                    service.assign_from_assignables(vmid, mock.MagicMock(), userservice_instance),
                    userservice_instance.error.return_value,
                )

            # Get and assign machine
            # will try to assign FIRST FREE machine, that is the second one
            vmid2: str = typing.cast(list[str], fixtures.SERVICE_FIXED_VALUES_DICT['machines'])[1]
            self.assertEqual(service.get_and_assign_machine(), vmid2)

            # Now two machies should be assigned
            with service._assigned_machines_access() as assigned_machines:
                self.assertEqual(assigned_machines, set([vmid, vmid2]))

    def test_service_methods_2(self) -> None:
        with fixtures.patched_provider() as provider:
            service = fixtures.create_service_fixed(provider=provider)

            # Get machine name
            self.assertEqual(service.get_machine_name('1'), fixtures.VMS_INFO[0].name)

            # Get first network mac
            self.assertEqual(
                service.get_first_network_mac('1'), fixtures.VMS_CONFIGURATION[0].networks[0].mac.lower()
            )

            # Get guest ip address
            self.assertEqual(service.get_guest_ip_address('1'), fixtures.GUEST_IP_ADDRESS)

            # Remove and free machine
            # Fist, assign a machine
            vmid = service.get_and_assign_machine()
            with service._assigned_machines_access() as assigned_machines:               
                self.assertEqual(assigned_machines, set([vmid]))

            # And now free it                
            self.assertEqual(service.remove_and_free_machine(vmid), types.states.State.FINISHED)
            with service._assigned_machines_access() as assigned_machines:
                self.assertEqual(assigned_machines, set())

    def test_process_snapshot(self) -> None:
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider._api())
            service = fixtures.create_service_fixed(provider=provider)

            vmid = typing.cast(list[str], fixtures.SERVICE_FIXED_VALUES_DICT['machines'])[0]
            userservice_instance = mock.MagicMock()
            userservice_instance._vmid = vmid

            # Create snapshot
            api.list_snapshots.return_value = []
            service.process_snapshot(False, userservice_instance)
            api.list_snapshots.assert_called_with(int(vmid), None)
            api.create_snapshot.assert_called_with(int(vmid), None, 'UDS Snapshot', None)

            # Skip snapshot creation
            api.reset_mock()
            api.list_snapshots.return_value = fixtures.SNAPSHOTS_INFO
            service.process_snapshot(False, userservice_instance)
            api.list_snapshots.assert_called_with(int(vmid), None)
            api.create_snapshot.assert_not_called()

            # Restore snapshot on exit
            # First, no snapshots, so no restore
            api.reset_mock()
            api.list_snapshots.return_value = []
            service.process_snapshot(True, userservice_instance)
            api.list_snapshots.assert_called_with(int(vmid), None)
            # no snapshots, so no restore
            api.restore_snapshot.assert_not_called()

            # Reset and add snapshot
            api.reset_mock()
            api.list_snapshots.return_value = fixtures.SNAPSHOTS_INFO
            service.process_snapshot(True, userservice_instance)
            api.list_snapshots.assert_called_with(int(vmid), None)
            # restore snapshot
            api.restore_snapshot.assert_called_with(int(vmid), None, fixtures.SNAPSHOTS_INFO[0].name)
