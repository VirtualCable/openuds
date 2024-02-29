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
import dataclasses
import logging
import typing
import collections.abc

from django.db import transaction
from django.db.models import Q
from uds.core.util.config import GlobalConfig
from uds.core.types.states import State
from uds.core.managers.userservice import UserServiceManager
from uds.core.services.exceptions import MaxServicesReachedError
from uds.models import ServicePool, ServicePoolPublication, UserService
from uds.core import services
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


@dataclasses.dataclass(slots=True)
class ServicePoolStats:
    servicepool: ServicePool
    l1_cache_count: int
    l2_cache_count: int
    assigned_count: int

    def l1_cache_overflow(self) -> bool:
        """Checks if L1 cache is overflown

        Overflows if:
            * l1_assigned_count > max_srvs
            (this is, if we have more than max, we can remove cached l1 items until we reach max)
            * l1_assigned_count > initial_srvs and l1_cache_count > cache_l1_srvs
            (this is, if we have more than initial, we can remove cached l1 items until we reach cache_l1_srvs)
        """
        l1_assigned_count = self.l1_cache_count + self.assigned_count
        return l1_assigned_count > self.servicepool.max_srvs or (
            l1_assigned_count > self.servicepool.initial_srvs
            and self.l1_cache_count > self.servicepool.cache_l1_srvs
        )

    def l1_cache_needed(self) -> bool:
        """Checks if L1 cache is needed

        Grow L1 cache if:
            * l1_assigned_count < max_srvs and (l1_assigned_count < initial_srvs or l1_cache_count < cache_l1_srvs)
            (this is, if we have not reached max, and we have not reached initial or cache_l1_srvs, we need to grow L1 cache)

        """
        l1_assigned_count = self.l1_cache_count + self.assigned_count
        return l1_assigned_count < self.servicepool.max_srvs and (
            l1_assigned_count < self.servicepool.initial_srvs
            or self.l1_cache_count < self.servicepool.cache_l1_srvs
        )

    def l2_cache_overflow(self) -> bool:
        """Checks if L2 cache is overflown"""
        return self.l2_cache_count > self.servicepool.cache_l2_srvs

    def l2_cache_needed(self) -> bool:
        """Checks if L2 cache is needed"""
        return self.l2_cache_count < self.servicepool.cache_l2_srvs


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
        log.log(
            servicepool,
            log.LogLevel.WARNING,
            'Service Pool is restrained due to excesive errors',
            log.LogSource.INTERNAL,
        )
        logger.info('%s is restrained, will check this later', servicepool.name)

    def service_pools_needing_cache_update(
        self,
    ) -> list[ServicePoolStats]:
        # State filter for cached and inAssigned objects
        # First we get all deployed services that could need cache generation
        # We start filtering out the deployed services that do not need caching at all.
        candidate_servicepools: collections.abc.Iterable[ServicePool] = (
            ServicePool.objects.filter(Q(initial_srvs__gte=0) | Q(cache_l1_srvs__gte=0))
            .filter(
                max_srvs__gt=0,
                state=State.ACTIVE,
                service__provider__maintenance_mode=False,
            )
            .iterator()
        )

        # We will get the one that proportionally needs more cache
        servicepools_numbers: list[ServicePoolStats] = []
        for servicepool in candidate_servicepools:
            servicepool.user_services.update()  # Cleans cached queries
            # If this deployedService don't have a publication active and needs it, ignore it
            service_instance = servicepool.service.get_instance()

            if service_instance.uses_cache is False:
                logger.debug(
                    'Skipping cache generation for service pool that does not uses cache: %s',
                    servicepool.name,
                )
                continue

            if servicepool.active_publication() is None and service_instance.publication_type is not None:
                logger.debug(
                    'Skipping. %s Needs publication but do not have one',
                    servicepool.name,
                )
                continue
            # If it has any running publication, do not generate cache anymore
            if servicepool.publications.filter(state=State.PREPARING).count() > 0:
                logger.debug(
                    'Skipping cache generation for service pool with publication running: %s',
                    servicepool.name,
                )
                continue

            if servicepool.is_restrained():
                logger.debug(
                    'StopSkippingped cache generation for restrained service pool: %s',
                    servicepool.name,
                )
                ServiceCacheUpdater._notify_restrain(servicepool)
                continue

            # Get data related to actual state of cache
            # Before we were removing the elements marked to be destroyed after creation, but this makes us
            # to create new items over the limit stablisshed, so we will not remove them anymore
            l1_cache_count: int = (
                servicepool.cached_users_services()
                .filter(UserServiceManager().get_cache_state_filter(servicepool, services.UserService.L1_CACHE))
                .count()
            )
            l2_cache_count: int = (
                (
                    servicepool.cached_users_services()
                    .filter(
                        UserServiceManager().get_cache_state_filter(servicepool, services.UserService.L2_CACHE)
                    )
                    .count()
                )
                if service_instance.uses_cache_l2
                else 0
            )
            assigned_count: int = (
                servicepool.assigned_user_services()
                .filter(UserServiceManager().get_state_filter(servicepool.service))
                .count()
            )
            pool_stat = ServicePoolStats(servicepool, l1_cache_count, l2_cache_count, assigned_count)
            # if we bypasses max cache, we will reduce it in first place. This is so because this will free resources on service provider
            logger.debug(
                "Examining %s with %s in cache L1 and %s in cache L2, %s inAssigned",
                servicepool.name,
                l1_cache_count,
                l2_cache_count,
                assigned_count,
            )

            # We have more than we want
            if pool_stat.l1_cache_overflow():
                logger.debug('We have more services than max configured. Reducing..')
                servicepools_numbers.append(
                    ServicePoolStats(servicepool, l1_cache_count, l2_cache_count, assigned_count)
                )
                continue

            # If we have more in L2 cache than needed, decrease L2 cache, but int this case, we continue checking cause L2 cache removal
            # has less priority than l1 creations or removals, but higher. In this case, we will simply take last l2 oversized found and reduce it
            if pool_stat.l2_cache_overflow():
                logger.debug('We have more services in L2 cache than configured, reducing')
                servicepools_numbers.append(
                    ServicePoolStats(servicepool, l1_cache_count, l2_cache_count, assigned_count)
                )
                continue
            
            # If this service don't allows more starting user services, continue
            if not UserServiceManager().can_grow_service_pool(servicepool):
                logger.debug(
                    'This pool cannot grow rithg now: %s',
                    servicepool,
                )
                continue
            
            if pool_stat.l1_cache_needed():
                logger.debug('Needs to grow L1 cache for %s', servicepool)
                servicepools_numbers.append(
                    ServicePoolStats(servicepool, l1_cache_count, l2_cache_count, assigned_count)
                )
                continue
            
            if pool_stat.l2_cache_needed():
                logger.debug('Needs to grow L2 cache for %s', servicepool)
                servicepools_numbers.append(
                    ServicePoolStats(servicepool, l1_cache_count, l2_cache_count, assigned_count)
                )
                continue

        # We also return calculated values so we can reuse then
        return servicepools_numbers

    def grow_l1_cache(
        self,
        servicepool_stats: ServicePoolStats,
    ) -> None:
        """
        This method tries to enlarge L1 cache.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        """
        logger.debug('Growing L1 cache creating a new service for %s', servicepool_stats.servicepool.name)
        # First, we try to assign from L2 cache
        if servicepool_stats.l2_cache_count > 0:
            valid = None
            with transaction.atomic():
                for n in (
                    servicepool_stats.servicepool.cached_users_services()
                    .select_for_update()
                    .filter(
                        UserServiceManager().get_cache_state_filter(
                            servicepool_stats.servicepool, services.UserService.L2_CACHE
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
                valid.move_to_level(services.UserService.L1_CACHE)
                return
        try:
            # This has a velid publication, or it will not be here
            UserServiceManager().create_cache_for(
                typing.cast(ServicePoolPublication, servicepool_stats.servicepool.active_publication()),
                services.UserService.L1_CACHE,
            )
        except MaxServicesReachedError:
            log.log(
                servicepool_stats.servicepool,
                log.LogLevel.ERROR,
                'Max number of services reached for this service',
                log.LogSource.INTERNAL,
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
        servicepool_stats: ServicePoolStats,
    ) -> None:
        """
        Tries to grow L2 cache of service.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        """
        logger.debug("Growing L2 cache creating a new service for %s", servicepool_stats.servicepool.name)
        try:
            # This has a velid publication, or it will not be here
            UserServiceManager().create_cache_for(
                typing.cast(ServicePoolPublication, servicepool_stats.servicepool.active_publication()),
                services.UserService.L2_CACHE,
            )
        except MaxServicesReachedError:
            logger.warning(
                'Max user services reached for %s: %s. Cache not created',
                servicepool_stats.servicepool.name,
                servicepool_stats.servicepool.max_srvs,
            )
            # TODO: When alerts are ready, notify this

    def reduce_l1_cache(
        self,
        servicepool_stats: ServicePoolStats,
    ) -> None:
        logger.debug("Reducing L1 cache erasing a service in cache for %s", servicepool_stats.servicepool)
        # We will try to destroy the newest l1_cache_count element that is USABLE if the deployer can't cancel a new service creation
        # Here, we will take into account the "remove_after" marked user services, so we don't try to remove them
        cacheItems: list[UserService] = [
            i
            for i in servicepool_stats.servicepool.cached_users_services()
            .filter(
                UserServiceManager().get_cache_state_filter(
                    servicepool_stats.servicepool, services.UserService.L1_CACHE
                )
            )
            .order_by('-creation_date')
            .iterator()
            if not i.destroy_after
        ]

        if not cacheItems:
            logger.debug(
                'There is more services than max configured, but could not reduce cache L1 cause its already empty'
            )
            return

        if servicepool_stats.l2_cache_count < servicepool_stats.servicepool.cache_l2_srvs:
            valid = None
            for n in cacheItems:
                if n.needs_osmanager():
                    if State.from_str(n.state).is_usable() is False or State.from_str(n.os_state).is_usable():
                        valid = n
                        break
                else:
                    valid = n
                    break

            if valid is not None:
                valid.move_to_level(services.UserService.L2_CACHE)
                return

        cache = cacheItems[0]
        cache.remove_or_cancel()

    def reduce_l2_cache(
        self,
        servicepool_stats: ServicePoolStats,
    ) -> None:
        logger.debug("Reducing L2 cache erasing a service in cache for %s", servicepool_stats.servicepool.name)
        if servicepool_stats.l2_cache_count > 0:
            cacheItems = (
                servicepool_stats.servicepool.cached_users_services()
                .filter(
                    UserServiceManager().get_cache_state_filter(
                        servicepool_stats.servicepool, services.UserService.L2_CACHE
                    )
                )
                .order_by('creation_date')
            )
            # TODO: Look first for non finished cache items and cancel them?
            cache: UserService = cacheItems[0]
            cache.remove_or_cancel()

    def run(self) -> None:
        logger.debug('Starting cache checking')
        # We need to get
        for servicepool_stat in self.service_pools_needing_cache_update():
            # We have cache to update??
            logger.debug("Updating cache for %s", servicepool_stat)

            # Treat l1 and l2 cache independently
            # first, try to reduce cache and then grow it
            if servicepool_stat.l1_cache_overflow():
                self.reduce_l1_cache(servicepool_stat)
            elif servicepool_stat.l1_cache_needed():  # We need more L1 items
                self.grow_l1_cache(servicepool_stat)
            # Treat l1 and l2 cache independently
            if servicepool_stat.l2_cache_overflow():
                self.reduce_l2_cache(servicepool_stat)
            elif servicepool_stat.l2_cache_needed():  # We need more L2 items
                self.grow_l2_cache(servicepool_stat)
