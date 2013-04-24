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

from uds.models import DeployedService
from uds.core.util.State import State
from uds.core.util.stats import counters
from uds.core.managers import statsManager
from uds.core.jobs.Job import Job

import logging

logger = logging.getLogger(__name__)

            
class DeployedServiceStatsCollector(Job):
    '''
    This Job is responsible for collecting stats for every deployed service every ten minutes
    '''
    
    frecuency = 599 # Once every ten minutes, 601 is prime, 599 also is prime
    friendly_name = 'Deployed Service Stats'
    
    def __init__(self, environment):
        super(DeployedServiceStatsCollector,self).__init__(environment)
    
    def run(self):
        logger.debug('Starting Deployed service stats collector')
        
        for ds in DeployedService.objects.filter(state = State.ACTIVE):
            try:
                fltr = ds.assignedUserServices().exclude(state__in=State.INFO_STATES)
                assigned = fltr.count()
                inUse = fltr.filter(in_use=True).count()
                counters.addCounter(ds, counters.CT_ASSIGNED, assigned)
                counters.addCounter(ds, counters.CT_INUSE, inUse)
            except:
                logger.exception('Getting counters for deployed service {0}'.format(ds))
            
        
        logger.debug('Done Deployed service stats collector')
        
 
class StatsCleaner(Job):
    '''
    This Job is responsible of housekeeping of stats tables. 
    This is done by:
        * Deleting all records
        * Optimize table
    '''
    
    frecuency = 3600*24*15 # Ejecuted just once every 15 days
    friendly_name = 'Statistic housekeeping'
    
    def run(self):
        logger.debug('Starting statistics cleanup')
        try:
            statsManager().cleanupCounters()
        except:
            logger.exception('Cleaning up counters')
            
        try:
            statsManager().cleanupEvents()
        except:
            logger.exception('Cleaning up events')
            
        logger.debug('Donde statistics cleanup')
