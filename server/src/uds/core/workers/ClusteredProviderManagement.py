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
from uds.models import Provider
import logging

logger = logging.getLogger(__name__)

GETCLUSTERSTATS_TAG = 'ClstrStats'

# Utility to get all providers that are derived from 
def getClusteredProvidersFromDB():
    #services.ClusteredServiceProvider.
    from uds.core import services
    
    p = services.ClusteredServiceProvider
    
    for prov in Provider.objects.all():
        for cls in p.__subclasses__():
            if prov.isOfType(cls.typeType):
                yield prov
                
class ClusterUpdateStatsTask(DelayedTask):
    def __init__(self, providerId):
        super(ClusterUpdateStatsTask,self).__init__()
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
                stats[node['id']] = { 'cpuLoad': s.get('cpuLoad', None), 'freeMemory': s.get('freeMemory', None),
                                      'totalMemory': s.get('totalMemory') } 
            cluster.storage().putPickle('ClusterStats', stats)
        except:
            logger.exception('Exception')
            # Removed provider, no problem at all, no update is done
            pass
         
                
# Job for managing ClusteredServiceProvider
class ClusterUpdateStats(Job):
    frecuency = 60 # Once every 60 seconds
    friendly_name = 'Clustered Providers Statistics Updater'
    
    def __init__(self, environment):
        super(ClusterUpdateStats,self).__init__(environment)
    
    def run(self):
        logger.debug('Clustered Service manager started')
        for p in getClusteredProvidersFromDB():
            logger.debug('Getting stats for clustered provider {0}'.format(p.name))
            ct = ClusterUpdateStatsTask(p.id)
            ct.register(0, '{0}_{1}'.format(GETCLUSTERSTATS_TAG, p.id), True)
