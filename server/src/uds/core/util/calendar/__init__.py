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

from __future__ import unicode_literals

from uds.models.Util import NEVER
from uds.models.Util import getSqlDatetime

from uds.models.Calendar import Calendar

from uds.core.util.Cache import Cache

import datetime
import six
import bitarray
import logging

__updated__ = '2016-02-17'


logger = logging.getLogger(__name__)


class CalendarChecker(object):
    data = None
    data_time = None
    calendar = None
    inverse = False

    # For performance checking
    updates = 0
    cache_hit = 0
    hits = 0

    cache = Cache('calChecker')

    def __init__(self, calendar, inverse=False):
        self.calendar = calendar
        self.calendar_modified = None
        self.inverse = inverse
        self.data = None
        self.data_time = None

    def _updateData(self, dtime):
        # Else, update the array
        CalendarChecker.updates += 1
        self.calendar_modified = self.calendar.modified
        self.data_time = dtime.date()

        # First, try to get data from cache if it is valid
        cacheKey = six.text_type(self.calendar.modified.toordinal()) + six.text_type(self.data_time.toordinal()) + self.calendar.uuid
        cached = CalendarChecker.cache.get(cacheKey, None)
        if cached is not None:
            self.data = bitarray.bitarray()  # Empty bitarray
            self.data.frombytes(cached)
            CalendarChecker.cache_hit += 1
            return

        self.data = bitarray.bitarray(60 * 24)  # Granurality is minute
        self.data.setall(False)

        start = datetime.datetime.combine(self.data_time, datetime.datetime.min.time())
        end = datetime.datetime.combine(self.data_time, datetime.datetime.max.time())

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
                if val.date() != self.data_time:
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
                self.data[pos:posdur] = True

        # Now self.data can be accessed as an array of booleans.
        # Store data on persistent cache
        CalendarChecker.cache.put(cacheKey, self.data.tobytes(), 3600 * 24)

    def check(self, dtime=None):
        '''
        Checks if the given time is a valid event on calendar
        @param dtime: Datetime object to check
        TODO: We can improve performance of this by getting from a cache first if we can
        '''
        if dtime is None:
            dtime = datetime.datetime.now()
        if self.calendar_modified != self.calendar.modified or self.data is None or self.data_time != dtime.date():
            self._updateData(dtime)
        else:
            CalendarChecker.hits += 1

        return self.data[dtime.hour * 60 + dtime.minute]

    def debug(self):
        if self.data is None:
            self.check()

        return '\n'.join([
            '{1}:{2} is {0}'.format(self.data[i], i / 60, i % 60) for i in range(60 * 24)
        ])
