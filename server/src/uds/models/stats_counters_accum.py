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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import enum
import datetime
import logging

from django.db import models

from .stats_counters import StatsCounters

logger = logging.getLogger(__name__)


class StatsCountersAccum(models.Model):
    """
    Statistics about counters (number of users at a given time, number of services at a time, whatever...)
    """

    # Valid intervals types for counters data
    class IntervalType(enum.IntEnum):
        HOUR = 1
        DAY = 2

        def seconds(self) -> int:
            """Returns the number of seconds for this interval type"""
            match self:
                case self.HOUR:
                    return 3600
                case self.DAY:
                    return 86400
            raise ValueError('Invalid interval type')

        def prev(self) -> 'StatsCountersAccum.IntervalType':
            """Returns the previous interval type"""
            match self:
                case self.HOUR:
                    raise ValueError('No previous interval for HOUR')
                case self.DAY:
                    return StatsCountersAccum.IntervalType.HOUR
            raise ValueError('Invalid interval type')
        
        def is_base_interval(self) -> bool:
            """Returns if this is the base interval"""
            return self == StatsCountersAccum.IntervalType.HOUR

    owner_type = models.SmallIntegerField(default=0)
    owner_id = models.IntegerField(default=0)
    counter_type = models.SmallIntegerField(default=0)
    interval_type = models.SmallIntegerField(
        default=IntervalType.HOUR, choices=[(x.value, x.name) for x in IntervalType]
    )
    stamp = models.IntegerField(default=0)
    # Values
    v_count = models.IntegerField(default=0)
    v_sum = models.IntegerField(default=0)
    v_max = models.IntegerField(default=0)
    v_min = models.IntegerField(default=0)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[StatsCountersAccum]'

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        indexes = [
            models.Index(
                fields=[
                    'stamp',
                    'interval_type',
                    'counter_type',
                    'owner_type',
                    'owner_id',
                ],
                name='uds_stats_all',
            ),
            models.Index(
                fields=['stamp', 'interval_type', 'counter_type'],
                name='uds_stats_partial',
            ),
            models.Index(fields=['stamp', 'interval_type'], name='uds_stats_stamp'),
        ]

        db_table = 'uds_stats_c_accum'
        app_label = 'uds'

    @staticmethod
    def _adjust_to_interval(
        value: int = -1,
        interval_type: 'StatsCountersAccum.IntervalType' = IntervalType.HOUR,
    ) -> int:
        """Adjusts a timestamp to the given interval"""
        if value == -1:
            value = int(datetime.datetime.now().timestamp())
        return value - (value % interval_type.seconds())

    @staticmethod
    def acummulate(interval_type: 'IntervalType', max_days: int = 7) -> None:
        """
        Compresses data in the table, generating "compressed" version of the data (mean values)
        """
        logger.debug(
            'Optimizing stats counters table for %s (max chunk days=%s)',
            interval_type,
            max_days,
        )

        # Assign values depending on interval type
        model: typing.Union[
            type['StatsCountersAccum'],
            type['StatsCounters'],
        ]
        # If base interval (that menas an inteval that must be readed from stats_c), 
        # we will use StatsCounters to create the accum
        # Else, we will use StatsCountersAccum to create the accum from previous interval
        # (for example, to create daily accum from hourly data)
        model = StatsCounters if interval_type.is_base_interval() else StatsCountersAccum

        # Accumulate INTERVAL from StatsCounters
        interval = interval_type.seconds()

        # Get last stamp in table for this interval_type
        start_record: 'StatsCounters|StatsCountersAccum|None' = (
            StatsCountersAccum.objects.filter(interval_type=interval_type)
            .order_by('stamp')
            .last()
        )

        if start_record is None:
            # No last stamp record, start from first StatsCounters record
            start_record = model.objects.order_by('stamp').first()

        if start_record is None:  # Empty table
            return

        start_stamp = StatsCountersAccum._adjust_to_interval(
            start_record.stamp, interval_type=interval_type
        )  # Adjust to hour

        # End date is now, adjusted to interval so we dont have "leftovers"
        end_stamp = StatsCountersAccum._adjust_to_interval(interval_type=interval_type)

        # If time lapse is greater that max_days days, we will optimize in 30 days chunks
        # This is to avoid having a huge query that will take a lot of time
        if end_stamp - start_stamp > (max_days * 24 * 3600):
            logger.info(
                'Accumulating stats counters table in chunks, because of large time lapse'
            )
            end_stamp = start_stamp + (max_days * 24 * 3600)

        # Fix end_stamp to interval, using base_end_stamp
        end_stamp = StatsCountersAccum._adjust_to_interval(
            end_stamp, interval_type=interval_type
        )

        logger.debug(
            'Accumulating stats counters table from %s to %s',
            datetime.datetime.fromtimestamp(start_stamp),
            datetime.datetime.fromtimestamp(end_stamp),
        )

        # Get all records for this owner_type, counter_type, owner_id
        query = (
            model.objects.filter(  # nosec: SQL injection is not possible here, all values are controlled
                stamp__gte=start_stamp,
                stamp__lt=end_stamp,
            )
            .extra(
                select={
                    'group_by_stamp': f'stamp - (stamp %% {interval})',  # f'{floor}(stamp / {interval})',
                    'owner_id': 'owner_id',
                    'owner_type': 'owner_type',
                    'counter_type': 'counter_type',
                },
            )

            .values('group_by_stamp', 'owner_id', 'owner_type', 'counter_type')
        )

        if model == StatsCounters:
            query = query.annotate(
                min=models.Min('value'),
                max=models.Max('value'),
                count=models.Count('value'),
                sum=models.Sum('value'),
            )
        else:
            # Only get Hourly data
            query = query.filter(interval_type=interval_type.prev()).annotate(
                min=models.Min('v_min'),
                max=models.Max('v_max'),
                count=models.Sum('v_count'),
                sum=models.Sum('v_sum'),
            )
            
        logger.debug('Query: %s', query.query)

        # Stores accumulated data in StatsCountersAccum
        # Acummulate data, only register if there is data
        accumulated: list[StatsCountersAccum] = [
            StatsCountersAccum(
                owner_type=rec['owner_type'],
                owner_id=rec['owner_id'],
                counter_type=rec['counter_type'],
                interval_type=interval_type,
                stamp=rec['group_by_stamp'] + interval_type.seconds(),
                v_count=rec['count'],
                v_sum=rec['sum'],
                v_min=rec['min'],
                v_max=rec['max'],
            )
            for rec in query
            if rec['sum'] or rec['min'] or rec['max']
        ]

        logger.debug('Inserting %s records', len(accumulated))
        # Insert in chunks of 2500 records
        while accumulated:
            StatsCountersAccum.objects.bulk_create(accumulated[:2500])
            accumulated = accumulated[2500:]

    def __str__(self) -> str:
        return f'{datetime.datetime.fromtimestamp(self.stamp)} - {self.owner_type}:{self.owner_id}:{self.counter_type} {StatsCountersAccum.IntervalType(self.interval_type)} {self.v_count},{self.v_sum},{self.v_min},{self.v_max}'
