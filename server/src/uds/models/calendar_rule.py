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

import dataclasses
import datetime
import enum
import logging
import typing

from django.db import models
from django.utils.translation import gettext_lazy as _
from dateutil import rrule as rules

from .uuid_model import UUIDModel
from .calendar import Calendar
from ..core.util.model import sql_now


logger = logging.getLogger(__name__)

@dataclasses.dataclass(frozen=True)
class _FrequencyData:
    title: str
    rule: int
    minutes: int


class FrequencyInfo(enum.Enum):
    YEARLY = _FrequencyData(_('Yearly'), rules.YEARLY, 366 * 24 * 60)
    MONTHLY = _FrequencyData(_('Monthly'), rules.MONTHLY, 31 * 24 * 60)
    WEEKLY = _FrequencyData(_('Weekly'), rules.WEEKLY, 7 * 24 * 60)
    DAILY = _FrequencyData(_('Daily'), rules.DAILY, 24 * 60)
    WEEKDAYS = _FrequencyData(_('Weekdays'), -1, 7 * 24 * 60)
    NEVER = _FrequencyData(
        _('Never'), rules.YEARLY, 1000 * 1000 * 24 * 60
    )  # Very high interval, so it never repeats

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def as_choices() -> tuple[tuple[str, str], ...]:
        return tuple((str(f.name), str(f.value.title)) for f in FrequencyInfo)

    @staticmethod
    def from_str(value: str) -> 'FrequencyInfo':
        try:
            return FrequencyInfo[value]
        except KeyError:
            return FrequencyInfo.YEARLY


@dataclasses.dataclass
class _DurationData:
    title: str
    minutes: int


class DurationInfo(enum.Enum):
    MINUTES = _DurationData(_('Minutes'), 1)
    HOURS = _DurationData(_('Hours'), 60)
    DAYS = _DurationData(_('Days'), 60 * 24)
    WEEKS = _DurationData(_('Weeks'), 60 * 24 * 7)

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def as_choices() -> tuple[tuple[str, str], ...]:
        return tuple((str(f.name), str(f.value.title)) for f in DurationInfo)

    @staticmethod
    def from_str(value: str) -> 'DurationInfo':
        try:
            return DurationInfo[value]
        except KeyError:
            return DurationInfo.MINUTES


WEEKDAYS_LIST: typing.Final[tuple[rules.weekday, ...]] = (
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
    frequency = models.CharField(choices=FrequencyInfo.as_choices(), max_length=32)
    interval = models.IntegerField(
        default=1
    )  # If interval is for WEEKDAYS, every bit means a day of week (bit 0 = SUN, 1 = MON, ...)
    duration = models.IntegerField(default=0)  # Duration in "duration_unit" units
    duration_unit = models.CharField(choices=DurationInfo.as_choices(), default='MINUTES', max_length=32)

    calendar = models.ForeignKey(Calendar, related_name='rules', on_delete=models.CASCADE)

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        db_table = 'uds_calendar_rules'
        app_label = 'uds'

    def _rrule(self, at_end_of_interval: bool) -> rules.rrule:
        if self.interval == 0:  # Fix 0 duration intervals
            self.interval = 1

        end = datetime.datetime.combine(
            self.end if self.end else datetime.datetime.max.date(),
            datetime.datetime.max.time(),
        )

        # If at end of interval is requested, displace dstart to match end of interval
        dstart = (
            self.start
            if not at_end_of_interval
            else self.start + datetime.timedelta(minutes=self.duration_as_minutes)
        )

        if self.frequency == str(FrequencyInfo.WEEKDAYS):
            dw = [WEEKDAYS_LIST[i] for i in range(7) if self.interval & (1 << i) != 0]
            return rules.rrule(rules.DAILY, byweekday=dw, dtstart=dstart, until=end)
        if self.frequency == str(FrequencyInfo.NEVER):  # do not repeat
            return rules.rrule(
                rules.YEARLY, interval=1000, dtstart=dstart, until=dstart + datetime.timedelta(days=1)
            )
        return rules.rrule(
            FrequencyInfo.from_str(self.frequency).value.rule,
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
        return FrequencyInfo.from_str(self.frequency).value.minutes

    @property
    def duration_as_minutes(self) -> int:
        return DurationInfo.from_str(self.duration_unit).value.minutes * self.duration

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        logger.debug('Saving...')
        self.calendar.modified = sql_now()

        super().save(*args, **kwargs)
        # Ensure saves associated calendar, so next execution of actions is updated with rule values
        self.calendar.save()

    def __str__(self) -> str:
        return f'Rule {self.name}: {self.start}-{self.end}, {self.frequency}, Interval: {self.interval}, duration: {self.duration}'
