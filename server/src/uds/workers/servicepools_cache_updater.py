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
import logging
import typing
import collections.abc

from django.db import transaction
from django.db.models import Q
from uds.core.util.config import GlobalConfig
from uds.core.types.states import State
from uds.core.managers.userservice import UserServiceManager
from uds.core.exceptions.services import MaxServicesReachedError
from uds.models import ServicePool, ServicePoolPublication, UserService
from uds.core import types
from uds.core.util import log
from uds.core.jobs import Job

logger = logging.getLogger(__name__)

# The functionallyty of counters are:
#    * while we have less items than initial, we need to create cached l1 items
#    * Once initial is reached, we have to keep cached l1 items at cache_l1_srvs
#    * We stop creating cached l1 items when max is reached
#    * If we have more than initial, we can remove cached l1 items until we reach cache_l1_srvs
#    * If we have more than max, we can remove cached l1 items until we have no more than max
#    * l2 is independent of any other counter, and will be created until cache_l2_srvs is reached
#    * l2 will be removed until cache_l2_srvs is reached


class ServiceCacheUpdater(Job):
    """
    Cache updater is responsible of keeping up to date the cache for different deployed services configurations requested
    We only process items that are "cacheables", to speed up process we will use the fact that initialServices = preparedServices = maxServices = 0
    if cache is not needed.
    This is included as a scheduled task that will run every X seconds, and scheduler will keep it so it will be only executed by one backend at a time
    """

    frecuency = 19
    frecuency_cfg = (
        GlobalConfig.CACHE_CHECK_DELAY
    )  # Request run cache manager every configured seconds (defaults to 20 seconds).
    friendly_name = 'Service Cache Updater'

    @staticmethod
    def _notify_restrain(servicepool: 'ServicePool') -> None:
        remaining_restraing_time = servicepool.remaining_restraint_time()
        log.log(
            servicepool,
            types.log.LogLevel.WARNING,
            f'Service Pool is restrained due to excesive errors (will be available in {remaining_restraing_time} seconds)',
            types.log.LogSource.INTERNAL,
        )
        logger.info(
            '%s will be restrained during %s seconds. Will check this later',
            servicepool.name,
            remaining_restraing_time,
        )

    def service_pools_needing_cache_update(
        self,
    ) -> list[types.services.ServicePoolStats]:
        # State filter for cached and inAssigned objects
        # First we get all deployed services that could need cache generation
        # We start filtering out the deployed services that do not need caching at all.
        candidate_servicepools: collections.abc.Iterable[ServicePool] = (
            ServicePool.objects.filter(Q(initial_srvs__gte=0) | Q(cache_l1_srvs__gte=0))
            .filter(
                max_srvs__gt=0,
                state__in=State.PROCESABLE_STATES,
                service__provider__maintenance_mode=False,
            )
            .iterator()
        )

        # We will get the one that proportionally needs more cache
        servicepools_numbers: list[types.services.ServicePoolStats] = []
        for servicepool in candidate_servicepools:
            stats = UserServiceManager.manager().get_cache_servicepool_stats(servicepool)
            if not stats.is_null():
                servicepools_numbers.append(stats)

        # We also return calculated values so we can reuse then
        return servicepools_numbers

    def grow_l1_cache(
        self,
        servicepool_stats: types.services.ServicePoolStats,
    ) -> None:
        """
        This method tries to enlarge L1 cache.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        """
        if servicepool_stats.servicepool is None:
            return
        logger.debug('Growing L1 cache creating a new service for %s', servicepool_stats.servicepool.name)
        # First, we try to assign from L2 cache
        if servicepool_stats.l2_cache_count > 0:
            valid = None
            with transaction.atomic():
                for n in (
                    servicepool_stats.servicepool.cached_users_services()
                    .select_for_update()
                    .filter(
                        UserServiceManager.manager().get_cache_state_filter(
                            servicepool_stats.servicepool, types.services.CacheLevel.L2
                        )
                    )
                    .order_by('creation_date')
                ):
                    if n.needs_osmanager():
                        if (
                            State.from_str(n.state).is_usable() is False
                            or State.from_str(n.os_state).is_usable()
                        ):
                            valid = n
                            break
                    else:
                        valid = n
                        break

            if valid is not None:
                valid.move_to_level(types.services.CacheLevel.L1)
                return
        try:
            # This has a velid publication, or it will not be here
            UserServiceManager.manager().create_cache_for(
                typing.cast(ServicePoolPublication, servicepool_stats.servicepool.active_publication()),
                types.services.CacheLevel.L1,
            )
        except MaxServicesReachedError:
            log.log(
                servicepool_stats.servicepool,
                types.log.LogLevel.ERROR,
                'Max number of services reached for this service',
                types.log.LogSource.INTERNAL,
            )
            logger.warning(
                'Max user services reached for %s: %s. Cache not created',
                servicepool_stats.servicepool.name,
                servicepool_stats.servicepool.max_srvs,
            )
        except Exception:
            logger.exception('Exception')

    def grow_l2_cache(
        self,
        servicepool_stats: types.services.ServicePoolStats,
    ) -> None:
        """
        Tries to grow L2 cache of service.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        """
        if servicepool_stats.servicepool is None:
            return
        logger.debug("Growing L2 cache creating a new service for %s", servicepool_stats.servicepool.name)
        try:
            # This has a velid publication, or it will not be here
            UserServiceManager.manager().create_cache_for(
                typing.cast(ServicePoolPublication, servicepool_stats.servicepool.active_publication()),
                types.services.CacheLevel.L2,
            )
        except MaxServicesReachedError:
            logger.warning(
                'Max user services reached for %s: %s. Cache not created',
                servicepool_stats.servicepool.name,
                servicepool_stats.servicepool.max_srvs,
            )
            # Alerts notified through logger

    def reduce_l1_cache(
        self,
        servicepool_stats: types.services.ServicePoolStats,
    ) -> None:
        logger.debug("Reducing L1 cache erasing a service in cache for %s", servicepool_stats.servicepool)
        # We will try to destroy the newest l1_cache_count element that is USABLE if the deployer can't cancel a new service creation
        # Here, we will take into account the "remove_after" marked user services, so we don't try to remove them
        if servicepool_stats.servicepool is None:
            return

        cache_items: list[UserService] = [
            i
            for i in servicepool_stats.servicepool.cached_users_services()
            .filter(
                UserServiceManager.manager().get_cache_state_filter(
                    servicepool_stats.servicepool, types.services.CacheLevel.L1
                )
            )
            .order_by('-creation_date')
            .iterator()
            if not i.destroy_after
        ]

        if not cache_items:
            logger.debug(
                'There is more services than max configured, but could not reduce cache L1 cause its already empty'
            )
            return

        if servicepool_stats.l2_cache_count < servicepool_stats.servicepool.cache_l2_srvs:
            valid = None
            for n in cache_items:
                if n.needs_osmanager():
                    if State.from_str(n.state).is_usable() is False or State.from_str(n.os_state).is_usable():
                        valid = n
                        break
                else:
                    valid = n
                    break

            if valid is not None:
                valid.move_to_level(types.services.CacheLevel.L2)
                return

        cache = cache_items[0]
        cache.remove_or_cancel()

    def reduce_l2_cache(
        self,
        servicepool_stats: types.services.ServicePoolStats,
    ) -> None:
        if servicepool_stats.servicepool is None:
            return
        logger.debug("Reducing L2 cache erasing a service in cache for %s", servicepool_stats.servicepool.name)
        if servicepool_stats.l2_cache_count > 0:
            cache_items = (
                servicepool_stats.servicepool.cached_users_services()
                .filter(
                    UserServiceManager.manager().get_cache_state_filter(
                        servicepool_stats.servicepool, types.services.CacheLevel.L2
                    )
                )
                .order_by('creation_date')
            )
            # TODO: Look first for non finished cache items and cancel them?
            cache: UserService = cache_items[0]
            cache.remove_or_cancel()

    def run(self) -> None:
        logger.debug('Starting cache checking')
        # We need to get
        for servicepool_stat in self.service_pools_needing_cache_update():
            # We have cache to update??
            logger.debug("Updating cache for %s", servicepool_stat)

            # Treat l1 and l2 cache independently
            # first, try to reduce cache and then grow it
            if servicepool_stat.has_l1_cache_overflow():
                self.reduce_l1_cache(servicepool_stat)
            elif servicepool_stat.is_l1_cache_growth_required():  # We need more L1 items
                self.grow_l1_cache(servicepool_stat)
            # Treat l1 and l2 cache independently
            if servicepool_stat.has_l2_cache_overflow():
                self.reduce_l2_cache(servicepool_stat)
            elif servicepool_stat.is_l2_cache_growth_required():  # We need more L2 items
                self.grow_l2_cache(servicepool_stat)
