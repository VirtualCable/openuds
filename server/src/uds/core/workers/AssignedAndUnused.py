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

from uds.core.util.Config import GlobalConfig
from uds.models import DeployedService, getSqlDatetime
from uds.core.util.State import State
from uds.core.jobs.Job import Job
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class AssignedAndUnused(object): # When derived from Job, it will be auto-registered
    frecuency = GlobalConfig.CHECK_UNUSED_TIME.getInt()
    friendly_name = 'Unused services checker'
    
    def __init__(self, environment):
        super(AssignedAndUnused,self).__init__(environment)
    
    def run(self):
        for ds in DeployedService.objects.all():
            osm = ds.osmanager.getInstance()
            if osm.processUnusedMachines is True:
                logger.debug('Processing unused services for {0}'.format(osm))
                since_state = getSqlDatetime() - timedelta( seconds = GlobalConfig.CHECK_UNUSED_TIME.getInt() / 2 )
                for us in ds.assignedUserServices().select_for_update().filter(in_use=False,since_state__lt=since_state):
                    logger.debug('Found unused assigned service {0}'.format(us))
                    osm.processUnused(us)