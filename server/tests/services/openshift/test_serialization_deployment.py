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
import pickle

from tests.services.openshift import fixtures

from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftDeploymentSerialization(UDSTransactionTestCase):
    def setUp(self) -> None:
        fixtures.clear()

    def test_userservice_serialization(self) -> None:
        """
        Test user service serialization
        """
        userservice = fixtures.create_userservice()
        userservice._name = 'test-vm'
        userservice._ip = '192.168.1.100'
        userservice._mac = '00:11:22:33:44:55'
        userservice._vmid = 'test-vm-id'

        # Serialize and deserialize
        data = pickle.dumps(userservice)
        userservice2 = pickle.loads(data)

        self.assertEqual(userservice2._name, 'test-vm')
        self.assertEqual(userservice2._ip, '192.168.1.100')
        self.assertEqual(userservice2._mac, '00:11:22:33:44:55')
        self.assertEqual(userservice2._vmid, 'test-vm-id')

    def test_userservice_methods_after_serialization(self) -> None:
        """
        Test user service methods after serialization
        """
        userservice = fixtures.create_userservice()
        userservice._name = 'test-vm'
        userservice._ip = '192.168.1.100'
        userservice._mac = '00:11:22:33:44:55'

        # Serialize and deserialize
        data = pickle.dumps(userservice)
        userservice2 = pickle.loads(data)

        # Test methods after serialization
        self.assertEqual(userservice2.get_name(), 'test-vm')
        self.assertEqual(userservice2.get_ip(), '192.168.1.100')
        self.assertEqual(userservice2.get_mac(), '00:11:22:33:44:55')
        self.assertEqual(userservice2.get_unique_id(), 'test-vm')

    def test_userservice_state_after_serialization(self) -> None:
        """
        Test user service state after serialization
        """
        userservice = fixtures.create_userservice()
        userservice._name = 'test-vm'
        userservice._reason = 'test-task'

        # Serialize and deserialize
        data = pickle.dumps(userservice)
        userservice2 = pickle.loads(data)

        self.assertEqual(userservice2._name, 'test-vm')
        self.assertEqual(userservice2._reason, 'test-task')