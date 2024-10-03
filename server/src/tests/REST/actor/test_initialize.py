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
import functools
import logging

from uds import models
from uds.core import consts

from ...utils import rest
from ...fixtures import services as services_fixtures


logger = logging.getLogger(__name__)


class ActorInitializeTest(rest.test.RESTActorTestCase):
    """
    Test actor functionality
    """

    def invoke_success(
        self,
        type_: typing.Union[typing.Literal['managed'], typing.Literal['unmanaged']],
        token: str,
        *,
        mac: typing.Optional[str] = None,
        ip: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        response = self.client.post(
            '/uds/rest/actor/v3/initialize',
            data={
                'type': type_,
                'version': consts.system.VERSION,
                'token': token,
                'id': [{'mac': mac or '42:AC:11:22:33', 'ip': ip or '1.2.3.4'}],
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data['result'], dict)
        return data['result']

    def invoke_failure(
        self,
        type_: typing.Union[typing.Literal['managed'], typing.Literal['unmanaged']],
        token: str,
        *,
        mac: typing.Optional[str] = None,
        ip: typing.Optional[str] = None,
        expect_forbidden: bool = False,
    ) -> dict[str, typing.Any]:
        response = self.client.post(
            '/uds/rest/actor/v3/initialize',
            data={
                'type': type_,
                'version': consts.system.VERSION,
                'token': token,
                'id': [{'mac': mac or '42:AC:33:22:11', 'ip': ip or '4.3.2.1'}],
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200 if not expect_forbidden else 403)
        if expect_forbidden:
            return {}

        data = response.json()
        self.assertIsInstance(data['result'], dict)
        return data['result']

    def test_initialize_managed_by_mac(self) -> None:
        """
        Test actor initialize v3 for managed actor
        """
        user_service = self.user_service_managed

        actor_token = self.login_and_register()

        # Get the user service unique_id, the default
        unique_id = user_service.get_unique_id()

        success = functools.partial(self.invoke_success, 'managed', actor_token, ip='1.2.3.4')
        failure = functools.partial(self.invoke_failure, 'managed', ip='1.2.3.4')

        result = success(mac=unique_id)

        # Ensure own token is assigned
        self.assertEqual(result['token'], user_service.uuid)
        self.assertEqual(result['own_token'], result['token'])  # Compat value with 3.x actors

        # Ensure unique_id detected is ours
        self.assertEqual(result['unique_id'], unique_id)

        # Ensure os is set and it is a dict
        self.assertIsInstance(result['os'], dict)
        os = result['os']

        # Ensure requested action is rename
        self.assertEqual(os['action'], 'rename')
        # And name is userservice name
        self.assertEqual(os['name'], user_service.friendly_name)

        # Now invoke failure
        failure('invalid token', mac=unique_id, expect_forbidden=True)

        # Now invoke failure with valid token but invalid mac
        result = failure(actor_token, mac='invalid mac', expect_forbidden=False)

        self.assertIsNone(result['own_token'])
        self.assertIsNone(result['token'])
        self.assertIsNone(result['os'])
        self.assertIsNone(result['unique_id'])

    def test_initialize_managed_by_ip(self) -> None:
        """
        Test actor initialize v3 for managed actor, same as previous but using ip instead of mac
        """
        user_service = services_fixtures.create_db_one_assigned_userservice(
            self.provider,
            self.admins[0],
            self.groups,
            'managed',
        )
        
        # Set an IP as unique_id
        unique_id = '1.2.3.4'
        user_service.unique_id = unique_id
        user_service.save()

        actor_token = self.login_and_register()

        success = functools.partial(self.invoke_success, 'managed', actor_token, mac='42:AC:99:99:99')
        failure = functools.partial(self.invoke_failure, 'managed', mac='42:AC:99:99:99')

        result = success(ip=unique_id)

        # Ensure own token is assigned
        self.assertEqual(result['token'], user_service.uuid)
        self.assertEqual(result['own_token'], result['token'])  # Compat value with 3.x actors

        # Ensure unique_id detected is ours
        self.assertEqual(result['unique_id'], unique_id)

        # Ensure os is set and it is a dict
        self.assertIsInstance(result['os'], dict)
        os = result['os']

        # Ensure requested action is rename
        self.assertEqual(os['action'], 'rename')
        # And name is userservice name
        self.assertEqual(os['name'], user_service.friendly_name)

        # Now invoke failure
        failure('invalid token', ip=unique_id, expect_forbidden=True)

        # Now invoke failure with valid token but invalid ip
        result = failure(actor_token, ip='invalid ip', expect_forbidden=False)

        self.assertIsNone(result['own_token'])
        self.assertIsNone(result['token'])
        self.assertIsNone(result['os'])
        self.assertIsNone(result['unique_id'])

    def test_initialize_unmanaged_by_mac(self) -> None:
        """
        Test actor initialize v3 for unmanaged actor
        """
        userservice = self.userservice_unmanaged
        actor_token: str = (
            userservice.deployed_service.service.token if userservice.deployed_service.service else None
        ) or ''
        
        if actor_token == '':
            self.fail('Service token not found')

        success = functools.partial(self.invoke_success, 'unmanaged')
        failure = functools.partial(self.invoke_failure, 'unmanaged')

        NONEXISTING_MAC: typing.Final[str] = '00:00:00:00:00:00'
        USERSERVICE_MAC: typing.Final[str] = userservice.get_unique_id()

        # This will succeed, but only alias token is returned because MAC is not registered by UDS
        result = success(
            actor_token,
            mac=NONEXISTING_MAC,
        )

        # Unmanaged host is the response for initialization of unmanaged actor ALWAYS
        self.assertIsInstance(result['master_token'], str)
        self.assertIsNone(result['unique_id'])
        self.assertIsNone(result['os'])
        self.assertIsNone(result['own_token'])
        self.assertIsNone(result['token'])

        alias_token = result['master_token']
        # Ensure that the alias returned is on alias db, and it points to the same service as the one we belong to
        alias = models.ServiceTokenAlias.objects.get(alias=alias_token)
        self.assertEqual(alias.service, userservice.deployed_service.service)
        self.assertEqual(alias.unique_id, NONEXISTING_MAC.lower())

        # If repeated, same token is returned
        result = success(
            actor_token,
            mac=NONEXISTING_MAC,
        )
        self.assertEqual(result['master_token'], alias_token)
        
        # Now, invoke with a correct mac (Exists os user services)
        result = success(
            actor_token,
            mac=USERSERVICE_MAC,
        )
        
        # Note that due the change of mac, a new alias is created
        alias_token = result['master_token']
        alias = models.ServiceTokenAlias.objects.get(alias=alias_token)
        self.assertEqual(alias.service, userservice.deployed_service.service)
        self.assertEqual(alias.unique_id, USERSERVICE_MAC.lower())
        
        self.assertEqual(USERSERVICE_MAC, result['unique_id'])
        self.assertEqual(result['own_token'], result['token'])
        self.assertEqual(result['token'], userservice.uuid)

        # Now, invoke with alias, result shouls be the same
        result2 = success(
            alias_token,
            mac=USERSERVICE_MAC,
        )

        # master_token should be the same as the alias token
        self.assertEqual(result, result2)
        #
        failure('invalid token', mac=USERSERVICE_MAC, expect_forbidden=True)

    def test_initialize_unmanaged_by_ip(self) -> None:
        """
        Test actor initialize v3 for unmanaged actor
        """
        userservice = services_fixtures.create_db_one_assigned_userservice(
            self.provider,
            self.admins[0],
            self.groups,
            'unmanaged',
        )
        # Set an IP as unique_id
        USERSERVICE_IP: typing.Final[str] = '1.2.3.4'
        userservice.unique_id = USERSERVICE_IP
        userservice.save()
        
        actor_token: str = (
            userservice.deployed_service.service.token if userservice.deployed_service.service else None
        ) or ''

        success = functools.partial(self.invoke_success, 'unmanaged', mac='00:00:00:00:00:00')
        failure = functools.partial(self.invoke_failure, 'unmanaged', mac='00:00:00:00:00:00')

        NONEXISTING_IP: typing.Final[str] = '00:00:00:00:00:00'

        # This will succeed, but only alias token is returned because MAC is not registered by UDS
        result = success(
            actor_token,
            ip=NONEXISTING_IP,
        )

        # Unmanaged host is the response for initialization of unmanaged actor ALWAYS
        self.assertIsInstance(result['master_token'], str)
        self.assertIsNone(result['unique_id'])
        self.assertIsNone(result['os'])
        self.assertIsNone(result['own_token'])
        self.assertIsNone(result['token'])


        alias_token = result['master_token']
        # Ensure that the alias returned is on alias db, and it points to the same service as the one we belong to
        alias = models.ServiceTokenAlias.objects.get(alias=alias_token)
        self.assertEqual(alias.service, userservice.deployed_service.service)
        self.assertEqual(alias.unique_id, NONEXISTING_IP.lower())

        # Now, invoke with a correct mac (Exists os user services)
        result = success(
            actor_token,
            mac=USERSERVICE_IP,
        )
        
        # Note that due the change of mac, a new alias is created
        alias_token = result['master_token']
        alias = models.ServiceTokenAlias.objects.get(alias=alias_token)
        self.assertEqual(alias.service, userservice.deployed_service.service)
        self.assertEqual(alias.unique_id, USERSERVICE_IP.lower())
        
        self.assertEqual(USERSERVICE_IP, result['unique_id'])
        self.assertEqual(result['own_token'], result['token'])
        self.assertEqual(result['token'], userservice.uuid)

        # Now, invoke with alias, result shouls be the same
        result2 = success(
            alias_token,
            mac=USERSERVICE_IP,
        )

        # master_token should be the same as the alias token
        self.assertEqual(result, result2)
        #
        failure('invalid token', mac=USERSERVICE_IP, expect_forbidden=True)
