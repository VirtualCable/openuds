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
import random

from uds import models
from uds.models.calendar_rule import freqs, dunits

# Counters so we can reinvoke the same method and generate new data
glob = {
    'calendar_id': 1,
    'calendar_rule_id': 1,
}

def createCalendars(number: int) -> typing.List[models.Calendar]:
    """
    Creates some testing calendars
    """
    calendars: typing.List[models.Calendar] = []
    for i in range(number):
        calendar = models.Calendar.objects.create(
            name='Calendar {}'.format(glob['calendar_id']),
            comments='Calendar {} comments'.format(glob['calendar_id']),
        )
        calendars.append(calendar)
        glob['calendar_id'] += 1
    return calendars


def createRules(number: int, calendar: models.Calendar) -> typing.List[models.CalendarRule]:
    """
    Creates some testing rules associated to a calendar
    """
    rules: typing.List[models.CalendarRule] = []
    rnd = random.Random()  # nosec: testing purposes
    for i in range(number):
        # All rules will start now
        # Rules duration will be a random between 1 and 10 days
        # freqs a random value from freqs
        # interval is a random value between 1 and 10
        # duration is a random value between 0 and 24
        # duration_unit is a random from dunits
        start = datetime.datetime.now()
        end = start + datetime.timedelta(days=rnd.randint(1, 10))
        freq = rnd.choice(freqs)
        interval = rnd.randint(1, 10)
        duration = rnd.randint(0, 24)
        duration_unit = rnd.choice(dunits)

        rule = models.CalendarRule.objects.create(
            calendar=calendar,
            name='Rule {}'.format(glob['calendar_rule_id']),
            comments='Rule {} comments'.format(glob['calendar_rule_id']),
            start=start,
            end=end,
            freq=freq,
            interval=interval,
            duration=duration,
            duration_unit=duration_unit,
        )
        rules.append(rule)
        glob['calendar_rule_id'] += 1

    return rules