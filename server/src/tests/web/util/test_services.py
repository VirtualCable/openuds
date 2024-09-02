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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import itertools
import random
import typing
from unittest import mock

from uds import models
from uds.core import consts, types
from uds.web.util import services

from ...fixtures import authenticators as fixtures_authenticators
from ...fixtures import services as fixtures_services
from ...utils.test import UDSTransactionTestCase


class TestGetServicesData(UDSTransactionTestCase):
    request: mock.Mock
    auth: models.Authenticator
    groups: list[models.Group]
    user: models.User
    transports: list[models.Transport]

    def setUp(self) -> None:
        # We need to create a user with some services
        self.auth = fixtures_authenticators.create_db_authenticator()
        self.groups = fixtures_authenticators.create_db_groups(self.auth, 3)
        self.user = fixtures_authenticators.create_db_users(self.auth, 1, groups=self.groups)[0]
        self.transports = [fixtures_services.create_db_transport(priority=counter, label=f'label{counter}') for counter in range(10)]

        self.request = mock.Mock()
        self.request.user = self.user
        self.request.authorized = True
        self.request.session = {}
        self.request.ip = '127.0.0.1'
        self.request.ip_version = 4
        self.request.ip_proxy = '127.0.0.1'
        self.request.os = types.os.DetectedOsInfo(
            types.os.KnownOS.LINUX, types.os.KnownBrowser.FIREFOX, 'Windows 10'
        )

        return super().setUp()

    def _create_metapools(
        self,
        grouping_method: types.pools.TransportSelectionPolicy,
        ha_policy: types.pools.HighAvailabilityPolicy = types.pools.HighAvailabilityPolicy.DISABLED,
    ) -> None:
        # Create 10 services, for this user
        service_pools: list[models.ServicePool] = []
        for i in range(110):
            service_pools.append(
                fixtures_services.create_db_assigned_userservices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        # Create 10 meta services, for this user, last 10 user_services will not be added to meta pools
        meta_services: list[models.MetaPool] = []
        for i in range(10):
            service_pool = fixtures_services.create_db_metapool(
                service_pools=service_pools[i * 10 : (i + 1) * 10],
                groups=self.groups,
                transport_grouping=grouping_method,
            )
            meta_services.append(service_pool)

    def test_get_services_data(self) -> None:
        # Create 10 services, for this user
        service_pools: list[models.ServicePool] = []
        for _i in range(10):
            service_pools.append(
                fixtures_services.create_db_assigned_userservices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        data = services.get_services_info_dict(self.request)
        now = datetime.datetime.now()
        # Will return this:
        #  return {
        #     'services': services,
        #     'ip': request.ip,
        #     'nets': nets,
        #     'transports': validTrans,
        #     'autorun': autorun,
        # }
        result_services: typing.Final[list[dict[str, typing.Any]]] = data['services']
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
                (x for x in service_pools if x.uuid == user_service['id'][1:]),
                models.ServicePool(uuid='x'),
            )
            if found.uuid == 'x':
                self.fail('Pool not found in user_services list')

            self.assertEqual(user_service['is_meta'], False)
            self.assertEqual(user_service['name'], found.name)
            self.assertEqual(user_service['visual_name'], found.visual_name)
            self.assertEqual(user_service['description'], found.comments)
            self.assertEqual(user_service['group'], models.ServicePoolGroup.default().as_dict)
            self.assertEqual(
                [(i['id'], i['name']) for i in user_service['transports']],
                [(t.uuid, t.name) for t in found.transports.all()],
            )
            self.assertEqual(user_service['imageId'], found.image and found.image.uuid or 'x')
            self.assertEqual(user_service['show_transports'], found.show_transports)
            self.assertEqual(user_service['allow_users_remove'], found.allow_users_remove)
            self.assertEqual(user_service['allow_users_reset'], found.allow_users_reset)
            self.assertEqual(user_service['maintenance'], found.service.provider.maintenance_mode)
            self.assertEqual(user_service['not_accesible'], not found.is_access_allowed(now))
            self.assertEqual(user_service['in_use'], found.userServices.filter(in_use=True).count())
            self.assertEqual(user_service['to_be_replaced'], None)
            self.assertEqual(user_service['to_be_replaced_text'], '')
            self.assertEqual(user_service['custom_calendar_text'], '')

    def test_get_meta_services_data(self) -> None:
        # Create 10 services, for this user
        service_pools: list[models.ServicePool] = []
        for i in range(100):
            service_pools.append(
                fixtures_services.create_db_assigned_userservices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        # Create 10 meta services, for this user
        meta_services: list[models.MetaPool] = []
        for i in range(10):
            meta_services.append(
                fixtures_services.create_db_metapool(
                    service_pools=service_pools[i * 10 : (i + 1) * 10], groups=self.groups
                )
            )

        data = services.get_services_info_dict(self.request)
        now = datetime.datetime.now()

        result_services: typing.Final[list[dict[str, typing.Any]]] = data['services']
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
            self.assertEqual(user_service['group'], models.ServicePoolGroup.default().as_dict)
            self.assertEqual(user_service['not_accesible'], not found.is_access_allowed(now))
            self.assertEqual(user_service['to_be_replaced'], None)
            self.assertEqual(user_service['to_be_replaced_text'], '')
            self.assertEqual(user_service['custom_calendar_text'], '')

    def test_get_meta_and_not_services_data(self) -> None:
        # Create 10 services, for this user
        user_services: list[models.ServicePool] = []
        for i in range(110):
            user_services.append(
                fixtures_services.create_db_assigned_userservices(
                    count=1, user=self.user, groups=self.groups
                )[0].deployed_service
            )

        # Create 10 meta services, for this user, last 10 user_services will not be added to meta pools
        meta_services: list[models.MetaPool] = []
        for i in range(10):
            meta_services.append(
                fixtures_services.create_db_metapool(
                    service_pools=user_services[i * 10 : (i + 1) * 10], groups=self.groups
                )
            )

        data = services.get_services_info_dict(self.request)

        result_services: typing.Final[list[dict[str, typing.Any]]] = data['services']
        self.assertEqual(len(result_services), 20)  # 10 metas and 10 normal pools
        # Some checks are ommited, because are already tested in other tests

        self.assertEqual(len(list(filter(lambda x: bool(x['is_meta']), result_services))), 10)
        self.assertEqual(len(list(filter(lambda x: not x['is_meta'], result_services))), 10)

    def _generate_metapool_with_transports(
        self, count: int, transport_grouping: types.pools.TransportSelectionPolicy, *,
        add_random_transports: bool
    ) -> tuple[list[models.ServicePool], models.MetaPool]:
        service_pools: list[models.ServicePool] = []
        for _i in range(count):
            pool = fixtures_services.create_db_assigned_userservices(
                count=1, user=self.user, groups=self.groups
            )[0].deployed_service

            pool.transports.add(*self.transports[:3])  # Add the first 3 transports to all pools
            # add some random transports to each pool after the three common ones
            if add_random_transports:
                pool.transports.add(*random.sample(self.transports[3:], 3))
            service_pools.append(pool)

        return service_pools, fixtures_services.create_db_metapool(
            service_pools=service_pools,
            groups=self.groups,
            transport_grouping=transport_grouping,
        )

    def test_meta_common_grouping(self) -> None:
        # For this test, we don't mind returned value, we just want to create the pools on db
        self._generate_metapool_with_transports(
            10, types.pools.TransportSelectionPolicy.COMMON,  # Group by common transports
            add_random_transports=True
            
        )

        # Now, get the data
        data = services.get_services_info_dict(self.request)

        # Now, check that the meta pool has the same transports as the common ones
        result_services: typing.Final[list[dict[str, typing.Any]]] = data['services']
        # We except 1 result only, a meta pool (is_meta = True)
        self.assertEqual(len(result_services), 1)
        self.assertEqual(result_services[0]['is_meta'], True)
        # Transpors for this meta pool should be the common ones, ordered by priority
        # First compose a list of the common transports, ordered by priority
        common_transports_ids = [t.uuid for t in sorted(self.transports[:3], key=lambda x: x.priority)]
        # Now, check that the transports are the same, and ordered by priority
        self.assertEqual([t['id'] for t in result_services[0]['transports']], common_transports_ids)

    def test_meta_auto_grouping(self) -> None:
        self._generate_metapool_with_transports(
            10, types.pools.TransportSelectionPolicy.AUTO,  # Group by common transports
            add_random_transports=True
        )
        
        # Now, get the data
        data = services.get_services_info_dict(self.request)
        result_services: typing.Final[list[dict[str, typing.Any]]] = data['services']
        # We except 1 result only, a meta pool (is_meta = True)
        self.assertEqual(len(result_services), 1)
        self.assertEqual(result_services[0]['is_meta'], True)
        # Transport should be {'id': 'meta', 'name: 'meta', 'priority': 0, 'link': (an udsa://... link}, and only one
        self.assertEqual(len(result_services[0]['transports']), 1)
        transport = result_services[0]['transports'][0]
        self.assertEqual(transport['id'], 'meta')
        self.assertEqual(transport['name'], 'meta')
        self.assertEqual(transport['priority'], 0)
        self.assertTrue(transport['link'].startswith(consts.system.UDS_ACTION_SCHEME))
        

    def test_meta_label_grouping(self) -> None:
        pools, _meta = self._generate_metapool_with_transports(
            10, types.pools.TransportSelectionPolicy.LABEL,  # Group by common transports
            add_random_transports=False
        )
        
        # Now we hav to had 2 same labels on the transports, add some ramdon to transports, but ensuring
        # that no transport is assigned to more ALL the transports
        possible_transports = self.transports[3:]
        transport_iterator = itertools.cycle(possible_transports)
        for pool in pools:
            pool.transports.add(next(transport_iterator))
            pool.transports.add(next(transport_iterator))
            
        # Whe know for sure that the only transports valid are the first 3 ones, because the rest are not present
        # in ALL the transports

        # Now, get the data
        data = services.get_services_info_dict(self.request)
        result_services: typing.Final[list[dict[str, typing.Any]]] = data['services']
        # We except 1 result only, a meta pool (is_meta = True)
        self.assertEqual(len(result_services), 1)
        self.assertEqual(result_services[0]['is_meta'], True)
        # should have 3 transports, the first 3 ones
        self.assertEqual(len(result_services[0]['transports']), 3)
        # id should be "LABEL:[the label]" for each transport. We added trasnports label "label0", "label1" and "label2", same as priority
        self.assertEqual([t['id'] for t in result_services[0]['transports']], ['LABEL:label0', 'LABEL:label1', 'LABEL:label2'])
        # And priority should be 0, 1 and 2
        self.assertEqual([t['priority'] for t in result_services[0]['transports']], [0, 1, 2])
        
        
