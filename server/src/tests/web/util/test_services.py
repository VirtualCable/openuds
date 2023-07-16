# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
# We use commit/rollback
import datetime
import typing
from unittest import mock

from uds import models
from uds.web.util import services
import uds.core.util.os_detector as osd

from ...utils.test import UDSTransactionTestCase
from ...fixtures import authenticators as fixtures_authenticators
from ...fixtures import services as fixtures_services


class TestGetServicesData(UDSTransactionTestCase):
    request: mock.Mock
    auth: models.Authenticator
    groups: typing.List[models.Group]
    user: models.User

    def setUp(self) -> None:
        # We need to create a user with some services
        self.auth = fixtures_authenticators.createAuthenticator()
        self.groups = fixtures_authenticators.createGroups(self.auth, 3)
        self.user = fixtures_authenticators.createUsers(
            self.auth, 1, groups=self.groups
        )[0]

        self.request = mock.Mock()
        self.request.user = self.user
        self.request.authorized = True
        self.request.session = {}
        self.request.ip = '127.0.0.1'
        self.request.ip_version = 4
        self.request.ip_proxy = '127.0.0.1'
        self.request.os = osd.DetectedOsInfo(
            osd.KnownOS.LINUX, osd.KnownBrowser.FIREFOX, 'Windows 10'
        )

        return super().setUp()

    def test_get_services_data(self) -> None:
        # Create 10 services, for this user
        user_services: typing.List[models.ServicePool] = []
        for i in range(10):
            user_services.append(
                fixtures_services.createCacheTestingUserServices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        data = services.getServicesData(self.request)
        now = datetime.datetime.now()
        # Will return this:
        #  return {
        #     'services': services,
        #     'ip': request.ip,
        #     'nets': nets,
        #     'transports': validTrans,
        #     'autorun': autorun,
        # }
        result_services: typing.Final[
            typing.List[typing.Mapping[str, typing.Any]]
        ] = data['services']
        self.assertEqual(len(result_services), 10)
        self.assertEqual(data['ip'], '127.0.0.1')
        self.assertEqual(len(data['nets']), 0)
        self.assertEqual(len(data['transports']), 0)
        self.assertEqual(data['autorun'], 0)

        # Check services data
        # Every service is returned like this:
        # return {
        #     'id': ('M' if is_meta else 'F') + uuid,
        #     'is_meta': is_meta,
        #     'name': name,
        #     'visual_name': visual_name,
        #     'description': description,
        #     'group': group,
        #     'transports': transports,
        #     'imageId': image and image.uuid or 'x',
        #     'show_transports': show_transports,
        #     'allow_users_remove': allow_users_remove,
        #     'allow_users_reset': allow_users_reset,
        #     'maintenance': maintenance,
        #     'not_accesible': not_accesible,
        #     'in_use': in_use,
        #     'to_be_replaced': to_be_replaced,
        #     'to_be_replaced_text': to_be_replaced_text,
        #     'custom_calendar_text': custom_calendar_text,
        # }
        for user_service in result_services:
            # Locate user service in user_services
            found: models.ServicePool = next(
                (x for x in user_services if x.uuid == user_service['id'][1:]),
                models.ServicePool(uuid='x'),
            )
            if found.uuid == 'x':
                self.fail('Pool not found in user_services list')

            self.assertEqual(user_service['is_meta'], False)
            self.assertEqual(user_service['name'], found.name)
            self.assertEqual(user_service['visual_name'], found.visual_name)
            self.assertEqual(user_service['description'], found.comments)
            self.assertEqual(
                user_service['group'], models.ServicePoolGroup.default().as_dict
            )
            self.assertEqual(
                [(i['id'], i['name']) for i in user_service['transports']],
                [(t.uuid, t.name) for t in found.transports.all()],
            )
            self.assertEqual(
                user_service['imageId'], found.image and found.image.uuid or 'x'
            )
            self.assertEqual(user_service['show_transports'], found.show_transports)
            self.assertEqual(
                user_service['allow_users_remove'], found.allow_users_remove
            )
            self.assertEqual(user_service['allow_users_reset'], found.allow_users_reset)
            self.assertEqual(
                user_service['maintenance'], found.service.provider.maintenance_mode
            )
            self.assertEqual(
                user_service['not_accesible'], not found.isAccessAllowed(now)
            )
            self.assertEqual(
                user_service['in_use'], found.userServices.filter(in_use=True).count()
            )
            self.assertEqual(user_service['to_be_replaced'], None)
            self.assertEqual(user_service['to_be_replaced_text'], '')
            self.assertEqual(user_service['custom_calendar_text'], '')

    def test_get_meta_services_data(self) -> None:
        # Create 10 services, for this user
        user_services: typing.List[models.ServicePool] = []
        for i in range(100):
            user_services.append(
                fixtures_services.createCacheTestingUserServices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        # Create 10 meta services, for this user
        meta_services: typing.List[models.MetaPool] = []
        for i in range(10):
            meta_services.append(
                fixtures_services.createMetaPool(
                    service_pools=user_services[i * 10 : (i + 1) * 10], groups=self.groups
                )
            )
                

        data = services.getServicesData(self.request)
        now = datetime.datetime.now()

        result_services: typing.Final[
            typing.List[typing.Mapping[str, typing.Any]]
        ] = data['services']
        self.assertEqual(len(result_services), 10)
        self.assertEqual(data['ip'], '127.0.0.1')
        self.assertEqual(len(data['nets']), 0)
        self.assertEqual(len(data['transports']), 0)
        self.assertEqual(data['autorun'], 0)

        for user_service in result_services:
            # Locate user service in user_services
            found: models.MetaPool = next(
                (x for x in meta_services if x.uuid == user_service['id'][1:]),
                models.MetaPool(uuid='x'),
            )
            if found.uuid == 'x':
                self.fail('Meta pool not found in user_services list')

            self.assertEqual(user_service['is_meta'], True)
            self.assertEqual(user_service['name'], found.name)
            self.assertEqual(user_service['visual_name'], found.visual_name)
            self.assertEqual(user_service['description'], found.comments)
            self.assertEqual(
                user_service['group'], models.ServicePoolGroup.default().as_dict
            )
            self.assertEqual(
                user_service['not_accesible'], not found.isAccessAllowed(now)
            )
            self.assertEqual(user_service['to_be_replaced'], None)
            self.assertEqual(user_service['to_be_replaced_text'], '')
            self.assertEqual(user_service['custom_calendar_text'], '')

    def test_get_meta_and_not_services_data(self) -> None:
        # Create 10 services, for this user
        user_services: typing.List[models.ServicePool] = []
        for i in range(110):
            user_services.append(
                fixtures_services.createCacheTestingUserServices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        # Create 10 meta services, for this user, last 10 user_services will not be added to meta pools
        meta_services: typing.List[models.MetaPool] = []
        for i in range(10):
            meta_services.append(
                fixtures_services.createMetaPool(
                    service_pools=user_services[i * 10 : (i + 1) * 10], groups=self.groups
                )
            )
                

        data = services.getServicesData(self.request)
        now = datetime.datetime.now()

        result_services: typing.Final[
            typing.List[typing.Mapping[str, typing.Any]]
        ] = data['services']
        self.assertEqual(len(result_services), 20)  # 10 metas and 10 normal pools
        # Some checks are ommited, because are already tested in other tests

        self.assertEqual(len(list(filter(lambda x: x['is_meta'], result_services))), 10)
        self.assertEqual(len(list(filter(lambda x: not x['is_meta'], result_services))), 10)

