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

from django.utils.translation import ugettext as _
from uds.models import DeployedService
from ..auths.AdminAuth import needs_credentials
from ..util.Exceptions import FindException
from uds.core.util.stats import counters
from uds.core.util.Cache import Cache
import cPickle
import time

import logging

logger = logging.getLogger(__name__)

cache = Cache('StatsDispatcher')

@needs_credentials
def getDeployedServiceCounters(credentials, id, counter_type, since, to, points, use_max):
    try:
        cacheKey = id + str(counter_type)+str(since)+str(to)+str(points)+str(use_max)
        val = cache.get(cacheKey)
        if val is None:
        
            if id == '-1':
                us = DeployedService()
                all = True
            else:
                us = DeployedService.objects.get(pk=id)
                all = False
            val = []
            for x in counters.getCounters(us, counter_type, since=since, to=to, limit=points, use_max=use_max, all=all):
                val.append({ 'stamp': x[0], 'value': x[1] })
            if len(val) > 2:
                cache.put(cacheKey, cPickle.dumps(val).encode('zip'), 3600)
            else:
                val = [{'stamp':since, 'value':0 }, {'stamp':to, 'value':0}]
        else:
            val = cPickle.loads(val.decode('zip'))
            
        return { 'title': counters.getCounterTitle(counter_type), 'data': val }
    except:
        logger.exception('exception')
        raise FindException(_('Service does not exists'))
    
# Registers XML RPC Methods
def registerStatsFunctions(dispatcher):
    dispatcher.register_function(getDeployedServiceCounters, 'getDeployedServiceCounters')
