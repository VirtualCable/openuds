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

from uds.core.managers.PublicationManager import PublicationManager
from uds.core.util.Config import GlobalConfig
from uds.models import DeployedServicePublication, DeployedService, getSqlDatetime
from uds.core.services.Exceptions import PublishException
from uds.core.util.State import State
from uds.core.jobs import Job
from uds.core.jobs import DelayedTask
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class PublicationInfoItemsCleaner(Job):
    frecuency = GlobalConfig.CLEANUP_CHECK.getInt() # Request run cache "info" cleaner every configured seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Publications Info Cleaner'
    now = getSqlDatetime()
    def __init__(self, environment):
        super(PublicationInfoItemsCleaner,self).__init__(environment)
        
    def run(self):
        removeFrom = getSqlDatetime() - timedelta(seconds = GlobalConfig.KEEP_INFO_TIME.getInt(True))
        DeployedServicePublication.objects.filter(state__in=State.INFO_STATES, state_date__lt=removeFrom).delete()
        
class PublicationCleaner(Job):
    frecuency = GlobalConfig.REMOVAL_CHECK.getInt() # Request run publication "removal" every configued seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Publication Cleaner'
    
    def __init__(self, environment):
        super(PublicationCleaner,self).__init__(environment)
        
    def run(self):
        removables = DeployedServicePublication.objects.filter(state=State.REMOVABLE)
        for removable in removables:
            try:
                PublicationManager.manager().unpublish(removable)
            except PublishException: # Can say that it cant be removed right now
                logger.debug('Delaying removal')
                pass
