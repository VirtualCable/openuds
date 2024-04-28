# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import collections.abc
import dataclasses
import datetime
import logging
import time
import typing

from uds.core import types
from uds.core.util import singleton
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_now, sql_stamp_seconds
from uds.models import StatsCounters, StatsCountersAccum, StatsEvents

if typing.TYPE_CHECKING:
    from django.db import models

logger = logging.getLogger(__name__)

_FLDS_EQUIV: typing.Final[collections.abc.Mapping[str, collections.abc.Iterable[str]]] = {
    'fld1': ('username', 'platform', 'duration'),
    'fld2': ('source', 'srcip', 'browser', 'sent'),
    'fld3': ('destination', 'dstip', 'received'),
    'fld4': ('uniqueid', 'tunnel'),
}

_REVERSE_FLDS_EQUIV: typing.Final[collections.abc.Mapping[str, str]] = {
    i: fld for fld, aliases in _FLDS_EQUIV.items() for i in aliases
}


@dataclasses.dataclass
class AccumStat:
    stamp: int
    n: int  # Number of elements in this interval
    sum: int  # Sum of elements in this interval
    max: int  # Max of elements in this interval
    min: int  # Min of elements in this interval


class StatsManager(metaclass=singleton.Singleton):
    """
    Manager for statistics, so we can provide usefull info about platform usage

    Right now, we are going to provide an interface to "counter stats", that is, statistics
    that has counters (such as how many users is at a time active at platform, how many services
    are assigned, are in use, in cache, etc...
    """
    @staticmethod
    def manager() -> 'StatsManager':
        return StatsManager()  # Singleton pattern will return always the same instance

    def _do_maintanance(
        self,
        model: type[typing.Union['StatsCounters', 'StatsEvents', 'StatsCountersAccum']],
    ) -> None:
        minTime = time.mktime(
            (sql_now() - datetime.timedelta(days=GlobalConfig.STATS_DURATION.as_int())).timetuple()
        )
        model.objects.filter(stamp__lt=minTime).delete()

    # Counter stats
    def add_counter(
        self,
        owner_type: types.stats.CounterOwnerType,
        owner_id: int,
        counterType: types.stats.CounterType,
        counterValue: int,
        stamp: typing.Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Adds a new counter stats to database.

        Args:

            owner_type: type of owner (integer, from internal tables)
            owner_id:  id of the owner
            counterType: The type of counter that will receive the value (look at uds.core.util.stats.counters module)
            counterValue: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:

            Nothing
        """
        if stamp is None:
            stamp = sql_now()

        # To Unix epoch
        stampInt = int(time.mktime(stamp.timetuple()))  # pylint: disable=maybe-no-member

        try:
            StatsCounters.objects.create(
                owner_type=owner_type,
                owner_id=owner_id,
                counter_type=counterType,
                value=counterValue,
                stamp=stampInt,
            )
            return True
        except Exception:
            logger.error('Exception handling counter stats saving (maybe database is full?)')
        return False

    def enumerate_counters(
        self,
        ownerType: int,
        counterType: int,
        ownerIds: typing.Union[collections.abc.Iterable[int], int, None],
        since: datetime.datetime,
        to: datetime.datetime,
        interval: typing.Optional[int],
        max_intervals: typing.Optional[int],
        limit: typing.Optional[int],
        use_max: bool = False,
    ) -> collections.abc.Iterable[tuple[int, int]]:
        """
        Retrieves counters from item

        Args:

            counterTye: Type of counter to get values
            counterId: (optional), if specified, limit counter to only this id, all ids for specidied type if not
            maxElements: (optional) Maximum number of elements to retrieve, all if nothing specified
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified

        Returns:

            Iterator, containing (date, counter) each element
        """
        # To Unix epoch
        sinceInt = int(time.mktime(since.timetuple()))
        toInt = int(time.mktime(to.timetuple()))

        return StatsCounters.get_grouped(
            ownerType,
            counterType,
            owner_id=ownerIds,
            since=sinceInt,
            to=toInt,
            interval=interval,
            max_intervals=max_intervals,
            limit=limit,
            use_max=use_max,
        )

    def get_accumulated_counters(
        self,
        intervalType: StatsCountersAccum.IntervalType,
        counterType: types.stats.CounterType,
        owner_type: typing.Optional[types.stats.CounterOwnerType] = None,
        owner_id: typing.Optional[int] = None,
        since: typing.Optional[typing.Union[datetime.datetime, int]] = None,
        points: typing.Optional[int] = None,
    ) -> typing.Generator[AccumStat, None, None]:
        if since is None:
            if points is None:
                points = 100  # If since is not specified, we need at least points, get a default
            since = sql_now() - datetime.timedelta(seconds=intervalType.seconds() * points)

        if isinstance(since, datetime.datetime):
            since = int(since.timestamp())

        # Filter from since to now, get at most points
        query = StatsCountersAccum.objects.filter(
            interval_type=intervalType,
            counter_type=counterType,
            stamp__gte=since,
        ).order_by('stamp')[0:points]
        if owner_type is not None:
            query = query.filter(owner_type=owner_type)
        if owner_id is not None:
            query = query.filter(owner_id=owner_id)

        # Yields all data, stamp, n, sum, max, min (stamp, v_count,v_sum,v_max,v_min)
        # Now, get exactly the points we need
        stamp = since
        last = AccumStat(stamp, 0, 0, 0, 0)
        for rec in query:
            # While query stamp is greater than stamp, repeat last AccumStat
            while rec.stamp > stamp:
                # Yield last value until we reach the record
                yield last
                stamp += intervalType.seconds()
                last.stamp = stamp
            # The record to be emmitted is the current one, but replace record stamp with current stamp
            # The recor is for sure the first one previous to stamp (we have emmited last record until we reach this one)
            last = AccumStat(
                stamp,
                rec.v_count,
                rec.v_sum,
                rec.v_max,
                rec.v_min,
            )
            # Append to numpy array
            yield last
            stamp += intervalType.seconds()

    def perform_counters_maintenance(self) -> None:
        """
        Removes all counters previous to configured max keep time for stat information from database.
        """
        self._do_maintanance(StatsCounters)
        self._do_maintanance(StatsCountersAccum)

    def get_event_field_for(self, fld: str) -> str:
        '''
        Get equivalency between "cool names" and field. Will raise "KeyError" if no equivalency
        '''
        return _REVERSE_FLDS_EQUIV[fld]

    # Event stats
    def add_event(
        self, owner_type: types.stats.EventOwnerType, owner_id: int, event_type: types.stats.EventType, **kwargs: typing.Any
    ) -> bool:
        """
        Adds a new event stat to database.

        stamp=None, fld1=None, fld2=None, fld3=None
        Args:

            toWhat: if of the counter
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:

            Nothing
        """
        logger.debug('Adding event stat')
        stamp = kwargs.get('stamp')
        if stamp is None:
            stamp = sql_stamp_seconds()
        else:
            # To Unix epoch
            stamp = int(time.mktime(stamp.timetuple()))  # pylint: disable=maybe-no-member

        try:

            def get_kwarg(fld: str) -> str:
                SENTINEL: typing.Final = object()
                val = kwargs.get(fld, SENTINEL)
                if val is SENTINEL and fld in _FLDS_EQUIV:
                    for i in _FLDS_EQUIV[fld]:
                        val = kwargs.get(i, SENTINEL)
                        if val is not SENTINEL:
                            break
                return val or ''

            fld1 = get_kwarg('fld1')
            fld2 = get_kwarg('fld2')
            fld3 = get_kwarg('fld3')
            fld4 = get_kwarg('fld4')

            StatsEvents.objects.create(
                owner_type=owner_type,
                owner_id=owner_id,
                event_type=event_type,
                stamp=stamp,
                fld1=fld1,
                fld2=fld2,
                fld3=fld3,
                fld4=fld4,
            )
            return True
        except Exception:
            logger.exception('Exception handling event stats saving (maybe database is full?)')
        return False

    def enumerate_events(
        self,
        owner_type: typing.Union[
            types.stats.EventOwnerType, collections.abc.Iterable[types.stats.EventOwnerType]
        ],
        event_type: typing.Union[types.stats.EventType, collections.abc.Iterable[types.stats.EventType]],
        **kwargs: typing.Any,
    ) -> 'models.QuerySet[StatsEvents]':
        """
        Retrieves counters from item

        Args:

            ownerType: Type of counter to get values
            eventType:
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified

        Returns:

            Iterator, containing (date, counter) each element
        """
        return StatsEvents.enumerate_stats(owner_type, event_type, **kwargs)

    def tail_events(
        self, *, starting_id: typing.Optional[str] = None, number: typing.Optional[int] = None
    ) -> 'models.QuerySet[StatsEvents]':
        # If number is not specified, we return five last events
        number = number or 5
        if starting_id:
            return StatsEvents.objects.filter(id__gt=starting_id).order_by('-id')[:number]
        return StatsEvents.objects.order_by('-id')[:number]

    def perform_events_maintenancecleanupEvents(self) -> None:
        """
        Removes all events previous to configured max keep time for stat information from database.
        """

        self._do_maintanance(StatsEvents)

    def acummulate(self, max_days: int = 7) -> None:
        for interval in StatsCountersAccum.IntervalType:
            StatsCountersAccum.acummulate(interval, max_days)
