# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import codecs
import collections.abc
import datetime
import logging
import pickle  # nosec: pickle is used to cache data, not to load it
import typing

from uds import models
from uds.core import exceptions, types
from uds.core.util import permissions
from uds.core.util.cache import Cache
from uds.core.util.model import process_uuid, sql_datetime
from uds.core.types.states import State
from uds.core.util.stats import counters
from uds.REST import Handler

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.db.models import Model

cache = Cache('StatsDispatcher')

# Enclosed methods under /stats path
POINTS = 70
SINCE = 7  # Days, if higer values used, ensure mysql/mariadb has a bigger sort buffer
USE_MAX = True
CACHE_TIME = SINCE * 24 * 3600 // POINTS


def get_servicepools_counters(
    servicePool: typing.Optional[models.ServicePool],
    counter_type: types.stats.CounterType,
    since_days: int = SINCE,
) -> list[collections.abc.Mapping[str, typing.Any]]:
    try:
        cacheKey = (
            (servicePool and str(servicePool.id) or 'all') + str(counter_type) + str(POINTS) + str(since_days)
        )
        to = sql_datetime()
        since: datetime.datetime = to - datetime.timedelta(days=since_days)

        cachedValue: typing.Optional[bytes] = cache.get(cacheKey)
        if not cachedValue:
            if not servicePool:
                us = models.ServicePool()
                us.id = -1  # Global stats
            else:
                us = servicePool
            val: list[collections.abc.Mapping[str, typing.Any]] = []
            for x in counters.enumerate_counters(
                us,
                counter_type,
                since=since,
                to=to,
                max_intervals=POINTS,
                use_max=USE_MAX,
                all=us.id == -1,
            ):
                val.append({'stamp': x[0], 'value': int(x[1])})
            logger.debug('val: %s', val)
            if len(val) >= 2:
                cache.put(cacheKey, codecs.encode(pickle.dumps(val), 'zip'), CACHE_TIME * 2)
            else:
                val = [{'stamp': since, 'value': 0}, {'stamp': to, 'value': 0}]
        else:
            val = pickle.loads(
                codecs.decode(cachedValue, 'zip')
            )  # nosec: pickle is used to cache data, not to load it

        # return [{'stamp': since + datetime.timedelta(hours=i*10), 'value': i*i*counter_type//4} for i in range(300)]

        return val
    except Exception as e:
        logger.exception('getServicesPoolsCounters')
        raise exceptions.rest.ResponseError('can\'t create stats for objects!!!') from e


class System(Handler):
    """
    {
        'paths': [
            "/system/overview", "Returns a json object with the number of services, service pools, users, etc",
            "/system/stats/assigned", "Returns a chart of assigned services (all pools)",
            "/system/stats/inuse", "Returns a chart of in use services (all pools)",
            "/system/stats/cached", "Returns a chart of cached services (all pools)",
            "/system/stats/complete",  "Returns a chart of complete services (all pools)",
            "/system/stats/assigned/<servicePoolId>", "Returns a chart of assigned services (for a pool)",
            "/system/stats/inuse/<servicePoolId>", "Returns a chart of in use services (for a pool)",
            "/system/stats/cached/<servicePoolId>", "Returns a chart of cached services (for a pool)",
            "/system/stats/complete/<servicePoolId>", "Returns a chart of complete services (for a pool)",
        ],
        'comments': [
            "Must be admin to access this",
        ]
    }
    """

    needs_admin = False
    needs_staff = True

    help_paths = [
        ('overview', ''),
        ('stats/assigned', ''),
        ('stats/inuse', ''),
        ('stats/cached', ''),
        ('stats/complete', ''),
        ('stats/assigned/<servicePoolId>', ''),
        ('stats/inuse/<servicePoolId>', ''),
        ('stats/cached/<servicePoolId>', ''),
        ('stats/complete/<servicePoolId>', ''),
    ]
    help_text = 'Provides system information. Must be admin to access this'

    def get(self) -> typing.Any:
        logger.debug('args: %s', self._args)
        # Only allow admin user for global stats
        if len(self._args) == 1:
            if self._args[0] == 'overview':  # System overview
                if not self._user.is_admin:
                    raise exceptions.rest.AccessDenied()
                users: int = models.User.objects.count()
                groups: int = models.Group.objects.count()
                services: int = models.Service.objects.count()
                service_pools: int = models.ServicePool.objects.count()
                meta_pools: int = models.MetaPool.objects.count()
                user_services: int = models.UserService.objects.exclude(
                    state__in=(State.REMOVED, State.ERROR)
                ).count()
                restrained_services_pools: int = models.ServicePool.restraineds_queryset().count()
                return {
                    'users': users,
                    'groups': groups,
                    'services': services,
                    'service_pools': service_pools,
                    'meta_pools': meta_pools,
                    'user_services': user_services,
                    'restrained_services_pools': restrained_services_pools,
                }

        if len(self._args) in (2, 3):
            # Extract pool if provided
            pool: typing.Optional[models.ServicePool] = None
            if len(self._args) == 3:
                try:
                    pool = models.ServicePool.objects.get(uuid=process_uuid(self._args[2]))
                except Exception:
                    pool = None
            # If pool is None, needs admin also
            if not pool and not self._user.is_admin:
                raise exceptions.rest.AccessDenied()
            # Check permission for pool..
            if not permissions.has_access(
                self._user, typing.cast('Model', pool), types.permissions.PermissionType.READ
            ):
                raise exceptions.rest.AccessDenied()
            if self._args[0] == 'stats':
                if self._args[1] == 'assigned':
                    return get_servicepools_counters(pool, counters.types.stats.CounterType.ASSIGNED)
                elif self._args[1] == 'inuse':
                    return get_servicepools_counters(pool, counters.types.stats.CounterType.INUSE)
                elif self._args[1] == 'cached':
                    return get_servicepools_counters(pool, counters.types.stats.CounterType.CACHED)
                elif self._args[1] == 'complete':
                    return {
                        'assigned': get_servicepools_counters(
                            pool, counters.types.stats.CounterType.ASSIGNED, since_days=7
                        ),
                        'inuse': get_servicepools_counters(
                            pool, counters.types.stats.CounterType.INUSE, since_days=7
                        ),
                        'cached': get_servicepools_counters(
                            pool, counters.types.stats.CounterType.CACHED, since_days=7
                        ),
                    }

        raise exceptions.rest.RequestError('invalid request')

    def put(self) -> typing.Any:
        raise exceptions.rest.RequestError()  # Not allowed right now
