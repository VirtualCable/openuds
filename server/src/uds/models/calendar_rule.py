# -*- coding: utf-8 -*-

#
# Copyright (c) 2016-2023 Virtual Cable S.L.
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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 'AS IS'
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
import logging
import typing
import collections.abc

from django.db import models
from django.utils.translation import gettext_lazy as _
from dateutil import rrule as rules

from .uuid_model import UUIDModel
from .calendar import Calendar
from ..core.util.model import sql_datetime


logger = logging.getLogger(__name__)

WEEKDAYS: typing.Final[str] = 'WEEKDAYS'
NEVER: typing.Final[str] = 'NEVER'

# Frequencies
freqs: tuple[tuple[str, str], ...] = (
    ('YEARLY', typing.cast(str, _('Yearly'))),
    ('MONTHLY', typing.cast(str, _('Monthly'))),
    ('WEEKLY', typing.cast(str, _('Weekly'))),
    ('DAILY', typing.cast(str, _('Daily'))),
    (WEEKDAYS, typing.cast(str, _('Weekdays'))),
    (NEVER, typing.cast(str, _('Never'))),
)

frq_to_rrl: collections.abc.Mapping[str, int] = {
    'YEARLY': rules.YEARLY,
    'MONTHLY': rules.MONTHLY,
    'WEEKLY': rules.WEEKLY,
    'DAILY': rules.DAILY,
    'NEVER': rules.YEARLY,
}

frq_to_mins: collections.abc.Mapping[str, int] = {
    'YEARLY': 366 * 24 * 60,
    'MONTHLY': 31 * 24 * 60,
    'WEEKLY': 7 * 24 * 60,
    'DAILY': 24 * 60,
    'NEVER': 1000* 1000 * 24 * 60,
}

dunits: tuple[tuple[str, str], ...] = (
    ('MINUTES', _('Minutes')),
    ('HOURS', _('Hours')),
    ('DAYS', _('Days')),
    ('WEEKS', _('Weeks')),
)

dunit_to_mins: collections.abc.Mapping[str, int] = {
    'MINUTES': 1,
    'HOURS': 60,
    'DAYS': 60 * 24,
    'WEEKS': 60 * 24 * 7,
}

weekdays: tuple[rules.weekday, ...] = (
    rules.SU,
    rules.MO,
    rules.TU,
    rules.WE,
    rules.TH,
    rules.FR,
    rules.SA,
)


# pylint: disable=no-member  # For some reason, pylint does not properly detect the ForeignKey, etc..
class CalendarRule(UUIDModel):
    name = models.CharField(max_length=128)
    comments = models.CharField(max_length=256)

    start = models.DateTimeField()
    end = models.DateField(null=True, blank=True)
    frequency = models.CharField(choices=freqs, max_length=32)
    interval = models.IntegerField(
        default=1
    )  # If interval is for WEEKDAYS, every bit means a day of week (bit 0 = SUN, 1 = MON, ...)
    duration = models.IntegerField(default=0)  # Duration in "duration_unit" units
    duration_unit = models.CharField(choices=dunits, default='MINUTES', max_length=32)

    calendar = models.ForeignKey(
        Calendar, related_name='rules', on_delete=models.CASCADE
    )

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare db table
        """

        db_table = 'uds_calendar_rules'
        app_label = 'uds'

    def _rrule(self, atEnd: bool) -> rules.rrule:
        if self.interval == 0:  # Fix 0 intervals
            self.interval = 1

        end = datetime.datetime.combine(
            self.end if self.end else datetime.datetime.max.date(),
            datetime.datetime.max.time(),
        )

        # If at end of interval is requested, displace dstart to match end of interval
        dstart = self.start if not atEnd else self.start + datetime.timedelta(minutes=self.duration_as_minutes)

        if self.frequency == WEEKDAYS:
            dw = []
            l = self.interval
            for i in range(7):
                if l & 1 == 1:
                    dw.append(weekdays[i])
                l >>= 1
            return rules.rrule(rules.DAILY, byweekday=dw, dtstart=dstart, until=end)
        if self.frequency == NEVER:  # do not repeat
            return rules.rrule(rules.YEARLY, interval=1000, dtstart=dstart, until=dstart+datetime.timedelta(days=1))
        return rules.rrule(
            frq_to_rrl[self.frequency],
            interval=self.interval,
            dtstart=dstart,
            until=end,
        )

    def as_rrule(self) -> rules.rrule:
        return self._rrule(False)

    def as_rrule_end(self) -> rules.rrule:
        return self._rrule(True)

    @property
    def frequency_as_minutes(self) -> int:
        if self.frequency != WEEKDAYS:
            return frq_to_mins.get(self.frequency, 0) * self.interval
        return 7 * 24 * 60

    @property
    def duration_as_minutes(self) -> int:
        return dunit_to_mins.get(self.duration_unit, 1) * self.duration

    def save(self, *args, **kwargs):
        logger.debug('Saving...')
        self.calendar.modified = sql_datetime()

        res = super().save(*args, **kwargs)
        # Ensure saves associated calendar, so next execution of actions is updated with rule values
        self.calendar.save()
        return res

    def __str__(self):
        return f'Rule {self.name}: {self.start}-{self.end}, {self.frequency}, Interval: {self.interval}, duration: {self.duration}'
