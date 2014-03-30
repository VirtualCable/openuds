# -*- coding: utf-8 -*-

#
# Copyright (c) 2013 Virtual Cable S.L.
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

from uds.core.jobs.Job import Job
from uds.core.jobs import DelayedTask
from uds.core.util.State import State
from uds.core.util import log
from django.db import transaction
from uds.models import Provider
from uds.models import UserService
import logging

logger = logging.getLogger(__name__)

GETCLUSTERSTATS_TAG = 'ClstrStats'
BALANCECLUSTER_TAG = 'ClstrBalance'
MIGRATETASK_TAG = 'ClstrMigrate'


# Utility to get all providers that are derived from
def getClusteredProvidersFromDB():
    # services.ClusteredServiceProvider.
    from uds.core import services

    p = services.ClusteredServiceProvider

    for prov in Provider.objects.all():
        for cls in p.__subclasses__():
            if prov.isOfType(cls.typeType):
                yield prov


class ClusterUpdateStatsTask(DelayedTask):
    def __init__(self, providerId):
        super(ClusterUpdateStatsTask, self).__init__()
        self._id = providerId

    def run(self):
        try:
            provider = Provider.objects.get(pk=self._id)
            logger.debug('Updating stats for {0}'.format(provider.name))
            cluster = provider.getInstance()
            nodes = cluster.getClusterNodes()
            stats = {}
            for node in nodes:
                s = cluster.getClusterNodeLoad(node['id'])
                stats[node['id']] = {
                    'cpuLoad': s.get('cpuLoad', None),
                    'freeMemory': s.get('freeMemory', None),
                    'totalMemory': s.get('totalMemory')
                }
            cluster.storage().putPickle('ClusterStats', stats)
        except:
            logger.exception('Update Stats Task')
            # Removed provider, no problem at all, no update is done
            pass


# Job for managing ClusteredServiceProvider
class ClusterUpdateStats(Job):
    frecuency = 60  # Once every 60 seconds
    friendly_name = 'Clustered Providers Statistics Updater'

    def __init__(self, environment):
        super(ClusterUpdateStats, self).__init__(environment)

    def run(self):
        logger.debug('Clustered Service manager started')
        for p in getClusteredProvidersFromDB():
            logger.debug('Getting stats for clustered provider {0}'.format(p.name))
            ct = ClusterUpdateStatsTask(p.id)
            ct.register(0, '{0}_{1}'.format(GETCLUSTERSTATS_TAG, p.id), True)


# Balancing nodes related
class ClusterMigrationTask(DelayedTask):
    def __init__(self, service):
        super(ClusterMigrationTask, self).__init__()
        self._serviceId = service.id
        self._state = service.state

    @staticmethod
    def checkAndUpdateState(userService, userServiceInstance, state):
        '''
        Checks the value returned from invocation to publish or checkPublishingState, updating the dsp database object
        Return True if it has to continue checking, False if finished
        '''
        try:
            if State.isFinished(state):
                checkLater = False
                userServiceInstance.finish()
                userService.updateData(userServiceInstance)
                userService.setState(State.USABLE)  # Wi will only migrate fully functional services
            elif State.isErrored(state):
                checkLater = False
                userService.updateData(userServiceInstance)
                userService.setState(State.ERROR)
            else:
                checkLater = True  # The task is running
                userService.updateData(userServiceInstance)
            userService.save()
            if checkLater:
                ClusterMigrationTask.checkLater(userService, userServiceInstance)
        except Exception as e:
            logger.exception('Migrating service')
            log.doLog(userService, log.ERROR, 'Exception: {0}'.format(e), log.INTERNAL)
            userService.setState(State.ERROR)
            userService.save()

    @staticmethod
    def checkLater(userService, userServiceInstance):
        '''
        Inserts a task in the delayedTaskRunner so we can check the state of this migration
        @param userService: Database object for DeployedServicePublication
        @param userServiceInstance: Instance of Publication manager for the object
        '''
        from uds.core.jobs.DelayedTaskRunner import DelayedTaskRunner
        # Do not add task if already exists one that updates this service
        if DelayedTaskRunner.runner().checkExists(MIGRATETASK_TAG + str(userService.id)):
            return
        DelayedTaskRunner.runner().insert(ClusterUpdateStats(userService), userServiceInstance.suggestedTime, ClusterUpdateStats + str(userService.id))

    def run(self):
        logger.debug('Checking user service finished migrating {0}'.format(self._serviceId))
        uService = None
        try:
            uService = UserService.objects.get(pk=self._serviceId)
            if uService.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
                # This item is no longer valid, returning will not check it again (no checkLater called)
                return

            ci = uService.getInstance()
            logger.debug("uService instance class: {0}".format(ci.__class__))
            state = ci.checkState()
            ClusterMigrationTask.checkAndUpdateState(uService, ci, state)
        except UserService.DoesNotExist, e:
            logger.error('User service not found (erased from database?) {0} : {1}'.format(e.__class__, e))
        except Exception, e:
            # Exception caught, mark service as errored
            logger.exception("Error {0}, {1} :".format(e.__class__, e))
            if uService is not None:
                log.doLog(uService, log.ERROR, 'Exception: {0}'.format(e), log.INTERNAL)
            try:
                uService.setState(State.ERROR)
                uService.save()
            except Exception:
                logger.error('Can\'t update state of uService object')


