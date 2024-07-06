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

from uds.services.Proxmox.proxmox import (
    types as prox_types,
    client as prox_client,
)

from tests.utils import vars

from tests.utils.test import UDSTransactionTestCase

logger = logging.getLogger(__name__)


class TestProxmoxClient(UDSTransactionTestCase):
    resource_group_name: str

    pclient: prox_client.ProxmoxClient
    
    vm: prox_types.VMInfo = prox_types.VMInfo.null()
    pool: prox_types.PoolInfo = prox_types.PoolInfo.null()

    def setUp(self) -> None:
        v = vars.get_vars('proxmox')
        if not v:
            self.skipTest('No proxmox vars')

        self.pclient = prox_client.ProxmoxClient(
            host=v['host'],
            port=int(v['port']),
            username=v['username'],
            password=v['password'],
            verify_ssl=True,
        )
        
        for vm in self.pclient.list_vms():
            if vm.name == v['test_vm']:
                self.vm = vm
                
        if self.vm.is_null():
            self.skipTest('No test vm found')

        for pool in self.pclient.list_pools():
            if pool.id == v['test_pool']:  # id is the pool name in proxmox
                self.pool = pool
