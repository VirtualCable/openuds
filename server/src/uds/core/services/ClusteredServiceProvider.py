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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from BaseServiceProvider import ServiceProvider
from uds.core.util.Config import GlobalConfig
from uds.core import managers

import logging

logger = logging.getLogger(__name__)

HEIGHT_OF_CPU = 5

class ClusteredServiceProvider(ServiceProvider):
    '''
    This class represents a Clustered Service Provider, that is, a Service provider that forms a Cluster and needs
    "organization".
    
    It adds the needed methods to keep cluster "in good shape"
    '''
    typeName = 'Base Clustered Provider' 
    typeType = 'BaseClusteredServiceProvider'
    typeDescription = 'Base Clustered Service Provider'
    iconFile = 'provider.png'
    
    balanceNodes = False         # If false, clustered provider will not try to balance nodes
    allowInUseMigration = False # If True, means that we can migrate a service while it is being used  
    
    # This methods do not need to be overriden
    def clusterStats(self):
        stats = self.storage().getPickle('ClusterStats')
        if stats is None:
            stats = {}
        return stats
    
    
    # This method do not need to be overriden, but can be if it is needed (taking care ofc :-) )
    def getClusterOverloadedNodes(self):
        '''
        Checks if a migration is desired, based on nodes load
        
        This method will return:
            Array of NodeName, preferably sorted by priority, with nodes that are "Overloaded".
            This array, ofc, can be "empty"
        '''
        if self.balanceNodes is False:
            return []
        
        overloadedNodes = []
        nodesStats = self.clusterStats()
        
        maxCpuLoad = GlobalConfig.CLUSTER_MIGRATE_CPULOAD.getInt(True)
        minFreeMemPercent = GlobalConfig.CLUSTER_MIGRATE_MEMORYLOAD.getInt(True)
        
        for nodeName, nodeStats in nodesStats.iteritems():
            if nodeStats['freeMemory'] is None or nodeStats['totalMemory'] is None or nodeStats['cpuLoad'] is None:
                continue
            freeMemPercent = (nodeStats['freeMemory'] * 100) / nodeStats['totalMemory']
            if nodeStats['cpuLoad'] > maxCpuLoad or freeMemPercent < minFreeMemPercent:
                overloadedNodes.append(nodeName)
                
        # Helper to sort array
        def getNodeStatsKey(name):
            val = 0
            if nodesStats[name]['cpuLoad']>maxCpuLoad:
                val += HEIGHT_OF_CPU + nodesStats[name]['cpuLoad']
            val += 100 - (nodeStats['freeMemory'] * 100) / nodeStats['totalMemory']
            return val
        
        # Here we sort nodes so most overloaded servers are migrated first
        return sorted(overloadedNodes, key=getNodeStatsKey)
        
    
    # Same as before, this method do not need to be overriden,
    def getClusterUnderloadedNodes(self):
        '''
        Checks which nodes of the cluster are elegible for destination of machines
        This method is very similar to  getClusterOverloadedNodes, but this returns
        a list of nodes where we can migrate the services. 
        
        This method will return:
            Array of NodeName, preferably sorted by priority, with nodes that are "Underloaded"
            This array, ofc, can be "empty"
        '''
        if self.balanceNodes is False:
            return []
        
        underloadedNodes = []
        nodesStats = self.clusterStats()
        
        maxCpuLoad = GlobalConfig.CLUSTER_ELEGIBLE_CPULOAD.getInt(True)
        minFreeMemPercent = GlobalConfig.CLUSTER_ELEGIBLE_MEMORYLOAD.getInt(True)
        
        for nodeName, nodeStats in nodesStats.iteritems():
            if nodeStats['freeMemory'] is None or nodeStats['totalMemory'] is None or nodeStats['cpuLoad'] is None:
                continue
            freeMemPercent = (nodeStats['freeMemory'] * 100) / nodeStats['totalMemory']
            if nodeStats['cpuLoad'] < maxCpuLoad and freeMemPercent > minFreeMemPercent:
                underloadedNodes.append(nodeName)
                
        # Helper to sort array
        def getNodeStatsKey(name):
            ns = nodesStats[name]
            memUsePercent = (ns['freeMemory'] * 100) / ns['totalMemory']
            # Percents of cpu is weighted over memory 
            val =  (maxCpuLoad - ns['cpuLoad']) * HEIGHT_OF_CPU + (minFreeMemPercent - memUsePercent)
            return -val
        
        # Here we sort nodes so most overloaded servers are migrated first
        return sorted(underloadedNodes, key=getNodeStatsKey)
        
    def getClusterBestNodeForDeploy(self):
        
        nodesStats = self.clusterStats()
        nodes = [name for name, v in nodesStats.iteritems()]
        
        def getNodeStatsKey(name):
            ns = nodesStats[name]
            if ns['freeMemory'] is None or ns['totalMemory'] is None or ns['cpuLoad'] is None:
                return 0 # We will put last if do not knwo anything about a node
            
            memUsePercent = (ns['freeMemory'] * 100) / ns['totalMemory']
            val = (100-ns['cpuLoad']) * HEIGHT_OF_CPU + (100-memUsePercent)
            return -val
        
        return sorted(nodes, key=getNodeStatsKey)
    
    # This methods must be overriden
    def getClusterNodes(self):
        '''
        This method must be overriden.
        
        returns the nodes of this clusters as an array dictionaries, with the id of nodes and the is the node is "active".
        Active means that it is ready to process services, inactive means that services are not available 
          
        This ids must be recognized later by nodes methods of ClusteredServiceProvider
        Example:
            [ { 'id': 'node1', 'active': True }, { 'id': 'node2', 'active': False }]
        '''
        return []
        
    
    def getClusterNodeLoad(self, nodeId):
        '''
        This method must be overriden
        
        Returns the load of a node of the cluster, as a dictionary, with 3 informations used right now:
         { 'cpuLoad':, 'freeMemory'}
        If any value is not known or can't be obtained, this can be not included in resulting dictionary, or
        it's value can be None
        
        The units for elements are:
            * cpuLoad: Load of cpu of Node (use) in %. If server has more than one CPU, average can be used (Integer)
            * freeMemory: Unused memory (or usable memory) of node, expressed in Kb (Integer)
            * totalMemory: Total memory of node, expressed in Kb (Integer)
        
        '''
        return {'cpuLoad': None, 'freeMemory': None, 'totalMemory': None} # We could have used return {}, but i prefer this "sample template" 
    