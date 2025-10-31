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

import logging

from uds.services.OpenShift.openshift import client as openshift_client
from tests.utils.test import UDSTransactionTestCase
from tests.utils import vars

logger = logging.getLogger(__name__)

class TestOpenshiftClient(UDSTransactionTestCase):
    """Tests for operations with OpenShiftClient."""

    os_client: openshift_client.OpenshiftClient
    test_vm: str = ''
    test_pool: str = ''
    test_storage: str = ''

    def setUp(self) -> None:
        v = vars.get_vars('openshift')
        if not v:
            self.skipTest('No OpenShift test variables found')

        self.os_client = openshift_client.OpenshiftClient(
            cluster_url=v['cluster_url'],
            api_url=v['api_url'],
            username=v['username'],
            password=v['password'],
            namespace=v['namespace'],
            timeout=int(v['timeout']),
            verify_ssl=v['verify_ssl'] == 'true',
        )
        self.test_vm = v.get('test_vm', '')
        self.test_pool = v.get('test_pool', '')
        self.test_storage = v.get('test_storage', '')

    # --- Token/API Tests ---
    def test_get_token(self) -> None:
        token = self.os_client.get_token()
        self.assertIsNotNone(token)

    def test_get_api_url(self) -> None:
        url = self.os_client.get_api_url('/test/path', ('param1', 'value1'))
        self.assertIn('/test/path', url)
        self.assertIn('param1=value1', url)

    def test_get_api_url_invalid(self):
        url = self.os_client.get_api_url('/invalid/path', ('param', 'value'))
        self.assertIn('/invalid/path', url)

    # --- VM Listing/Info Tests ---
    def test_list_vms(self) -> None:
        vms = self.os_client.list_vms()
        self.assertIsInstance(vms, list)
        if vms:
            info = self.os_client.get_vm_info(vms[0].name)
            self.assertIsNotNone(info)

    def test_list_vms_and_check_fields(self):
        vms = self.os_client.list_vms()
        self.assertIsInstance(vms, list)
        for vm in vms:
            self.assertTrue(hasattr(vm, 'name'))
            self.assertTrue(hasattr(vm, 'namespace'))

    def test_get_vm_info(self):
        if not self.test_vm:
            self.skipTest('No test_vm specified')
        info = self.os_client.get_vm_info(self.test_vm)
        self.assertIsNotNone(info)

    def test_get_vm_info_invalid(self):
        info = self.os_client.get_vm_info('nonexistent-vm')
        self.assertIsNone(info)

    def test_get_vm_instance_info(self):
        if not self.test_vm:
            self.skipTest('No test_vm specified')
        info = self.os_client.get_vm_instance_info(self.test_vm)
        self.assertTrue(info is None or hasattr(info, 'name'))

    def test_get_vm_instance_info_invalid(self):
        info = self.os_client.get_vm_instance_info('nonexistent-vm')
        self.assertIsNone(info)

    # --- VM Lifecycle and Actions ---
    def test_vm_lifecycle(self) -> None:
        self.skipTest('Skip this test to avoid issues in shared environments')
        if not self.test_vm:
            self.skipTest('No test_vm specified in test-vars.ini')
        self.assertTrue(self.os_client.start_vm_instance(self.test_vm))
        self.assertTrue(self.os_client.stop_vm_instance(self.test_vm))
        self.assertTrue(self.os_client.delete_vm_instance(self.test_vm))

    def test_start_stop_suspend_resume_vm(self):
        if not self.test_vm:
            self.skipTest('No test_vm specified')
        #self.assertTrue(self.os_client.start_vm_instance(self.test_vm))
        self.assertTrue(self.os_client.stop_vm_instance(self.test_vm))
        # Suspend/resume skipped if not supported

    def test_delete_vm_invalid(self):
        self.assertFalse(self.os_client.delete_vm_instance('nonexistent-vm'))

    # --- DataVolume Tests ---
    def test_datavolume_phase(self) -> None:
        phase = self.os_client.get_datavolume_phase('test-dv')
        self.assertIsInstance(phase, str)

    def test_datavolume_phase_invalid(self):
        phase = self.os_client.get_datavolume_phase('nonexistent-dv')
        self.assertIsInstance(phase, str)
