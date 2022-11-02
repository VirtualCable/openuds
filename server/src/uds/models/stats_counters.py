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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import types
import datetime
import logging

from django.db import models

from .util import NEVER_UNIX
from .util import getSqlDatetimeAsUnix
from .util import getSqlFnc


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

    class Meta:
        """
        Meta class to declare db table
        """

        db_table = 'uds_stats_c'
        app_label = 'uds'
        indexes = [
            models.Index(fields=['owner_type', 'stamp']),
            models.Index(fields=['owner_type', 'counter_type', 'stamp']),
        ]

    @staticmethod
    def get_grouped(
        owner_type: typing.Union[int, typing.Iterable[int]], counter_type: int, **kwargs
    ) -> typing.Generator['StatsCounters', None, None]:
        """
        Returns a QuerySet of counters grouped by owner_type and counter_type
        """
        if isinstance(owner_type, int):
            owner_type = [owner_type]

        q = StatsCounters.objects.filter(owner_type__in=owner_type, counter_type=counter_type)

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
            since = StatsCounters.objects.order_by('stamp').first().stamp # type: ignore
        to = kwargs.get('to')
        if isinstance(to, datetime.datetime):
            # Convert to unix timestamp
            to = int(to.timestamp())
        if not to:
            # Get last timestamp from table, we know table has at least one record
            to = StatsCounters.objects.order_by('-stamp').first().stamp # type: ignore

        q = q.filter(stamp__gte=since, stamp__lte=to)

        if q.count() == 0:
            return

        interval = kwargs.get('interval') or 600

        # Max intervals, if present, will adjust interval (that are seconds)
        max_intervals = kwargs.get('max_intervals') or 0
        if max_intervals > 0:
            count = q.count()
            if max_intervals < count:
                max_intervals = count
            interval = int(to - since) / max_intervals

        floor = getSqlFnc('FLOOR')
        if interval > 0:
            q = q.extra(
                select={
                    'group_by_stamp': f'{floor}(stamp / {interval}) * {interval}',
                },
            )


        fnc = models.Avg('value') if not kwargs.get('use_max') else models.Max('value')

        q = q.order_by('group_by_stamp').values('group_by_stamp').annotate(
            value=fnc,
        )
        if kwargs.get('limit'):
            q = q[:kwargs['limit']]

        for i in q:
            yield StatsCounters(id=-1, owner_type=-1, counter_type=-1, stamp=i['group_by_stamp'], value=i['value'])

    @staticmethod
    def get_grouped_old(
        owner_type: typing.Union[int, typing.Iterable[int]], counter_type: int, **kwargs
    ) -> 'models.QuerySet[StatsCounters]':
        """
        Returns the average stats grouped by interval for owner_type and owner_id (optional)

        Note: if someone cant get this more optimized, please, contribute it!
        """

        filt = 'owner_type'
        if isinstance(owner_type, (list, tuple, types.GeneratorType)):
            filt += ' in (' + ','.join((str(x) for x in owner_type)) + ')'
        else:
            filt += '=' + str(owner_type)

        owner_id = kwargs.get('owner_id', None)
        if owner_id:
            filt += ' AND OWNER_ID'
            if isinstance(owner_id, (list, tuple, types.GeneratorType)):
                filt += ' in (' + ','.join(str(x) for x in owner_id) + ')'
            else:
                filt += '=' + str(owner_id)

        filt += ' AND counter_type=' + str(counter_type)

        since = kwargs.get('since', None)
        to = kwargs.get('to', None)

        since = int(since) if since else NEVER_UNIX
        to = int(to) if to else getSqlDatetimeAsUnix()

        interval = int(
            kwargs.get('interval') or '600'
        )  # By default, group items in ten minutes interval (600 seconds)

        max_intervals = kwargs.get('max_intervals')

        limit = kwargs.get('limit')

        if max_intervals:
            # Protect against division by "elements-1" a few lines below
            max_intervals = int(max_intervals) if int(max_intervals) > 1 else 2

            if owner_id is None:
                q = StatsCounters.objects.filter(stamp__gte=since, stamp__lte=to)
            else:
                if isinstance(owner_id, (list, tuple, types.GeneratorType)):
                    q = StatsCounters.objects.filter(
                        owner_id__in=owner_id, stamp__gte=since, stamp__lte=to
                    )
                else:
                    q = StatsCounters.objects.filter(
                        owner_id=owner_id, stamp__gte=since, stamp__lte=to
                    )

            if isinstance(owner_type, (list, tuple, types.GeneratorType)):
                q = q.filter(owner_type__in=owner_type)
            else:
                q = q.filter(owner_type=owner_type)

            if q.count() > max_intervals:
                first = q.order_by('stamp')[0].stamp    # type: ignore  # Slicing is not supported by pylance right now
                last = q.order_by('stamp').reverse()[0].stamp    # type: ignore  # Slicing is not supported by pylance right now
                interval = int((last - first) / (max_intervals - 1))

        stampValue = '{ceil}(stamp/{interval})'.format(
            ceil=getSqlFnc('CEIL'), interval=interval
        )
        filt += ' AND stamp>={since} AND stamp<={to} GROUP BY {stampValue} ORDER BY stamp'.format(
            since=since, to=to, stampValue=stampValue
        )

        if limit:
            filt += ' LIMIT {}'.format(limit)

        if kwargs.get('use_max', False):
            fnc = getSqlFnc('MAX') + ('(value)')
        else:
            fnc = getSqlFnc('CEIL') + '({}(value))'.format(getSqlFnc('AVG'))

        # fnc = getSqlFnc('MAX' if kwargs.get('use_max', False) else 'AVG')

        query = (
            'SELECT -1 as id,-1 as owner_id,-1 as owner_type,-1 as counter_type, '
            + stampValue
            + '*{}'.format(interval)
            + ' AS stamp, '
            + '{} AS value '
            'FROM {} WHERE {}'
        ).format(fnc, StatsCounters._meta.db_table, filt)

        logger.debug('Stats query: %s', query)

        # We use result as an iterator
        return typing.cast(
            'models.QuerySet[StatsCounters]', StatsCounters.objects.raw(query)
        )

    def __str__(self):
        return u"Counter of {}({}): {} - {} - {}".format(
            self.owner_type, self.owner_id, self.stamp, self.counter_type, self.value
        )
