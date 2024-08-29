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
from uds import models
from uds.core import types
from unittest import mock
from . import fixtures


from ...utils.test import UDSTransactionTestCase


class TestOpenstackFixedService(UDSTransactionTestCase):

    def test_service_fixed(self) -> None:
        """
        Test the service
        """
        for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
            with patcher() as prov:
                api = typing.cast(mock.MagicMock, prov.api())
                service = fixtures.create_fixed_service(prov)  # Will use provider patched api
                userservice = fixtures.create_fixed_userservice(service)

                # Test service is_available method
                self.assertTrue(service.is_avaliable())
                api.is_available.assert_called()

                # assignables should be same as service.macines
                assignables = set(i['id'] for i in service.enumerate_assignables())
                self.assertEqual(assignables, set(service.machines.value), f'legacy={prov.legacy}')

                # Remove one machine from fixtures servers_list (from the first one on service.machine.value)
                prev_servers_list = fixtures.SERVERS_LIST.copy()
                fixtures.SERVERS_LIST[:] = [
                    i for i in fixtures.SERVERS_LIST if i.id != service.machines.value[0]
                ]

                # Now should not return the first from service.machines.value
                assignables = set(i['id'] for i in service.enumerate_assignables())
                self.assertEqual(assignables, set(set(service.machines.value[1:])), f'legacy={prov.legacy}')

                # Restore servers_list and assignables
                fixtures.SERVERS_LIST[:] = prev_servers_list
                assignables = set(str(i['id']) for i in service.enumerate_assignables())

                to_assign = list(assignables)[0]

                # Assign one, and test it's not available anymore
                # First time, it will run the queue, so we should receive a RUNNING
                self.assertEqual(
                    service.assign_from_assignables(to_assign, models.User(), userservice),
                    types.states.TaskState.RUNNING,
                )

                # Now it's not on available list for any new user nor user service
                self.assertEqual(
                    set(i['id'] for i in service.enumerate_assignables()) ^ assignables,
                    {list(assignables)[0]},
                )

                # If called again, should return types.states.TaskState.ERROR beause it's already assigned
                self.assertEqual(
                    service.assign_from_assignables(to_assign, models.User(), userservice),
                    types.states.TaskState.ERROR,
                )

                # How many assignables machines are available?
                remaining = len(list(service.enumerate_assignables()))

                api.get_server_info.reset_mock()
                # Now get_and_assign_machine as much as remaining machines
                for _ in range(remaining):
                    vm = service.get_and_assign()
                    self.assertIn(vm, assignables)

                # enumarate_assignables should return an empty list now
                self.assertEqual(list(service.enumerate_assignables()), [])

                # And get_server should have been called remaining times
                self.assertEqual(api.get_server_info.call_count, remaining)

                # And a new try, should raise an exception
                self.assertRaises(Exception, service.get_and_assign)
