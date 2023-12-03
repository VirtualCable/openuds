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
import logging
import typing
import collections.abc

from django.db import transaction
from django.db.models import Q
from uds.core.util.config import GlobalConfig
from uds.core.util.state import State
from uds.core.managers.user_service import UserServiceManager
from uds.core.services.exceptions import MaxServicesReachedError
from uds.models import ServicePool, ServicePoolPublication, UserService
from uds.core import services
from uds.core.util import log
from uds.core.jobs import Job

logger = logging.getLogger(__name__)


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
    def __notifyRestrain(servicePool) -> None:
        log.doLog(
            servicePool,
            log.LogLevel.WARNING,
            'Service Pool is restrained due to excesive errors',
            log.LogSource.INTERNAL,
        )
        logger.info('%s is restrained, will check this later', servicePool.name)

    def servicesPoolsNeedingCacheUpdate(
        self,
    ) -> list[typing.Tuple[ServicePool, int, int, int]]:
        # State filter for cached and inAssigned objects
        # First we get all deployed services that could need cache generation
        # We start filtering out the deployed services that do not need caching at all.
        servicePoolsNeedingCaching: typing.Iterable[ServicePool] = (
            ServicePool.objects.filter(Q(initial_srvs__gte=0) | Q(cache_l1_srvs__gte=0))
            .filter(
                max_srvs__gt=0,
                state=State.ACTIVE,
                service__provider__maintenance_mode=False,
            )
            .iterator()
        )

        # We will get the one that proportionally needs more cache
        servicesPools: list[typing.Tuple[ServicePool, int, int, int]] = []
        for servicePool in servicePoolsNeedingCaching:
            servicePool.userServices.update()  # Cleans cached queries
            # If this deployedService don't have a publication active and needs it, ignore it
            spServiceInstance = servicePool.service.getInstance()  # type: ignore
            
            if spServiceInstance.usesCache is False:
                logger.debug(
                    'Skipping cache generation for service pool that does not uses cache: %s',
                    servicePool.name,
                )
                continue

            if servicePool.activePublication() is None and spServiceInstance.publicationType is not None:
                logger.debug(
                    'Skipping. %s Needs publication but do not have one',
                    servicePool.name,
                )
                continue
            # If it has any running publication, do not generate cache anymore
            if servicePool.publications.filter(state=State.PREPARING).count() > 0:
                logger.debug(
                    'Skipping cache generation for service pool with publication running: %s',
                    servicePool.name,
                )
                continue

            if servicePool.isRestrained():
                logger.debug(
                    'StopSkippingped cache generation for restrained service pool: %s',
                    servicePool.name,
                )
                ServiceCacheUpdater.__notifyRestrain(servicePool)
                continue

            # Get data related to actual state of cache
            # Before we were removing the elements marked to be destroyed after creation, but this makes us
            # to create new items over the limit stablisshed, so we will not remove them anymore
            inCacheL1: int = (
                servicePool.cachedUserServices()
                .filter(UserServiceManager().getCacheStateFilter(servicePool, services.UserService.L1_CACHE))
                .count()
            )
            inCacheL2: int = (
                servicePool.cachedUserServices()
                .filter(UserServiceManager().getCacheStateFilter(servicePool, services.UserService.L2_CACHE))
                .count()
            ) if spServiceInstance.usesCache_L2 else 0
            inAssigned: int = (
                servicePool.assignedUserServices()
                .filter(UserServiceManager().getStateFilter(servicePool.service))  # type: ignore
                .count()
            )
            # if we bypasses max cache, we will reduce it in first place. This is so because this will free resources on service provider
            logger.debug(
                "Examining %s with %s in cache L1 and %s in cache L2, %s inAssigned",
                servicePool.name,
                inCacheL1,
                inCacheL2,
                inAssigned,
            )
            totalL1Assigned = inCacheL1 + inAssigned

            # We have more than we want
            if totalL1Assigned > servicePool.max_srvs:
                logger.debug('We have more services than max configured. skipping.')
                servicesPools.append((servicePool, inCacheL1, inCacheL2, inAssigned))
                continue
            # We have more in L1 cache than needed
            if totalL1Assigned > servicePool.initial_srvs and inCacheL1 > servicePool.cache_l1_srvs:
                logger.debug('We have more services in cache L1 than configured, appending')
                servicesPools.append((servicePool, inCacheL1, inCacheL2, inAssigned))
                continue

            # If we have more in L2 cache than needed, decrease L2 cache, but int this case, we continue checking cause L2 cache removal
            # has less priority than l1 creations or removals, but higher. In this case, we will simply take last l2 oversized found and reduce it
            if spServiceInstance.usesCache_L2 and inCacheL2 > servicePool.cache_l2_srvs:
                logger.debug('We have more services in L2 cache than configured, appending')
                servicesPools.append((servicePool, inCacheL1, inCacheL2, inAssigned))
                continue

            # If this service don't allows more starting user services, continue
            if not UserServiceManager().canGrowServicePool(servicePool):
                logger.debug(
                    'This pool cannot grow rithg now: %s',
                    servicePool,
                )
                continue

            # If wee need to grow l2 cache, annotate it
            # Whe check this before checking the total, because the l2 cache is independent of max services or l1 cache.
            # It reflects a value that must be keeped in cache for futre fast use.
            if inCacheL2 < servicePool.cache_l2_srvs:
                logger.debug('Needs to grow L2 cache for %s', servicePool)
                servicesPools.append((servicePool, inCacheL1, inCacheL2, inAssigned))
                continue

            # We skip it if already at max
            if totalL1Assigned == servicePool.max_srvs:
                continue

            if totalL1Assigned < servicePool.initial_srvs or inCacheL1 < servicePool.cache_l1_srvs:
                logger.debug('Needs to grow L1 cache for %s', servicePool)
                servicesPools.append((servicePool, inCacheL1, inCacheL2, inAssigned))

        # We also return calculated values so we can reuse then
        return servicesPools

    def growL1Cache(
        self,
        servicePool: ServicePool,
        cacheL1: int,  # pylint: disable=unused-argument
        cacheL2: int,
        assigned: int,  # pylint: disable=unused-argument
    ) -> None:
        """
        This method tries to enlarge L1 cache.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        """
        logger.debug('Growing L1 cache creating a new service for %s', servicePool.name)
        # First, we try to assign from L2 cache
        if cacheL2 > 0:
            valid = None
            with transaction.atomic():
                for n in (
                    servicePool.cachedUserServices()
                    .select_for_update()
                    .filter(
                        UserServiceManager().getCacheStateFilter(servicePool, services.UserService.L2_CACHE)
                    )
                    .order_by('creation_date')
                ):
                    if n.needsOsManager():
                        if State.isUsable(n.state) is False or State.isUsable(n.os_state):
                            valid = n
                            break
                    else:
                        valid = n
                        break

            if valid is not None:
                valid.moveToLevel(services.UserService.L1_CACHE)
                return
        try:
            # This has a velid publication, or it will not be here
            UserServiceManager().createCacheFor(
                typing.cast(ServicePoolPublication, servicePool.activePublication()),
                services.UserService.L1_CACHE,
            )
        except MaxServicesReachedError:
            log.doLog(
                servicePool,
                log.LogLevel.ERROR,
                'Max number of services reached for this service',
                log.LogSource.INTERNAL,
            )
            logger.warning(
                'Max user services reached for %s: %s. Cache not created',
                servicePool.name,
                servicePool.max_srvs,
            )
        except Exception:
            logger.exception('Exception')

    def growL2Cache(
        self,
        servicePool: ServicePool,
        cacheL1: int,  # pylint: disable=unused-argument
        cacheL2: int,  # pylint: disable=unused-argument
        assigned: int,  # pylint: disable=unused-argument
    ) -> None:
        """
        Tries to grow L2 cache of service.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        """
        logger.debug("Growing L2 cache creating a new service for %s", servicePool.name)
        try:
            # This has a velid publication, or it will not be here
            UserServiceManager().createCacheFor(
                typing.cast(ServicePoolPublication, servicePool.activePublication()),
                services.UserService.L2_CACHE,
            )
        except MaxServicesReachedError:
            logger.warning(
                'Max user services reached for %s: %s. Cache not created',
                servicePool.name,
                servicePool.max_srvs,
            )
            # TODO: When alerts are ready, notify this

    def reduceL1Cache(
        self,
        servicePool: ServicePool,
        cacheL1: int,  # pylint: disable=unused-argument
        cacheL2: int,
        assigned: int,  # pylint: disable=unused-argument
    ):
        logger.debug("Reducing L1 cache erasing a service in cache for %s", servicePool)
        # We will try to destroy the newest cacheL1 element that is USABLE if the deployer can't cancel a new service creation
        # Here, we will take into account the "remove_after" marked user services, so we don't try to remove them
        cacheItems: list[UserService] = [
            i
            for i in servicePool.cachedUserServices()
            .filter(UserServiceManager().getCacheStateFilter(servicePool, services.UserService.L1_CACHE))
            .order_by('-creation_date')
            .iterator()
            if not i.destroy_after
        ]

        if not cacheItems:
            logger.debug(
                'There is more services than max configured, but could not reduce cache L1 cause its already empty'
            )
            return

        if cacheL2 < servicePool.cache_l2_srvs:
            valid = None
            for n in cacheItems:
                if n.needsOsManager():
                    if State.isUsable(n.state) is False or State.isUsable(n.os_state):
                        valid = n
                        break
                else:
                    valid = n
                    break

            if valid is not None:
                valid.moveToLevel(services.UserService.L2_CACHE)
                return

        cache = cacheItems[0]
        cache.removeOrCancel()

    def reduceL2Cache(
        self,
        servicePool: ServicePool,
        cacheL1: int,  # pylint: disable=unused-argument
        cacheL2: int,
        assigned: int,  # pylint: disable=unused-argument
    ):
        logger.debug("Reducing L2 cache erasing a service in cache for %s", servicePool.name)
        if cacheL2 > 0:
            cacheItems = (
                servicePool.cachedUserServices()
                .filter(UserServiceManager().getCacheStateFilter(servicePool, services.UserService.L2_CACHE))
                .order_by('creation_date')
            )
            # TODO: Look first for non finished cache items and cancel them?
            cache: UserService = cacheItems[0]
            cache.removeOrCancel()

    def run(self) -> None:
        logger.debug('Starting cache checking')
        # We need to get
        servicesThatNeedsUpdate = self.servicesPoolsNeedingCacheUpdate()
        for servicePool, cacheL1, cacheL2, assigned in servicesThatNeedsUpdate:
            # We have cache to update??
            logger.debug("Updating cache for %s", servicePool)
            totalL1Assigned = cacheL1 + assigned

            # We try first to reduce cache before tring to increase it.
            # This means that if there is excesive number of user deployments
            # for L1 or L2 cache, this will be reduced untill they have good numbers.
            # This is so because service can have limited the number of services and,
            # if we try to increase cache before having reduced whatever needed
            # first, the service will get lock until someone removes something.
            if totalL1Assigned > servicePool.max_srvs:
                self.reduceL1Cache(servicePool, cacheL1, cacheL2, assigned)
            elif totalL1Assigned > servicePool.initial_srvs and cacheL1 > servicePool.cache_l1_srvs:
                self.reduceL1Cache(servicePool, cacheL1, cacheL2, assigned)
            elif cacheL2 > servicePool.cache_l2_srvs:  # We have excesives L2 items
                self.reduceL2Cache(servicePool, cacheL1, cacheL2, assigned)
            elif totalL1Assigned < servicePool.max_srvs and (
                totalL1Assigned < servicePool.initial_srvs or cacheL1 < servicePool.cache_l1_srvs
            ):  # We need more services
                self.growL1Cache(servicePool, cacheL1, cacheL2, assigned)
            elif cacheL2 < servicePool.cache_l2_srvs:  # We need more L2 items
                self.growL2Cache(servicePool, cacheL1, cacheL2, assigned)
            else:
                logger.warning("We have more services than max requested for %s", servicePool.name)
