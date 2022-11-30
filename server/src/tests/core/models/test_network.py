# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import logging

from uds.models import Network

from ...utils.test import UDSTestCase

NET_IPV4_TEMPLATE = '192.168.{}.0/24'
NET_IPV6_TEMPLATE = '2001:db8:85a3:8d3:13{:02x}::/64'

logger = logging.getLogger(__name__)

class NetworkModelTest(UDSTestCase):
    nets: 'typing.List[Network]'

    def setUp(self) -> None:
        super().setUp()
        self.nets = []
        for i in range(0, 255, 15):
            n = Network()
            n.name = f'{i}'
            if i % 2 == 0:
                n.net_string = f'192.168.{i}.0/24'
            else:  # ipv6 net
                n.net_string = f'2001:db8:85a3:8d3:13{i:02x}::/64'
            n.save()
            self.nets.append(n)
    
    def testNetworks(self) -> None:
        for n in self.nets:
            i = int(n.name)
            if i % 2 == 0:  # ipv4 net
                self.assertEqual(n.net_string, NET_IPV4_TEMPLATE.format(i))
                # Test some ips in range are in net
                for r in range(0, 256, 15):
                    self.assertTrue(n.contains(f'192.168.{i}.{r}'), f'192.168.{i}.{r} is not in {n.net_string}')
                    self.assertTrue(f'192.168.{i}.{r}' in n, f'192.168.{i}.{r} is not in {n.net_string}')
            else:  # ipv6 net
                self.assertEqual(n.net_string, NET_IPV6_TEMPLATE.format(i))
                # Test some ips in range are in net
                for r in range(0, 65536, 255):
                    self.assertTrue(n.contains(f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}::'), f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}:: is not in {n.net_string}')
                    self.assertTrue(f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}::' in n, f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}:: is not in {n.net_string}')
                    self.assertTrue(n.contains(f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}:{r:04x}::'), f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}:{r:04x}:: is not in {n.net_string}')
                    self.assertTrue(f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}:{r:04x}::' in n, f'2001:db8:85a3:8d3:13{i:02x}:{r:04x}:{r:04x}:: is not in {n.net_string}')
