# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.db import transaction
from django.db.models import Q
from uds.core.util.Config import GlobalConfig
from uds.core.util.State import State
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.core.services.Exceptions import MaxServicesReachedException
from uds.models import DeployedService
from uds.core import services
from uds.core.util import log
from uds.core.jobs.Job import Job
import logging

logger = logging.getLogger(__name__)


class ServiceCacheUpdater(Job):
    '''
    Cache updater is responsible of keeping up to date the cache for different deployed services configurations requested
    We only process items that are "cacheables", to speed up process we will use the fact that initialServices = preparedServices = maxServices = 0
    if cache is not needed.
    This is included as a scheduled task that will run every X seconds, and scheduler will keep it so it will be only executed by one backend at a time
    '''
    frecuency = 19
    frecuency_cfg = GlobalConfig.CACHE_CHECK_DELAY  # Request run cache manager every configured seconds (defaults to 20 seconds).

    friendly_name = 'Service Cache Updater'

    def __init__(self, environment):
        super(ServiceCacheUpdater, self).__init__(environment)

    @staticmethod
    def calcProportion(max_, actual):
        return actual * 10000 / (max_ or 1)

    @staticmethod
    def __notifyRestrain(deployedService):
        log.doLog(deployedService, log.WARN, 'Service Pool is restrained due to errors', log.INTERNAL)
        logger.info(' {0} is restrained, will check this later'.format(deployedService.name))

    def servicesPoolsNeedingCacheUpdate(self):
        # State filter for cached and inAssigned objects
        # First we get all deployed services that could need cache generation
        DeployedService.objects.update()
        # We start filtering out the deployed services that do not need caching at all.
        whichNeedsCaching = DeployedService.objects.filter(Q(initial_srvs__gte=0) | Q(cache_l1_srvs__gte=0)).filter(max_srvs__gte=0, state=State.ACTIVE,
                                                                                                                    service__provider__maintenance_mode=False)[:]

        # We will get the one that proportionally needs more cache
        servicesPools = []
        for sp in whichNeedsCaching:
            sp.userServices.update()  # Cleans cached queries
            # If this deployedService don't have a publication active and needs it, ignore it
            if sp.activePublication() is None and sp.service.getInstance().publicationType is not None:
                logger.debug('Needs publication but do not have one, cache test ignored')
                continue
            # If it has any running publication, do not generate cache anymore
            if sp.publications.filter(state=State.PREPARING).count() > 0:
                logger.debug('Stopped cache generation for deployed service with publication running: {0}'.format(sp))
                continue

            if sp.isRestrained():
                ServiceCacheUpdater.__notifyRestrain(sp)
                continue

            # Get data related to actual state of cache
            inCacheL1 = sp.cachedUserServices().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L1_CACHE)).count()
            inCacheL2 = sp.cachedUserServices().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L2_CACHE)).count()
            inAssigned = sp.assignedUserServices().filter(UserServiceManager.getStateFilter()).count()
            # if we bypasses max cache, we will reduce it in first place. This is so because this will free resources on service provider
            logger.debug("Examining {0} with {1} in cache L1 and {2} in cache L2, {3} inAssigned".format(
                         sp, inCacheL1, inCacheL2, inAssigned))
            totalL1Assigned = inCacheL1 + inAssigned
            # We have more than we want
            if totalL1Assigned > sp.max_srvs:
                logger.debug('We have more services than max configured')
                servicesPools.append((sp, inCacheL1, inCacheL2, inAssigned))
                continue
            # We have more in L1 cache than needed
            if totalL1Assigned > sp.initial_srvs and inCacheL1 > sp.cache_l1_srvs:
                logger.debug('We have more services in cache L1 than configured')
                servicesPools.append((sp, inCacheL1, inCacheL2, inAssigned))
                continue

            # If we have more in L2 cache than needed, decrease L2 cache, but int this case, we continue checking cause L2 cache removal
            # has less priority than l1 creations or removals, but higher. In this case, we will simply take last l2 oversized found and reduce it
            if inCacheL2 > sp.cache_l2_srvs:
                logger.debug('We have more services in L2 cache than configured, decreasing it')
                servicesPools.append((sp, inCacheL1, inCacheL2, inAssigned))
                continue

            # If this service don't allows more starting user services, continue
            if UserServiceManager.manager().canInitiateServiceFromDeployedService(sp) is False:
                logger.debug('This provider has the max allowed starting services running: {0}'.format(sp))
                continue

            # If wee need to grow l2 cache, annotate it
            # Whe check this before checking the total, because the l2 cache is independent of max services or l1 cache.
            # It reflects a value that must be keeped in cache for futre fast use.
            if inCacheL2 < sp.cache_l2_srvs:
                logger.debug('Needs to grow L2 cache for {}'.format(sp))
                servicesPools.append((sp, inCacheL1, inCacheL2, inAssigned))
                continue

            # We skip it if already at max
            if totalL1Assigned == sp.max_srvs:
                continue

            if totalL1Assigned < sp.initial_srvs or inCacheL1 < sp.cache_l1_srvs:
                logger.debug('Needs to grow L1 cache for {}'.format(sp))
                servicesPools.append((sp, inCacheL1, inCacheL2, inAssigned))

        # We also return calculated values so we can reuse then
        return servicesPools

    def growL1Cache(self, sp, cacheL1, cacheL2, assigned):
        '''
        This method tries to enlarge L1 cache.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        '''
        logger.debug("Growing L1 cache creating a new service for {0}".format(sp))
        # First, we try to assign from L2 cache
        if cacheL2 > 0:
            valid = None
            with transaction.atomic():
                for n in sp.cachedUserServices().select_for_update().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L2_CACHE)).order_by('creation_date'):
                    if n.needsOsManager():
                        if State.isUsable(n.state) is False or State.isUsable(n.os_state):
                            valid = n
                            break
                    else:
                        valid = n
                        break

            if valid is not None:
                valid.moveToLevel(services.UserDeployment.L1_CACHE)
                return
        try:
            UserServiceManager.manager().createCacheFor(sp.activePublication(), services.UserDeployment.L1_CACHE)
        except MaxServicesReachedException as e:
            log.doLog(sp, log.ERROR, 'Max number of services reached for this service', log.INTERNAL)
            logger.error(str(e))
        except:
            logger.exception('Exception')

    def growL2Cache(self, sp, cacheL1, cacheL2, assigned):
        '''
        Tries to grow L2 cache of service.

        If for some reason the number of deployed services (Counting all, ACTIVE
        and PREPARING, assigned, L1 and L2) is over max allowed service deployments,
        this method will not grow the L1 cache
        '''
        logger.debug("Growing L2 cache creating a new service for {0}".format(sp))
        try:
            UserServiceManager.manager().createCacheFor(sp.activePublication(), services.UserDeployment.L2_CACHE)
        except MaxServicesReachedException as e:
            logger.error(str(e))
            # TODO: When alerts are ready, notify this

    def reduceL1Cache(self, sp, cacheL1, cacheL2, assigned):
        logger.debug("Reducing L1 cache erasing a service in cache for {0}".format(sp))
        # We will try to destroy the newest cacheL1 element that is USABLE if the deployer can't cancel a new service creation
        cacheItems = sp.cachedUserServices().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L1_CACHE)).order_by('-creation_date')
        if len(cacheItems) == 0:
            logger.debug('There is more services than configured, but could not reduce cache cause its already empty')
            return

        if cacheL2 < sp.cache_l2_srvs:
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
                valid.moveToLevel(services.UserDeployment.L2_CACHE)
                return

        cache = cacheItems[0]
        cache.removeOrCancel()

    def reduceL2Cache(self, sp, cacheL1, cacheL2, assigned):
        logger.debug("Reducing L2 cache erasing a service in cache for {0}".format(sp))
        if cacheL2 > 0:
            cacheItems = sp.cachedUserServices().filter(UserServiceManager.getCacheStateFilter(services.UserDeployment.L2_CACHE)).order_by('creation_date')
            # TODO: Look first for non finished cache items and cancel them
            cache = cacheItems[0]
            cache.removeOrCancel()

    def run(self):
        logger.debug('Starting cache checking')
        # We need to get
        servicesThatNeedsUpdate = self.servicesPoolsNeedingCacheUpdate()
        logger.debug('**** Services That Needs Update: {}'.format(servicesThatNeedsUpdate))
        for sp, cacheL1, cacheL2, assigned in servicesThatNeedsUpdate:
            # We have cache to update??
            logger.debug("Updating cache for {0}".format(sp))
            totalL1Assigned = cacheL1 + assigned

            # We try first to reduce cache before tring to increase it.
            # This means that if there is excesive number of user deployments
            # for L1 or L2 cache, this will be reduced untill they have good numbers.
            # This is so because service can have limited the number of services and,
            # if we try to increase cache before having reduced whatever needed
            # first, the service will get lock until someone removes something.
            if totalL1Assigned > sp.max_srvs:
                self.reduceL1Cache(sp, cacheL1, cacheL2, assigned)
            elif totalL1Assigned > sp.initial_srvs and cacheL1 > sp.cache_l1_srvs:
                self.reduceL1Cache(sp, cacheL1, cacheL2, assigned)
            elif cacheL2 > sp.cache_l2_srvs:  # We have excesives L2 items
                self.reduceL2Cache(sp, cacheL1, cacheL2, assigned)
            elif totalL1Assigned < sp.max_srvs and (totalL1Assigned < sp.initial_srvs or cacheL1 < sp.cache_l1_srvs):  # We need more services
                self.growL1Cache(sp, cacheL1, cacheL2, assigned)
            elif cacheL2 < sp.cache_l2_srvs:  # We need more L2 items
                self.growL2Cache(sp, cacheL1, cacheL2, assigned)
            else:
                logger.info("We have more services than max requested for {0}, but can't erase any of then cause all of them are already assigned".format(sp))
