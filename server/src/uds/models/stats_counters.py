# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import datetime
import logging

from django.db import models

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
    objects: 'models.manager.Manager[StatsCounters]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare db table
        """

        db_table = 'uds_stats_c'
        app_label = 'uds'

    @staticmethod
    def get_grouped(
        owner_type: typing.Union[int, typing.Iterable[int]], counter_type: int, **kwargs
    ) -> typing.Generator[typing.Tuple[int, int], None, None]:
        """
        Returns a QuerySet of counters grouped by owner_type and counter_type
        """
        if isinstance(owner_type, int):
            owner_type = [owner_type]

        q = StatsCounters.objects.filter(
            owner_type__in=owner_type,
            counter_type=counter_type,
        )

        if kwargs.get('owner_id'):
            # If owner_id is a int, we add it to the list
            if isinstance(kwargs['owner_id'], int):
                kwargs['owner_id'] = [kwargs['owner_id']]

            q = q.filter(owner_id__in=kwargs['owner_id'])

        if q.count() == 0:
            return

        since = kwargs.get('since')
        if isinstance(since, datetime.datetime):
            # Convert to unix timestamp
            since = int(since.timestamp())
        if not since:
            # Get first timestamp from table, we knwo table has at least one record
            since = StatsCounters.objects.order_by('stamp').first().stamp  # type: ignore
        to = kwargs.get('to')
        if isinstance(to, datetime.datetime):
            # Convert to unix timestamp
            to = int(to.timestamp())
        if not to:
            # Get last timestamp from table, we know table has at least one record
            to = StatsCounters.objects.order_by('-stamp').first().stamp  # type: ignore

        q = q.filter(stamp__gte=since, stamp__lte=to)

        if q.count() == 0:
            return

        interval = kwargs.get('interval') or 600

        # Max intervals, if present, will adjust interval (that are seconds)
        max_intervals = kwargs.get('max_intervals') or 0
        if max_intervals > 0:
            count = q.count()
            max_intervals = max(min(max_intervals, count), 2)
            interval = int(to - since) / max_intervals

        if interval > 0:
            q = q.extra(  # nosec: SQL injection is not possible here
                select={
                    'group_by_stamp': f'stamp - (stamp %% {interval})',  # f'{floor}(stamp / {interval}) * {interval}',
                },
            )

        fnc = models.Avg('value') if not kwargs.get('use_max') else models.Max('value')

        q = (
            q.order_by('group_by_stamp')
            .values('group_by_stamp')
            .annotate(
                value=fnc,
            )
        )
        if kwargs.get('limit'):
            q = q[: kwargs['limit']]

        for i in q.values('group_by_stamp', 'value'):
            yield (int(i['group_by_stamp']), i['value'])

    def __str__(self):
        return f'{datetime.datetime.fromtimestamp(self.stamp)} - {self.owner_id}:{self.owner_type}:{self.counter_type} {self.value}'
