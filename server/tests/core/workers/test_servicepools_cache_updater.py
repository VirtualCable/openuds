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


from uds.core.types.states import State
from uds.core.workers.servicepools_cache_updater import ServiceCacheUpdater
from uds.core.environment import Environment

from uds.services.Test.provider import TestProvider
from uds.services.Test.service import TestServiceCache, TestServiceNoCache

from ...utils.test import UDSTestCase
from ...fixtures import services as services_fixtures

if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)

class ServiceCacheUpdaterTest(UDSTestCase):
    servicePool: 'models.ServicePool'

    def setUp(self) -> None:
        # Default values for max
        TestProvider.concurrent_creation_limit = 1000
        TestProvider.concurrent_removal_limit = 1000
        TestServiceCache.userservices_limit = 1000
        TestServiceNoCache.userservices_limit = 1000

        ServiceCacheUpdater.setup()
        userService = services_fixtures.create_db_cache_userservices()[0]
        self.servicePool = userService.deployed_service
        userService.delete()  # empty all

    def removing_or_canceled_count(self) -> int:
        return self.servicePool.userServices.filter(
            state__in=[State.REMOVABLE, State.CANCELED]
        ).count()

    def execute_cache_updater(self, times: int) -> int:
        for _ in range(times):
            updater = ServiceCacheUpdater(Environment.testing_environment())
            updater.run()
        # Test user service will cancel automatically so it will not get in "removable" state (on remove start, it will tell it has been removed)
        return self.servicePool.userServices.count() - self.removing_or_canceled_count()

    def set_cache(
        self,
        initial: typing.Optional[int] = None,
        cache: typing.Optional[int] = None,
        cache2: typing.Optional[int] = None,
        max: typing.Optional[int] = None,
    ) -> None:
        self.servicePool.initial_srvs = (
            self.servicePool.initial_srvs if initial is None else initial
        )
        self.servicePool.cache_l1_srvs = (
            self.servicePool.cache_l1_srvs if cache is None else cache
        )
        self.servicePool.cache_l2_srvs = (
            self.servicePool.cache_l2_srvs if cache2 is None else cache2
        )
        self.servicePool.max_srvs = self.servicePool.max_srvs if max is None else max
        self.servicePool.save()

    def test_initial(self) -> None:
        self.set_cache(initial=100, cache=10, max=500)

        self.assertEqual(
            self.execute_cache_updater(self.servicePool.initial_srvs + 10),
            self.servicePool.initial_srvs,
        )

    def test_remove(self) -> None:
        self.set_cache(initial=100, cache=110, max=500)

        self.execute_cache_updater(self.servicePool.cache_l1_srvs)

        # Now again, decrease cache to original, must remove ten elements
        mustDelete = self.servicePool.cache_l1_srvs - self.servicePool.initial_srvs

        self.set_cache(cache=10)
        self.assertEqual(
            self.execute_cache_updater(mustDelete*2), self.servicePool.initial_srvs
        )

        self.assertEqual(self.removing_or_canceled_count(), mustDelete)

    def test_max(self) -> None:
        self.set_cache(initial=100, cache=10, max=50)
        self.assertEqual(
            self.execute_cache_updater(self.servicePool.initial_srvs + 10),
            self.servicePool.max_srvs,
        )

        self.set_cache(cache=200)
        self.assertEqual(
            self.execute_cache_updater(self.servicePool.initial_srvs + 10),
            self.servicePool.max_srvs,
        )

    def test_cache(self) -> None:
        self.set_cache(initial=10, cache=100, max=500)

        # Try to "overcreate" cache elements (must create 100, that is "cache" (bigger than initial))
        self.assertEqual(
            self.execute_cache_updater(self.servicePool.cache_l1_srvs + 10),
            self.servicePool.cache_l1_srvs,
        )

    def test_provider_preparing_limits(self) -> None:
        TestProvider.concurrent_creation_limit = 10
        self.set_cache(initial=100, cache=10, max=50)

        # Try to "overcreate" cache elements but provider limits it to 10
        self.assertEqual(self.execute_cache_updater(self.servicePool.cache_l1_srvs + 10), 10)

        # Delete all userServices
        self.servicePool.userServices.all().delete()

        # Now, set provider limit to 0. Minumum aceptable is 1, so 1 will be created
        TestProvider.concurrent_creation_limit = 0
        self.assertEqual(self.execute_cache_updater(self.servicePool.cache_l1_srvs + 10), 1)

    def test_provider_no_removing_limits(self) -> None:
        # Removing limits are appliend in fact when EXECUTING removal, not when marking as removable
        # Note that "cancel" also overpass this limit
        self.set_cache(initial=0, cache=50, max=50)

        # Try to "overcreate" cache elements but provider limits it to 10
        self.execute_cache_updater(self.servicePool.cache_l1_srvs)

        # Now set cache to a lower value
        self.set_cache(cache=10)

        # Execute updater, must remove as long as runs elements (we use cancle here, so it will be removed)
        # removes until 10, that is the limit due to cache
        self.assertEqual(self.execute_cache_updater(50), 10)

    def test_service_max_deployed(self) -> None:
        TestServiceCache.userservices_limit = 22

        self.set_cache(initial=100, cache=100, max=50)

        # Try to "overcreate" cache elements but provider limits it to 10
        self.assertEqual(self.execute_cache_updater(self.servicePool.cache_l1_srvs + 10), TestServiceCache.userservices_limit)

        # Delete all userServices
        self.servicePool.userServices.all().delete()

        # We again allow masUserServices to be zero (meaning that no service will be created)
        # This allows us to "honor" some external providers that, in some cases, will not have services available...
        TestServiceCache.userservices_limit = 0
        self.assertEqual(self.execute_cache_updater(self.servicePool.cache_l1_srvs + 10), 0)
