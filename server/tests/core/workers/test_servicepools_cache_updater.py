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
import collections.abc
import logging


from uds.core.util.state import State
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
        TestProvider.maxPreparingServices = 1000
        TestProvider.maxRemovingServices = 1000
        TestServiceCache.maxUserServices = 1000
        TestServiceNoCache.maxUserServices = 1000

        ServiceCacheUpdater.setup()
        userService = services_fixtures.createCacheTestingUserServices()[0]
        self.servicePool = userService.deployed_service
        userService.delete()  # empty all

    def numberOfRemovingOrCanced(self) -> int:
        return self.servicePool.userServices.filter(
            state__in=[State.REMOVABLE, State.CANCELED]
        ).count()

    def runCacheUpdater(self, times: int) -> int:
        for _ in range(times):
            updater = ServiceCacheUpdater(Environment.getTempEnv())
            updater.run()
        # Test user service will cancel automatically so it will not get in "removable" state (on remove start, it will tell it has been removed)
        return self.servicePool.userServices.count() - self.numberOfRemovingOrCanced()

    def setCache(
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
        self.setCache(initial=100, cache=10, max=500)

        self.assertEqual(
            self.runCacheUpdater(self.servicePool.initial_srvs + 10),
            self.servicePool.initial_srvs,
        )

    def test_remove(self) -> None:
        self.setCache(initial=100, cache=110, max=500)

        self.runCacheUpdater(self.servicePool.cache_l1_srvs)

        # Now again, decrease cache to original, must remove ten elements
        mustDelete = self.servicePool.cache_l1_srvs - self.servicePool.initial_srvs

        self.setCache(cache=10)
        self.assertEqual(
            self.runCacheUpdater(mustDelete), self.servicePool.initial_srvs
        )

        self.assertEqual(self.numberOfRemovingOrCanced(), mustDelete)

    def test_max(self) -> None:
        self.setCache(initial=100, cache=10, max=50)
        self.assertEqual(
            self.runCacheUpdater(self.servicePool.initial_srvs + 10),
            self.servicePool.max_srvs,
        )

        self.setCache(cache=200)
        self.assertEqual(
            self.runCacheUpdater(self.servicePool.initial_srvs + 10),
            self.servicePool.max_srvs,
        )

    def test_cache(self) -> None:
        self.setCache(initial=10, cache=100, max=500)

        # Try to "overcreate" cache elements (must create 100, that is "cache" (bigger than initial))
        self.assertEqual(
            self.runCacheUpdater(self.servicePool.cache_l1_srvs + 10),
            self.servicePool.cache_l1_srvs,
        )

    def test_provider_preparing_limits(self) -> None:
        TestProvider.maxPreparingServices = 10
        self.setCache(initial=100, cache=10, max=50)

        # Try to "overcreate" cache elements but provider limits it to 10
        self.assertEqual(self.runCacheUpdater(self.servicePool.cache_l1_srvs + 10), 10)

        # Delete all userServices
        self.servicePool.userServices.all().delete()

        # Now, set provider limit to 0. Minumum aceptable is 1, so 1 will be created
        TestProvider.maxPreparingServices = 0
        self.assertEqual(self.runCacheUpdater(self.servicePool.cache_l1_srvs + 10), 1)

    def test_provider_removing_limits(self) -> None:
        TestProvider.maxRemovingServices = 10
        self.setCache(initial=0, cache=50, max=50)

        # Try to "overcreate" cache elements but provider limits it to 10
        self.runCacheUpdater(self.servicePool.cache_l1_srvs)

        # Now set cache to a lower value
        self.setCache(cache=10)

        # Execute updater, must remove 10 elements (maxRemovingServices)
        self.assertEqual(self.runCacheUpdater(10), 40)

    def test_service_max_deployed(self) -> None:
        TestServiceCache.maxUserServices = 22

        self.setCache(initial=100, cache=100, max=50)

        # Try to "overcreate" cache elements but provider limits it to 10
        self.assertEqual(self.runCacheUpdater(self.servicePool.cache_l1_srvs + 10), TestServiceCache.maxUserServices)

        # Delete all userServices
        self.servicePool.userServices.all().delete()

        # We again allow masUserServices to be zero (meaning that no service will be created)
        # This allows us to "honor" some external providers that, in some cases, will not have services available...
        TestServiceCache.maxUserServices = 0
        self.assertEqual(self.runCacheUpdater(self.servicePool.cache_l1_srvs + 10), 0)
