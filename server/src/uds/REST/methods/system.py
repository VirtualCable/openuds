# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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

from uds.models import User, Service, UserService, DeployedService, getSqlDatetime

from uds.core.util.stats import counters
from uds.core.util.Cache import Cache
from uds.REST import Handler, RequestError, ResponseError
import cPickle
import time
from datetime import timedelta

import logging

logger = logging.getLogger(__name__)

cache = Cache('StatsDispatcher')

# Enclosed methods under /syatem path
POINTS = 365
SINCE = 365  # Days
USE_MAX = True


def getServicesPoolsCounters(servicePool, counter_type):
    try:
        cacheKey = (servicePool and servicePool.id or 'all') + str(counter_type) + str(POINTS) + str(SINCE)
        to = getSqlDatetime()
        since = to - timedelta(days=SINCE)
        val = cache.get(cacheKey)
        if val is None:
            if servicePool is None:
                us = DeployedService()
                complete = True  # Get all deployed services stats
            else:
                us = servicePool
                complete = False
            val = []
            for x in counters.getCounters(us, counter_type, since=since, to=to, limit=POINTS, use_max=USE_MAX, all=complete):
                val.append({'stamp': x[0], 'value': int(x[1])})
            if len(val) > 2:
                cache.put(cacheKey, cPickle.dumps(val).encode('zip'), 600)
            else:
                val = [{'stamp':since, 'value': 0}, {'stamp':to, 'value':0}]
        else:
            val = cPickle.loads(val.decode('zip'))

        return val
    except:
        logger.exception('exception')
        raise ResponseError('can\'t create stats for objects!!!')


class System(Handler):
    def get(self):
        logger.debug('args: {0}'.format(self._args))
        if len(self._args) == 1:
            if self._args[0] == 'overview':  # System overview
                users = User.objects.count()
                services = Service.objects.count()
                user_services = UserService.objects.count()
                restrained_services_pools = len(DeployedService.getRestraineds())
                return {
                    'users': users,
                    'services': services,
                    'user_services': user_services,
                    'restrained_services_pools': restrained_services_pools,
                }

        if len(self._args) == 2:
            if self._args[0] == 'stats':
                if self._args[1] == 'assigned':
                    return getServicesPoolsCounters(None, counters.CT_ASSIGNED)
                if self._args[1] == 'inuse':
                    return getServicesPoolsCounters(None, counters.CT_INUSE)

        raise RequestError('invalid request')

    def put(self):
        raise RequestError('todo')
