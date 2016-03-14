# -*- coding: utf-8 -*-

#
# Copyright (c) 2015 Virtual Cable S.L.
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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
# pylint: disable=maybe-no-member
from __future__ import unicode_literals

from uds.models.Util import NEVER
from uds.models.Util import getSqlDatetime

from uds.models.Calendar import Calendar

from uds.core.util.Cache import Cache

import datetime
import six
import bitarray
import logging

__updated__ = '2016-03-14'


logger = logging.getLogger(__name__)


class CalendarChecker(object):
    calendar = None

    # For performance checking
    updates = 0
    cache_hit = 0
    hits = 0

    cache = Cache('calChecker')

    def __init__(self, calendar):
        self.calendar = calendar

    def _updateData(self, dtime):
        # Else, update the array
        CalendarChecker.updates += 1

        data = bitarray.bitarray(60 * 24)  # Granurality is minute
        data.setall(False)

        data_date = dtime.date()

        start = datetime.datetime.combine(data_date, datetime.datetime.min.time())
        end = datetime.datetime.combine(data_date, datetime.datetime.max.time())

        for rule in self.calendar.rules.all():
            rr = rule.as_rrule()

            r_end = datetime.datetime.combine(rule.end, datetime.datetime.max.time()) if rule.end is not None else None

            ruleDurationMinutes = rule.duration_as_minutes
            ruleFrequencyMinutes = rule.frequency_as_minutes

            ruleDurationMinutes = ruleDurationMinutes
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


    def _updateEvents(self, checkFrom, startEvent=True):

        next_event = None
        for rule in self.calendar.rules.all():
            if startEvent:
                event = rule.as_rrule().after(checkFrom)  # At start
            else:
                event = rule.as_rrule_end().after(checkFrom)  # At end

            if next_event is None or next_event > event:
                next_event = event

        return next_event

    def check(self, dtime=None):
        '''
        Checks if the given time is a valid event on calendar
        @param dtime: Datetime object to check
        TODO: We can improve performance of this by getting from a cache first if we can
        '''
        if dtime is None:
            dtime = getSqlDatetime()

        # First, try to get data from cache if it is valid
        cacheKey = six.text_type(self.calendar.modified.toordinal()) + six.text_type(dtime.date().toordinal()) + self.calendar.uuid + 'checker'
        cached = CalendarChecker.cache.get(cacheKey, None)

        if cached is not None:
            data = bitarray.bitarray()  # Empty bitarray
            data.frombytes(cached)
            CalendarChecker.cache_hit += 1
        else:
            data = self._updateData(dtime)

            # Now data can be accessed as an array of booleans.
            # Store data on persistent cache
            CalendarChecker.cache.put(cacheKey, data.tobytes(), 3600 * 24)

        return data[dtime.hour * 60 + dtime.minute]

    def nextEvent(self, checkFrom=None, startEvent=True):
        '''
        Returns next event for this interval
        Returns a list of two elements. First is datetime of event begining, second is timedelta of duration
        '''
        if checkFrom is None:
            checkFrom = getSqlDatetime()

        cacheKey = six.text_type(self.calendar.modified.toordinal()) + self.calendar.uuid + six.text_type(checkFrom.toordinal()) + 'event' + ('x' if startEvent is True else '_')
        print cacheKey
        next_event = CalendarChecker.cache.get(cacheKey, None)
        print next_event
        if next_event is None:
            next_event = self._updateEvents(checkFrom, startEvent)
            CalendarChecker.cache.put(cacheKey, next_event, 3600)
        else:
            CalendarChecker.hits += 1

        return next_event


    def debug(self):

        return "Calendar checker for {}".format(self.calendar)
