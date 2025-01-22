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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
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
        min_time = time.mktime(
            (sql_now() - datetime.timedelta(days=GlobalConfig.STATS_DURATION.as_int())).timetuple()
        )
        model.objects.filter(stamp__lt=min_time).delete()

    # Counter stats
    def add_counter(
        self,
        owner_type: types.stats.CounterOwnerType,
        owner_id: int,
        counter_type: types.stats.CounterType,
        value: int,
        stamp: typing.Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Adds a new counter stats to database.

        Args:

            owner_type: type of owner (integer, from internal tables)
            owner_id:  id of the owner
            counter_type: The type of counter that will receive the value (look at uds.core.util.stats.counters module)
            value: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
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
                counter_type=counter_type,
                value=value,
                stamp=stampInt,
            )
            return True
        except Exception:
            logger.error('Exception handling counter stats saving (maybe database is full?)')
        return False

    def enumerate_counters(
        self,
        owner_type: int,
        counter_type: int,
        owners_ids: typing.Union[collections.abc.Iterable[int], int, None],
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
            owner_type: Type of counter to get values
            counter_type: Type of counter to get values
            owners_ids: Ids of the owners to get counters from. If None, all owners will be used
            since: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified
            interval: Interval in seconds to get counters. If None, all counters will be returned
            max_intervals: Maximum number of intervals to get. If None, all intervals will be returned
            limit: Maximum number of counters to get. If None, all counters will be returned
            use_max: If True, the maximum value of the counter will be returned instead of the sum

        Returns:
            Iterable, containing (timestamp, counter) each element
        """
        # To Unix epoch
        since_stamp = int(time.mktime(since.timetuple()))
        to_stamp = int(time.mktime(to.timetuple()))

        return StatsCounters.get_grouped(
            owner_type,
            counter_type,
            owner_id=owners_ids,
            since=since_stamp,
            to=to_stamp,
            interval=interval,
            max_intervals=max_intervals,
            limit=limit,
            use_max=use_max,
        )

    def get_accumulated_counters(
        self,
        interval_type: StatsCountersAccum.IntervalType,
        counter_type: types.stats.CounterType,
        owner_type: typing.Optional[types.stats.CounterOwnerType] = None,
        owner_id: typing.Optional[int] = None,
        since: typing.Optional[typing.Union[datetime.datetime, int]] = None,
        to: typing.Optional[typing.Union[datetime.datetime, int]] = None,
        points: typing.Optional[int] = None,
    ) -> typing.Generator[types.stats.AccumStat, None, None]:
        if to is None:
            to = sql_now()
        elif isinstance(to, int):
            to = datetime.datetime.fromtimestamp(to)

        if since is None:
            if points is None:
                points = 100  # If since is not specified, we need at least points, get a default
            since = to - datetime.timedelta(seconds=interval_type.seconds() * points)
        elif isinstance(since, int):
            since = datetime.datetime.fromtimestamp(since)

        # If points has any value, ensure since..to is points long
        if points is not None:
            # Ensure since is at least points long before to
            if (to - since).seconds < interval_type.seconds() * points:
                since = to - datetime.timedelta(seconds=interval_type.seconds() * points)

        since = int(since.replace(minute=0, second=0, microsecond=0).timestamp())
        to = int(to.replace(minute=0, second=0, microsecond=0).timestamp())

        # Filter from since to now, get at most points
        query = StatsCountersAccum.objects.filter(
            interval_type=interval_type,
            counter_type=counter_type,
            stamp__gte=since,
            owner_id=owner_id if owner_id is not None else -1,
        ).order_by('stamp')
        if owner_type is not None:
            query = query.filter(owner_type=owner_type)
        # If points is NONE, we get all data
        query = query[:points]

        # Yields all data, stamp, n, sum, max, min (stamp, v_count,v_sum,v_max,v_min)
        # Now, get exactly the points we need
        
        # Note that empty values were not saved, so we can find "holes" in the data
        # that will be filled with empty values
        
        stamp = since
        for rec in query:
            # While query stamp is greater than stamp, repeat last AccumStat
            while rec.stamp > stamp:
                # No values, return empty
                yield types.stats.AccumStat(stamp, 0, 0, 0, 0)
                stamp += interval_type.seconds()

            # The record to be emmitted is the current one, but replace record stamp with current stamp
            # The recor is for sure the first one previous to stamp (we have emmited last record until we reach this one)
            yield types.stats.AccumStat(
                stamp,
                rec.v_count,
                rec.v_sum,
                rec.v_max,
                rec.v_min,
            )
            stamp += interval_type.seconds()

        while stamp < to:
            yield types.stats.AccumStat(stamp, 0, 0, 0, 0)
            stamp += interval_type.seconds()

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
        self,
        owner_type: types.stats.EventOwnerType,
        owner_id: int,
        event_type: types.stats.EventType,
        stamp: typing.Optional[datetime.datetime] = None,
        **kwargs: str,
    ) -> bool:
        """
        Adds a new event stat to database.

        stamp=None, fld1=None, fld2=None, fld3=None
        Args:
            owner_type: type of owner (integer, from internal tables)
            owner_id:  id of the owner
            event_type: The type of event that will be stored (look at uds.core.util.stats.events module)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get

            kwargs: Additional fields for the event. This will be stored as fld1, fld2, fld3, fld4

        Note: to see fields equivalency, check _FLDS_EQUIV

        Returns:

            Nothing
        """
        logger.debug('Adding event stat')
        if stamp is None:
            stamp_seconds = sql_stamp_seconds()
        else:
            # To Unix epoch
            stamp_seconds = int(time.mktime(stamp.timetuple()))  # pylint: disable=maybe-no-member

        def get_kwarg(fld: str) -> str:
            SENTINEL: typing.Final = object()
            val: 'str|None|object' = kwargs.get(fld, SENTINEL)
            if val is SENTINEL and fld in _FLDS_EQUIV:
                for i in _FLDS_EQUIV[fld]:
                    val = kwargs.get(i, SENTINEL)
                    if val is not SENTINEL:
                        break

            if val is SENTINEL:
                return ''

            return typing.cast('str|None', val) or ''

        fld1 = get_kwarg('fld1')
        fld2 = get_kwarg('fld2')
        fld3 = get_kwarg('fld3')
        fld4 = get_kwarg('fld4')

        try:
            StatsEvents.objects.create(
                owner_type=owner_type,
                owner_id=owner_id,
                event_type=event_type,
                stamp=stamp_seconds,
                fld1=fld1 or '',
                fld2=fld2 or '',
                fld3=fld3 or '',
                fld4=fld4 or '',
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
        owner_id: 'int|collections.abc.Iterable[int]|None' = None,
        since: 'datetime.datetime|int|None' = None,
        to: 'datetime.datetime|int|None' = None,
        limit: int = 0,
    ) -> 'models.QuerySet[StatsEvents]':
        """
        Retrieves counters from item

        Args:

            owner_type: Type of counter to get values
            event_type:
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified

        Returns:

            Iterator, containing (date, counter) each element
        """
        return StatsEvents.enumerate_stats(owner_type, event_type, owner_id, since, to, limit)

    def tail_events(
        self,
        *,
        starting_id: typing.Optional[str] = None,
        number: typing.Optional[int] = None,
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
