# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import typing
import datetime


from uds import models
from uds.core.util.stats import counters

from ...utils.test import UDSTransactionTestCase
from ...fixtures import stats_counters as fixtures_stats_counters

from uds.core.workers import stats_collector
from uds.core.environment import Environment
from uds.core.util import config


START_DATE = datetime.datetime(2009, 12, 4, 0, 0, 0)
# Some random values,
DAYS = 4
NUMBER_PER_HOUR = 6  # Can be any value divisor of 3600
NUMBER_OF_POOLS = 11
COUNTERS_TYPES = [counters.CT_ASSIGNED, counters.CT_INUSE]


class StatsFunction:
    counter: int
    multiplier: int

    def __init__(self, counter_multiplier: int = 100):
        self.counter = 0
        self.multiplier = counter_multiplier

    def __call__(self, i: int, number_per_hour: int) -> int:
        self.counter += 1
        return self.counter * 100


class StatsAcummulatorTest(UDSTransactionTestCase):
    def setUp(self):
        # In fact, real data will not be assigned to Userservices, but it's ok for testing
        for pool_id in range(NUMBER_OF_POOLS):
            fixtures_stats_counters.create_stats_interval_total(
                pool_id,
                COUNTERS_TYPES,
                START_DATE,
                days=DAYS,
                number_per_hour=NUMBER_PER_HOUR,
                value=StatsFunction(10 ** (pool_id + 1)),
                owner_type=counters.OT_DEPLOYED,
            )

        # Setup worker
        config.GlobalConfig.STATS_ACCUM_MAX_CHUNK_TIME.set(DAYS // 2 + 1)
        stats_collector.StatsAccumulator.setup()

    def test_stats_accumulator(self):
        # Ensure first that we have correct number of base stats
        base_stats = models.StatsCounters.objects.all()
        total_base_stats = (
            DAYS * 24 * NUMBER_PER_HOUR * NUMBER_OF_POOLS * len(COUNTERS_TYPES)
        )  # All stats
        self.assertEqual(base_stats.count(), total_base_stats)

        optimizer = stats_collector.StatsAccumulator(Environment.getTempEnv())
        optimizer.run()
        # Shoul have DAYS // 2 + 1 stats
        hour_stats = models.StatsCountersAccum.objects.filter(
            interval_type=models.StatsCountersAccum.IntervalType.HOUR
        )
        total_hour_stats = (DAYS // 2 + 1) * 24 * NUMBER_OF_POOLS * len(COUNTERS_TYPES)
        # Ensure that we have correct number of stats
        self.assertEqual(hour_stats.count(), total_hour_stats)
        # Days stats
        day_stats = models.StatsCountersAccum.objects.filter(
            interval_type=models.StatsCountersAccum.IntervalType.DAY
        )
        total_day_stats = (DAYS // 2 + 1) * NUMBER_OF_POOLS * len(COUNTERS_TYPES)
        self.assertEqual(day_stats.count(), total_day_stats)

        # Run it twice, now it will collect DAY - (DAYS // 2 + 1) stats      
        optimizer.run()
        # In fact, hour, day and week have AVG and MAX, so we need to multiply by 2 on testing
        total_hour_stats = DAYS * 24 * NUMBER_OF_POOLS * len(COUNTERS_TYPES)
        self.assertEqual(hour_stats.count(), total_hour_stats)
        # Days stats
        day_stats = models.StatsCountersAccum.objects.filter(
            interval_type=models.StatsCountersAccum.IntervalType.DAY
        )
        total_day_stats = DAYS * NUMBER_OF_POOLS * len(COUNTERS_TYPES)
        self.assertEqual(day_stats.count(), total_day_stats)

        # Calculate sum of stats, by hour
        data: typing.Dict[str, typing.Dict[int, typing.List[int]]] = {}
        for i in base_stats.order_by('owner_id', 'counter_type', 'stamp'):
            stamp = i.stamp - (i.stamp % 3600) + 3600  # Round to hour and to next hour
            d = data.setdefault(f'{i.owner_id}{i.counter_type}', {})
            d.setdefault(stamp, []).append(i.value)

        # Last hour NEVER is completed (until next hour appears), so it's not included in hour stats
        # Check that hourly stats are correctly generated
        stat: 'models.StatsCountersAccum'
        for stat in hour_stats.order_by('owner_id', 'stamp'):
            stamp = stat.stamp  # Already rounded to hour
            d = data[f'{stat.owner_id}{stat.counter_type}']
            self.assertEqual(stat.v_sum, sum(d[stamp]))
            self.assertEqual(stat.v_max, max(d[stamp]))
            self.assertEqual(stat.v_min, min(d[stamp]))
            self.assertEqual(stat.v_count, len(d[stamp]))

        # Recalculate sum of stats, now from StatsCountersAccum (hourly)
        data: typing.Dict[str, typing.Dict[int, typing.List[int]]] = {}
        for i in hour_stats.order_by('owner_id', 'counter_type', 'stamp'):
            pass

        return

        # Calculate sum of stats, by hour, day
        data: typing.Dict[int, typing.Dict[int, typing.List[int]]] = {}
        for i in base_stats.order_by('owner_id', 'stamp'):
            stamp = i.stamp - (i.stamp % 3600) + 3600  # Round to hour and to next hour
            d = data.setdefault(i.owner_id, {})
            d.setdefault(stamp, []).append(i.value)

        # Last hour NEVER is completed (until next hour appears), so it's not included in hour stats

        # Check that hourly stats are correctly generated
        for i in hour_stats.order_by('owner_id', 'stamp'):
            stamp = i.stamp  # Already rounded to hour
            d = data[i.owner_id]
            if i.interval_operation == models.StatsCounters.IntervalOperation.AVG:
                self.assertEqual(i.value, sum(d[stamp]) // len(d[stamp]))
            else:
                self.assertEqual(i.value, max(d[stamp]))

        # Now check day stats, max and avg
        for op in (
            models.StatsCounters.IntervalOperation.AVG,
            models.StatsCounters.IntervalOperation.MAX,
        ):
            data = {}
            for i in hour_stats.filter(interval_operation=op).order_by(
                'owner_id', 'stamp'
            ):
                stamp = i.stamp - (i.stamp % 86400) + 86400
                d = data.setdefault(i.owner_id, {})
                d.setdefault(stamp, []).append(i.value)

            # Last day NEVER is completed (until next day appears), so it's not included in day stats
            for i in day_stats.filter(interval_operation=op).order_by(
                'owner_id', 'stamp'
            ):
                stamp = i.stamp  # Already rounded to day
                d = data[i.owner_id]
                if i.interval_operation == models.StatsCounters.IntervalOperation.AVG:
                    self.assertEqual(i.value, sum(d[stamp]) // len(d[stamp]))
                else:
                    self.assertEqual(i.value, max(d[stamp]))
