# -*- coding: utf-8 -*-

#
# Copyright (c) 2015-2021 Virtual Cable S.L.U.
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
import datetime
import hashlib
import time
import typing
import collections.abc
import logging

import bitarray

from django.core.cache import caches

from uds.core.util.model import sql_datetime

from uds.models.calendar import Calendar

from uds.core.util.cache import Cache


logger = logging.getLogger(__name__)

ONE_DAY = 3600 * 24


class CalendarChecker:
    __slots__ = ('calendar',)

    calendar: Calendar

    # For performance checking
    updates: typing.ClassVar[int] = 0
    cache_hit: typing.ClassVar[int] = 0
    hits: typing.ClassVar[int] = 0

    cache: typing.ClassVar[Cache] = Cache('calChecker')

    def __init__(self, calendar: Calendar) -> None:
        self.calendar = calendar

    def _updateData(self, dtime: datetime.datetime) -> bitarray.bitarray:
        logger.debug('Updating %s', dtime)
        CalendarChecker.updates += 1

        data = bitarray.bitarray(60 * 24)  # Granurality is minute
        data.setall(False)

        data_date = dtime.date()

        start = datetime.datetime.combine(data_date, datetime.datetime.min.time())
        end = datetime.datetime.combine(data_date, datetime.datetime.max.time())

        for rule in self.calendar.rules.all():
            rr = rule.as_rrule()

            r_end = datetime.datetime.combine(rule.end, datetime.datetime.max.time()) if rule.end else None

            ruleDurationMinutes = rule.duration_as_minutes
            ruleFrequencyMinutes = rule.frequency_as_minutes

            # Skip "bogus" definitions
            if ruleDurationMinutes == 0 or ruleFrequencyMinutes == 0:
                continue

            # Relative start, rrule can "spawn" the days, so we get the start at least the ruleDurationMinutes of rule to see if it "matches"
            # This means, we need the previous matching day to be "executed" so we can get the "actives" correctly
            diff = ruleFrequencyMinutes if ruleFrequencyMinutes > ruleDurationMinutes else ruleDurationMinutes
            _start = (start if start > rule.start else rule.start) - datetime.timedelta(minutes=diff)

            _end = end if r_end is None or end < r_end else r_end

            for val in rr.between(_start, _end, inc=True):
                if val.date() != data_date:
                    diff = int((start - val).total_seconds() / 60)
                    pos = 0
                    posdur = ruleDurationMinutes - diff
                    if posdur <= 0:
                        continue
                else:
                    pos = val.hour * 60 + val.minute
                    posdur = pos + ruleDurationMinutes
                if posdur > 60 * 24:
                    posdur = 60 * 24
                data[pos:posdur] = True

        return data

    def _updateEvents(
        self, checkFrom: datetime.datetime, startEvent: bool = True
    ) -> typing.Optional[datetime.datetime]:
        next_event = None
        for rule in self.calendar.rules.all():
            # logger.debug('RULE: start = {}, checkFrom = {}, end'.format(rule.start.date(), checkFrom.date()))
            if rule.end is not None and rule.end < checkFrom.date():
                continue
            # logger.debug('Rule in check interval...')
            if startEvent:
                event = rule.as_rrule().after(checkFrom)  # At start
            else:
                event = rule.as_rrule_end().after(checkFrom)  # At end

            if event and (next_event is None or next_event > event):
                next_event = event

        return next_event

    def check(self, dtime: typing.Optional[datetime.datetime] = None) -> bool:
        """
        Checks if the given time is a valid event on calendar
        @param dtime: Datetime object to check
        """
        if dtime is None:
            dtime = sql_datetime()

        # memcached access
        memCache = caches['memory']

        # First, try to get data from cache if it is valid
        cacheKey = CalendarChecker._cacheKey(
            str(self.calendar.modified) + str(dtime.date()) + (self.calendar.uuid or '') + 'checker'
        )
        # First, check "local memory cache", and if not found, from DB cache
        cached = memCache.get(cacheKey)
        if not cached:
            cached = CalendarChecker.cache.get(cacheKey, None)
            if cached:
                memCache.set(cacheKey, cached, ONE_DAY)

        if cached:
            data = bitarray.bitarray()  # Empty bitarray
            data.frombytes(cached)
            CalendarChecker.cache_hit += 1
        else:
            data = self._updateData(dtime)

            # Now data can be accessed as an array of booleans.
            # Store data on persistent cache
            CalendarChecker.cache.put(cacheKey, data.tobytes(), ONE_DAY)
            memCache.set(cacheKey, data.tobytes(), ONE_DAY)

        return bool(data[dtime.hour * 60 + dtime.minute])

    def nextEvent(
        self,
        checkFrom: typing.Optional[datetime.datetime] = None,
        startEvent: bool = True,
        offset: typing.Optional[datetime.timedelta] = None,
    ) -> typing.Optional[datetime.datetime]:
        """
        Returns next event for this interval
        """
        logger.debug('Obtaining nextEvent')
        if not checkFrom:
            checkFrom = sql_datetime()

        if not offset:
            offset = datetime.timedelta(minutes=0)

        cacheKey = CalendarChecker._cacheKey(
            str(self.calendar.modified)
            + (self.calendar.uuid or '')
            + str(offset.seconds)
            + str(checkFrom)
            + 'event'
            + ('x' if startEvent else '_')
        )
        next_event: typing.Optional[datetime.datetime] = CalendarChecker.cache.get(cacheKey, None)
        if not next_event:
            logger.debug('Regenerating cached nextEvent')
            next_event = self._updateEvents(
                checkFrom + offset, startEvent
            )  # We substract on checkin, so we can take into account for next execution the "offset" on start & end (just the inverse of current, so we substract it)
            if next_event:
                next_event += offset
            CalendarChecker.cache.put(cacheKey, next_event, 3600)
        else:
            logger.debug('nextEvent cache hit')
            CalendarChecker.hits += 1

        return next_event

    def debug(self) -> str:
        return f'Calendar checker for {self.calendar}'

    @staticmethod
    def _cacheKey(key: str) -> str:
        # Returns a valid cache key for all caching backends (memcached, redis, or whatever)
        # Simple, fastest algorihm is to use md5
        return hashlib.md5(key.encode('utf-8')).hexdigest()  # nosec  simple fast algorithm for cache keys