class ClusterBalancingTask(DelayedTask):
    def __init__(self, providerId):
        super(ClusterBalancingTask, self).__init__()
        self._id = providerId

    @staticmethod
    def migrate(serviceId, toNode):
        try:
            with transaction.atomic():
                service = UserService.objects.select_for_update().get(pk=serviceId)
                service.setState(State.BALANCING)
                service.save()

            serviceInstance = service.getInstance()

            # Now we will start a new task, similar to those of deploying
            state = serviceInstance.startMigration(toNode)

            ClusterMigrationTask.checkAndUpdateState(service, serviceInstance, state)
        except Exception as e:
            logger.exception('Initializing migration')
            if service is not None:
                log.doLog(service, log.ERROR, 'At migration init: {0}'.format(e), log.INTERNAL)
            try:
                service.setState(State.ERROR)
                service.save()
            except:
                logger.exception('Setting error state at migration init')

    def run(self):
        try:
            provider = Provider.objects.get(pk=self._id)
            logger.debug('Balancing cluster {0}'.format(provider.name))
            cluster = provider.getInstance()
            serviceForBalancing = None
            for c in cluster.getClusterOverloadedNodes():
                for s in cluster.getServicesForBalancing(c):
                    si = s.getInstance()
                    if si.ensureExistsOnNode(c) is True:
                        serviceForBalancing = s.id
                        break
                    else:
                        # Update node information for service on DB
                        node = cluster.locateClusterService(si)
                        if node is not None:
                            s.cluster_node = node
                            s.save()

            if serviceForBalancing is None:
                return

            nodesForDestination = cluster.getClusterUnderloadedNodes()
            if len(nodesForDestination) == 0:
                logger.debug('Cluster is overloaded, but no underloaded nodes for receiving migration')

            underloadedNode = nodesForDestination[0]

            ClusterBalancingTask.migrate(serviceForBalancing, underloadedNode)
        except:
            logger.exception('Cluster Balancing Task')


class ClusterBalancingJob(Job):
    frecuency = 90
    friendly_name = 'Clustered Providers Balancing job'

    def __init__(self, environment):
        super(ClusterBalancingJob, self).__init__(environment)

    def run(self):
        '''
        Checks which clusters support "balancing" and created a parallel thread for each
        '''
        logger.debug('Started balancing clusters task')
        for p in getClusteredProvidersFromDB():
            logger.debug('Checking balancing on {0}'.format(p.name))
            cb = ClusterBalancingTask(p.id)
            cb.register(0, '{0}_{1}'.format(BALANCECLUSTER_TAG, p.id), True)
