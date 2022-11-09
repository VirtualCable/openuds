# -*- coding: utf-8 -*-
#
# Copyright (c) 2013-2020 Virtual Cable S.L.U.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core.util.state import State
from uds.core.util.stats import counters
from uds.core.managers.stats import StatsManager
from uds.core.jobs import Job
from uds.core.util import config


logger = logging.getLogger(__name__)

# Early declaration of config variable
STATS_ACCUM_FREQUENCY = config.Config.section(config.ADMIN_SECTION).value(
    'Stats Accumulation Frequency',
    '14400',
    type=config.Config.NUMERIC_FIELD,
    help=_('Frequency of stats collection in seconds. Default is 4 hours (14400 seconds)'),
)
STATS_ACCUM_MAX_CHUNK_TIME = config.Config.section(config.ADMIN_SECTION).value(
    'Stats Accumulation Chunk',
    '7',
    type=config.Config.NUMERIC_FIELD,
    help=_('Maximum number of time to accumulate on one run. Default is 7 (1 week)'),
)

class DeployedServiceStatsCollector(Job):
    """
    This Job is responsible for collecting stats for every deployed service every ten minutes
    """

    frecuency = 599  # Once every ten minutes
    friendly_name = 'Deployed Service Stats'

    def run(self) -> None:
        logger.debug('Starting Deployed service stats collector')

        servicePoolsToCheck: typing.Iterable[
            models.ServicePool
        ] = models.ServicePool.objects.filter(state=State.ACTIVE).iterator()
        stamp = models.getSqlDatetime()
        # Global counters
        totalAssigned, totalInUse, totalCached = 0, 0, 0
        for servicePool in servicePoolsToCheck:
            try:
                fltr = servicePool.assignedUserServices().exclude(
                    state__in=State.INFO_STATES
                )
                assigned = fltr.count()
                inUse = fltr.filter(in_use=True).count()
                # Cached user services
                cached = (
                    servicePool.cachedUserServices()
                    .exclude(state__in=State.INFO_STATES)
                    .count()
                )
                totalAssigned += assigned
                totalInUse += inUse
                totalCached += cached
                counters.addCounter(
                    servicePool, counters.CT_ASSIGNED, assigned, stamp=stamp
                )
                counters.addCounter(servicePool, counters.CT_INUSE, inUse, stamp=stamp)
                counters.addCounter(
                    servicePool, counters.CT_CACHED, cached, stamp=stamp
                )
            except Exception:
                logger.exception(
                    'Getting counters for service pool %s', servicePool.name
                )
        # Store a global "fake pool" with all stats
        sp = models.ServicePool()
        sp.id = -1
        counters.addCounter(sp, counters.CT_ASSIGNED, totalAssigned, stamp=stamp)
        counters.addCounter(sp, counters.CT_INUSE, totalInUse, stamp=stamp)
        counters.addCounter(sp, counters.CT_CACHED, totalCached, stamp=stamp)

        totalUsers, totalAssigned, totalWithService = 0, 0, 0
        for auth in models.Authenticator.objects.all():
            fltr = auth.users.filter(userServices__isnull=False).exclude(
                userServices__state__in=State.INFO_STATES
            )
            users = auth.users.all().count()
            users_with_service = fltr.distinct().count()
            number_assigned_services = fltr.count()
            # Global counters
            totalUsers += users
            totalAssigned += number_assigned_services
            totalWithService += users_with_service

            counters.addCounter(auth, counters.CT_AUTH_USERS, users, stamp=stamp)
            counters.addCounter(
                auth, counters.CT_AUTH_SERVICES, number_assigned_services, stamp=stamp
            )
            counters.addCounter(
                auth,
                counters.CT_AUTH_USERS_WITH_SERVICES,
                users_with_service,
                stamp=stamp,
            )

        au = models.Authenticator()
        au.id = -1
        counters.addCounter(au, counters.CT_AUTH_USERS, totalUsers, stamp=stamp)
        counters.addCounter(au, counters.CT_AUTH_SERVICES, totalAssigned, stamp=stamp)
        counters.addCounter(
            au, counters.CT_AUTH_USERS_WITH_SERVICES, totalWithService, stamp=stamp
        )

        logger.debug('Done Deployed service stats collector')


class StatsCleaner(Job):
    """
    This Job is responsible of housekeeping of stats tables.
    This is done by:
        * Deleting all records
        * Optimize table
    """

    frecuency = 3600 * 24 * 15  # Ejecuted just once every 15 days
    friendly_name = 'Statistic housekeeping'

    def run(self):
        logger.debug('Starting statistics cleanup')
        try:
            StatsManager.manager().cleanupCounters()
        except Exception:
            logger.exception('Cleaning up counters')

        try:
            StatsManager.manager().cleanupEvents()
        except Exception:
            logger.exception('Cleaning up events')

        logger.debug('Done statistics cleanup')


class StatsAccumulator(Job):
    """
    This Job is responsible of compressing stats tables.
    This is done by:
        * For HOUR, DAY, WEEK
        * For every row of same owner_id, owner_type
    """
    frecuency = 3600  # Executed every 4 hours
    frecuency_cfg = (
        STATS_ACCUM_FREQUENCY
    )
    friendly_name = 'Statistics acummulator'

    def run(self):
        try:
            StatsManager.manager().acummulate(STATS_ACCUM_MAX_CHUNK_TIME.getInt())
        except Exception as e:
            logger.exception('Compressing counters')

        logger.debug('Done statistics compression')
