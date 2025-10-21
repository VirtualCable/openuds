# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
from collections import defaultdict
import typing
import collections.abc
import datetime
import logging

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class StatsCounters(models.Model):
    """
    Statistics about counters (number of users at a given time, number of services at a time, whatever...)
    """

    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)
    counter_type = models.SmallIntegerField(db_index=True, default=0)
    stamp = models.IntegerField(db_index=True, default=0)
    value = models.IntegerField(db_index=True, default=0)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[StatsCounters]'

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        db_table = 'uds_stats_c'
        app_label = 'uds'

    @staticmethod
    def get_grouped(
        owner_type: typing.Union[int, collections.abc.Iterable[int]],
        counter_type: int,
        since: typing.Union[None, int, datetime.datetime] = None,
        to: typing.Union[None, int, datetime.datetime] = None,
        owner_id: typing.Union[None, int, collections.abc.Iterable[int]] = None,
        interval: typing.Optional[int] = None,
        max_intervals: typing.Optional[int] = None,
        use_max: bool = False,
        limit: typing.Optional[int] = None,
    ) -> typing.Generator[tuple[int, int], None, None]:
        """
        Returns a QuerySet of counters grouped by owner_type and counter_type
        """
        if isinstance(since, datetime.datetime):
            # Convert to unix timestamp
            since = int(since.timestamp())
        if not since:
            # Get first timestamp from table, we knwo table has at least one record
            first = StatsCounters.objects.order_by('stamp').first()
            if first is None:
                return  # No data
            since = first.stamp
        if isinstance(to, datetime.datetime):
            # Convert to unix timestamp
            to = int(to.timestamp())
        if not to:
            # Get last timestamp from table, we know table has at least one record
            last = StatsCounters.objects.order_by('-stamp').first()
            if last is None:
                return
            to = last.stamp

        q = StatsCounters.objects.filter(counter_type=counter_type, stamp__gte=since, stamp__lte=to)

        if isinstance(owner_type, int):
            q = q.filter(owner_type=owner_type)
        else:
            q = q.filter(owner_type__in=owner_type)

        if owner_id:
            # If owner_id is a int, we add it to the list
            if isinstance(owner_id, int):
                q = q.filter(owner_id=owner_id)
            else:
                q = q.filter(owner_id__in=owner_id)

        if q.count() == 0:
            return

        interval = interval or 600

        # Max intervals, if present, will adjust interval (that are seconds)
        max_intervals = max_intervals or 0
        values = q.values_list('stamp', 'value')
        if max_intervals > 0:
            count = len(values)
            max_intervals = max(min(max_intervals, count), 2)
            interval = int(to - since) // max_intervals

        # If interval is 0, we return the values as they are
        if interval == 0:
            yield from values
            return

        # If interval is greater than 0, we group by interval using average or max as requested
        result: dict[int, int] = defaultdict(int)
        for counter, i in enumerate(values, 1):
            group_by_stamp = i[0] - (i[0] % interval)
            if use_max:
                result[group_by_stamp] = max(result[group_by_stamp], i[1])
            else:
                result[group_by_stamp] = (result[group_by_stamp] * (counter - 1) + i[1]) // counter

        for k, v in result.items():
            yield (k, v)

        # if interval > 0:
        #     q = q.extra(  # type: ignore # nosec: SQL injection is not possible here
        #         select={
        #             'group_by_stamp': f'stamp - (stamp %% {interval})',  # f'{floor}(stamp / {interval}) * {interval}',
        #         },
        #     )

        # fnc = models.Avg('value') if not use_max else models.Max('value')

        # q = (
        #     q.order_by('group_by_stamp')  # type: ignore
        #     .values('group_by_stamp')
        #     .annotate(
        #         value=fnc,
        #     )
        # )
        # if limit:
        #     q = q[: limit]

        # for i in q.values('group_by_stamp', 'value'):
        #     yield (int(i['group_by_stamp']), i['value'])

    def __str__(self) -> str:
        return f'{timezone.make_aware(datetime.datetime.fromtimestamp(self.stamp))} - {self.owner_id}:{self.owner_type}:{self.counter_type} {self.value}'
