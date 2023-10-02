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
from uds.core import types, consts
from uds.core.managers import crypto
from uds.core.util import log


from ...utils import rest, random_ip_v4, random_ip_v6, random_mac, random_hostname

if typing.TYPE_CHECKING:
    from ...utils.test import UDSHttpResponse

logger = logging.getLogger(__name__)


class ServerRegisterTest(rest.test.RESTTestCase):
    """
    Test server functionality
    """

    _data: typing.Dict[str, typing.Any]

    def setUp(self) -> None:
        super().setUp()
        self._data = {
            'ip': '',  # To be set on tests
            'port': consts.SERVER_DEFAULT_LISTEN_PORT,
            'type': '',  # To be set on tests
            'subtype': crypto.CryptoManager.manager().randomString(10),
            'os': '',  # To be set on tests
            'hostname': 'test',
            'log_level': log.LogLevel.INFO.value,
            'mac': random_mac(),
        }
        self.login(as_admin=False)  # As staff
        
    def ip_type_os_generator(self) -> typing.Generator[typing.Tuple[str, int, str], None, None]:
        for ip_v in 4, 6:
            for type in types.servers.ServerType:
                for os in types.os.KnownOS:
                    ip = random_ip_v4() if ip_v == 4 else random_ip_v6()
                    yield ip, type.value, os.value[0]

    def test_valid_register(self) -> None:
        """
        Test server rest api registration
        """
        response: 'UDSHttpResponse'

        for ip, type, os in self.ip_type_os_generator():
            self._data['hostname'] = random_hostname()
            self._data['ip'] = ip
            self._data['port'] = 1234
            self._data['mac'] = random_mac()
            self._data['type'] = type
            self._data['os'] = os
            response = self.client.rest_post(
                'servers/register',
                data=self._data,
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            # This is the server token, should exist on self._database
            token = response.json()['result']

            server = models.Server.objects.get(token=token)
            self.assertEqual(server.ip, self._data['ip'])
            self.assertEqual(server.listen_port, self._data['port'])
            self.assertEqual(server.type, self._data['type'])
            self.assertEqual(server.subtype, self._data['subtype'])
            self.assertEqual(server.mac, self._data['mac'])
            self.assertEqual(server.hostname, self._data['hostname'])
            self.assertEqual(server.log_level, self._data['log_level'])
            self.assertEqual(server.os_type, self._data['os'].lower())

            # Second register from same ip and type will update hostname, mac and subtype
            self._data2 = self._data.copy()
            self._data2['ip'] = random_ip_v4()
            self._data2['subtype'] = 'test2'
            self._data2['mac'] = random_mac()
            self._data2['os'] = (
                types.os.KnownOS.UNKNOWN.value[0]
                if os != types.os.KnownOS.UNKNOWN
                else types.os.KnownOS.WINDOWS.value[0]
            )
            response = self.client.rest_post(
                'servers/register',
                data=self._data2,
                content_type='application/json',
            )

            token2 = response.json()['result']  # Same as token
            self.assertEqual(token, token2)

            server = models.Server.objects.get(token=token)

            self.assertEqual(server.hostname, self._data['hostname'])
            self.assertEqual(server.type, self._data2['type'])
            self.assertEqual(server.subtype, self._data2['subtype'])
            self.assertEqual(server.hostname, self._data2['hostname'])
            self.assertEqual(server.mac, self._data2['mac'])
            # Rest of fields should be the same

    def test_invalid_register(self) -> None:
        response: 'UDSHttpResponse'
        
        def _do_test(where: str) -> None:
            response = self.client.rest_post(
                'servers/register',
                data=self._data,
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn('valid', response.content.decode().lower(), where) # Not valid or invalid match
            
        
        for ip, type, os in self.ip_type_os_generator():
            # Invalid IP
            self._data['ip'] = 'invalid ip'
            self._data['type'] = type
            self._data['os'] = os
            _do_test('invalid ip')
            # Invalid port
            self._data['ip'] = ip
            self._data['port'] = 0
            _do_test('invalid port')
            # Invalid type
            self._data['ip'] = ip
            self._data['type'] = 'x' * 32
            _do_test('invalid type')
            # Invalid subtype
            self._data['type'] = type
            self._data['subtype'] = 'x' * 32
            _do_test('invalid subtype')
            # Invalid os
            self._data['subtype'] = ''
            self._data['os'] = 'x' * 32
            _do_test('invalid os')
            # Invalid hostname
            self._data['os'] = os
            self._data['hostname'] = 'x' * 256
            _do_test('invalid hostname')
            # Invalid mac
            self._data['hostname'] = 'test'
            self._data['mac'] = 'x' * 32
            _do_test('invalid mac')
            # Invalid json
            self._data['mac'] = random_mac()
            self._data['data'] = 'invalid json'
            _do_test('invalid json')
            
    def test_invalid_user_not_staff_or_admin(self) -> None:
        self.login(self.plain_users[0])
        # Login successfull, but not admin or staff
        # Data is invalid, but we will get a 403 because we are not admin or staff
        response = self.client.rest_post(
            'servers/register',
            data=self._data,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn('denied', response.content.decode().lower())

