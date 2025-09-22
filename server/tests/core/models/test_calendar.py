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
import datetime
import logging

from django.utils import timezone

from uds import models
from uds.models.calendar_rule import  FrequencyInfo, DurationInfo
#FREQ_NAMES, dunits, WEEKDAYS_LIST
from ...utils.test import UDSTestCase

if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

FREQ_NAMES: typing.Final[list[str]] = [i.name for i in FrequencyInfo]
DURATION_UNITS: typing.Final[list[str]] = [i.name for i in DurationInfo]

class ModelCalendarTest(UDSTestCase):
    def test_calendar(self) -> None:
        # Ensure we can create some calendars
        for i in range(32):
            calendar = models.Calendar.objects.create(
                name='Test Calendar' + str(i),
                comments='Test Calendar Comments' + str(i),
            )

        # Ensure that calendars exists on DB
        self.assertEqual(models.Calendar.objects.count(), 32)

        # Ensure that all calendars are emtpy
        for calendar in models.Calendar.objects.all():
            self.assertEqual(calendar.rules.all().count(), 0)

        # Ensure that we can add rules to calendars
        # random, no test is done here
        for calendar in models.Calendar.objects.all():
            for i in range(32):
                calendar.rules.create(
                    name=str(i),
                    comments='Test Rule Comments' + str(i),
                    start=timezone.make_aware(datetime.datetime(2009+i, (i%12)+1, (i%28)+1, (i%24), (i%60))),
                    end=datetime.date(2010+i, (i%12)+1, (i%28)+1),
                    frequency=FREQ_NAMES[i%len(FREQ_NAMES)],
                    interval=1,
                    duration=i,
                    duration_unit=DURATION_UNITS[i%len(DURATION_UNITS)],
                )
            # Also add a weekday interval
            calendar.rules.create(
                name='Test Rule Weekday',
                comments='Test Rule Comments Weekday',
                start=timezone.make_aware(datetime.datetime(2009, 1, 1, 0, 0)),
                end=timezone.make_aware(datetime.datetime(2010, 1, 1, 0, 0)),
                frequency='WEEKLY',
                interval=0b1111111,  # Every bit is set, so every day, first (LSB) bit is sunday
                duration=1,
                duration_unit='WEEKS',
            )

        # Ensure that all calendars have rules
        # and the rules are correct
        for calendar in models.Calendar.objects.all():
            self.assertEqual(calendar.rules.all().count(), 33)
            for rule in calendar.rules.all():
                try:
                    i = int(rule.name)
                except ValueError: # Weekday rule
                    continue
                self.assertEqual(rule.comments, 'Test Rule Comments' + str(i))
                self.assertEqual(rule.start, timezone.make_aware(datetime.datetime(2009+i, (i%12)+1, (i%28)+1, (i%24), (i%60))))
                self.assertEqual(rule.end, datetime.date(2010+i, (i%12)+1, (i%28)+1))
                self.assertEqual(rule.frequency, FREQ_NAMES[i%len(FREQ_NAMES)])
                self.assertEqual(rule.interval, 1)
                self.assertEqual(rule.duration, i)
                self.assertEqual(rule.duration_unit, DURATION_UNITS[i%len(DURATION_UNITS)])

