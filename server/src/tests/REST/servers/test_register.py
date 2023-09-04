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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging

from uds import models
from uds.core import types
from uds.core.util import log

from ...utils import rest, constants, random_ip_v4, random_ip_v6, random_mac


logger = logging.getLogger(__name__)


class ServerRegisterTest(rest.test.RESTTestCase):
    """
    Test server functionality
    """

    def test_valid_register(self) -> None:
        """
        Test server rest api registration
        """
        data: typing.Dict[str, typing.Any] = {
            'ip': '',  # To be set on tests
            'type': '',  # To be set on tests
            'subtype': 'test',
            'os': '',  # To be set on tests
            'hostname': 'test',
            'log_level': log.LogLevel.INFO.value,
            'mac': '',  # To be set on tests
        }
        response: typing.Any

        token = self.login(as_admin=True)  # Token not used, alreade inserted on login

        for ip_v in 4, 6:
            for type in types.servers.ServerType:
                for os in types.os.KnownOS:
                    data['ip'] = random_ip_v4() if ip_v == 4 else random_ip_v6()
                    data['mac'] = random_mac()
                    data['type'] = type.value
                    data['os'] = os.value[0]
                    response = self.client.post(
                        '/uds/rest/servers/register',
                        data=data,
                        content_type='application/json',
                    )
                    self.assertEqual(response.status_code, 200)
                    # This is the server token, should exist on database
                    token = response.json()['result']

                    server = models.Server.objects.get(token=token)
                    self.assertEqual(server.ip, data['ip'])
                    self.assertEqual(server.type, data['type'])
                    self.assertEqual(server.subtype, data['subtype'])
                    self.assertEqual(server.mac, data['mac'])
                    self.assertEqual(server.hostname, data['hostname'])
                    self.assertEqual(server.log_level, data['log_level'])
                    self.assertEqual(server.os_type, data['os'].lower())

                    # Second register from same ip and type will update hostname, mac and subtype
                    data2 = data.copy()
                    data2['hostname'] = 'test2'
                    data2['subtype'] = 'test2'
                    data2['mac'] = random_mac()
                    data2['os'] = (
                        types.os.KnownOS.UNKNOWN.value[0]
                        if os != types.os.KnownOS.UNKNOWN
                        else types.os.KnownOS.WINDOWS.value[0]
                    )
                    response = self.client.post(
                        '/uds/rest/servers/register',
                        data=data2,
                        content_type='application/json',
                    )

                    token2 = response.json()['result']  # Same as token
                    self.assertEqual(token, token2)

                    server = models.Server.objects.get(token=token)

                    self.assertEqual(server.ip, data['ip'])
                    self.assertEqual(server.type, data2['type'])
                    self.assertEqual(server.subtype, data2['subtype'])
                    self.assertEqual(server.hostname, data2['hostname'])
                    self.assertEqual(server.mac, data2['mac'])
                    # Rest of fields should be the same
