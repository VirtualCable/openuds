# -*- coding: utf-8 -*-
#
# Copyright (c) 2013-2023 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from uds import models
from uds.core.util import model
from uds.core import types
from uds.core.util.stats import counters
from uds.core.managers.stats import StatsManager
from uds.core.jobs import Job
from uds.core.util import config


logger = logging.getLogger(__name__)


class DeployedServiceStatsCollector(Job):
    """
    This Job is responsible for collecting stats for every deployed service every ten minutes
    """

    frecuency = 599  # Once every ten minutes
    friendly_name = 'Deployed Service Stats'

    def run(self) -> None:
        logger.debug('Starting Deployed service stats collector')

        service_pool_to_check = models.ServicePool.objects.filter(state__in=types.states.State.PROCESABLE_STATES).iterator()
        stamp = model.sql_now()
        # Global counters
        total_assigned, total_inuse, total_cached = 0, 0, 0
        for service_pool in service_pool_to_check:
            try:
                fltr = service_pool.assigned_user_services().exclude(
                    state__in=types.states.State.INFO_STATES
                )
                assigned = fltr.count()
                in_use = fltr.filter(in_use=True).count()
                # Cached user services
                cached = (
                    service_pool.cached_users_services()
                    .exclude(state__in=types.states.State.INFO_STATES)
                    .count()
                )
                total_assigned += assigned
                total_inuse += in_use
                total_cached += cached
                counters.add_counter(
                    service_pool, types.stats.CounterType.ASSIGNED, assigned, stamp=stamp
                )
                counters.add_counter(service_pool, types.stats.CounterType.INUSE, in_use, stamp=stamp)
                counters.add_counter(
                    service_pool, types.stats.CounterType.CACHED, cached, stamp=stamp
                )
            except Exception:
                logger.exception(
                    'Getting counters for service pool %s', service_pool.name
                )
        # Store a global "fake pool" with all stats
        sp = models.ServicePool()
        sp.id = -1
        counters.add_counter(sp, types.stats.CounterType.ASSIGNED, total_assigned, stamp=stamp)
        counters.add_counter(sp, types.stats.CounterType.INUSE, total_inuse, stamp=stamp)
        counters.add_counter(sp, types.stats.CounterType.CACHED, total_cached, stamp=stamp)

        total_users, total_assigned, total_users_with_service = 0, 0, 0
        for auth in models.Authenticator.objects.all():
            fltr_user = auth.users.filter(userServices__state__in=types.states.State.VALID_STATES).order_by()
            users = auth.users.all().count()
            users_with_service = fltr_user.values('id').distinct().count()  # Use "values" to simplify query (only id)
            number_assigned_services = fltr_user.values('id').count()
            # Global counters
            total_users += users
            total_assigned += number_assigned_services
            total_users_with_service += users_with_service

            counters.add_counter(auth, types.stats.CounterType.AUTH_USERS, users, stamp=stamp)
            counters.add_counter(
                auth, types.stats.CounterType.AUTH_SERVICES, number_assigned_services, stamp=stamp
            )
            counters.add_counter(
                auth,
                types.stats.CounterType.AUTH_USERS_WITH_SERVICES,
                users_with_service,
                stamp=stamp,
            )

        au = models.Authenticator()
        au.id = -1
        counters.add_counter(au, types.stats.CounterType.AUTH_USERS, total_users, stamp=stamp)
        counters.add_counter(au, types.stats.CounterType.AUTH_SERVICES, total_assigned, stamp=stamp)
        counters.add_counter(
            au, types.stats.CounterType.AUTH_USERS_WITH_SERVICES, total_users_with_service, stamp=stamp
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

    def run(self) -> None:
        logger.debug('Starting statistics cleanup')
        try:
            StatsManager.manager().perform_counters_maintenance()
        except Exception:
            logger.exception('Cleaning up counters')

        try:
            StatsManager.manager().perform_events_maintenancecleanup_events()
        except Exception:
            logger.exception('Cleaning up events')

        logger.debug('Done statistics cleanup')


class StatsAccumulator(Job):
    """
    This Job is responsible of compressing stats tables.
    This is done by:
        * For HOUR, DAY
    """
    frecuency = 3600  # Executed every hours
    frecuency_cfg = (
        config.GlobalConfig.STATS_ACCUM_FREQUENCY
    )
    friendly_name = 'Statistics acummulator'

    def run(self) -> None:
        try:
            StatsManager.manager().acummulate(config.GlobalConfig.STATS_ACCUM_MAX_CHUNK_TIME.as_int())
        except Exception:
            logger.exception('Compressing counters')

        logger.debug('Done statistics compression')
