# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

__updated__ = '2015-09-17'

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _, ugettext
from dateutil import rrule as rules

from .UUIDModel import UUIDModel
from .Calendar import Calendar
from .Util import getSqlDatetime

import datetime
import logging

logger = logging.getLogger(__name__)

WEEKDAYS = 'WEEKDAYS'

# Frequencies
freqs = (("YEARLY", _("Yearly")),
         ("MONTHLY", _("Monthly")),
         ("WEEKLY", _("Weekly")),
         ("DAILY", _("Daily")),
         (WEEKDAYS, _("Weekdays")))

frq_to_rrl = {
    'YEARLY': rules.YEARLY,
    'MONTHLY': rules.MONTHLY,
    'WEEKLY': rules.WEEKLY,
    'DAILY': rules.DAILY,
}

frq_to_mins = {
    'YEARLY': 366 * 24 * 60,
    'MONTHLY': 31 * 24 * 60,
    'WEEKLY': 7 * 24 * 60,
    'DAILY': 24 * 60,
}

weekdays = [rules.SU, rules.MO, rules.TU, rules.WE, rules.TH, rules.FR, rules.SA]


@python_2_unicode_compatible
class CalendarRule(UUIDModel):
    name = models.CharField(max_length=128)
    comments = models.CharField(max_length=256)

    start = models.DateTimeField()
    end = models.DateField(null=True, blank=True)
    frequency = models.CharField(choices=freqs, max_length=32)
    interval = models.IntegerField(default=1)  # If interval is for WEEKDAYS, every bit means a day of week (bit 0 = SUN, 1 = MON, ...)
    duration = models.IntegerField(default=0)  # Duration in minutes

    calendar = models.ForeignKey(Calendar, related_name='rules')

    class Meta:
        '''
        Meta class to declare db table
        '''
        db_table = 'uds_calendar_rules'
        app_label = 'uds'

    def as_rrule(self):
        if self.frequency == WEEKDAYS:
            dw = []
            l = self.interval
            for i in range(7):
                if l & 1 == 1:
                    dw.append(weekdays[i])
                l >>= 1
            return rules.rrule(rules.DAILY, byweekday=dw, dtstart=self.start)
        else:
            return rules.rrule(frq_to_rrl[self.frequency], interval=self.interval, dtstart=self.start)

    def freqInMinutes(self):
        if self.frequency != WEEKDAYS:
            return frq_to_mins.get(self.frequency, 0) * self.interval
        else:
            return 7 * 24 * 60


    def save(self, *args, **kwargs):
        logger.debug('Saving...')
        self.calendar.modified = getSqlDatetime()
        self.calendar.save()

        return UUIDModel.save(self, *args, **kwargs)

    def __str__(self):
        return 'Rule {0}: {1}-{2}, {3}, Interval: {4}, duration: {5}'.format(self.name, self.start, self.end, self.frequency, self.interval, self.duration)
