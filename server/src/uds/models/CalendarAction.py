# -*- coding: utf-8 -*-

# Model based on https://github.com/llazzaro/django-scheduler
#
# Copyright (c) 2016 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""

from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from django.db import models
from uds.models.Calendar import Calendar
from uds.models.UUIDModel import UUIDModel
from uds.models.Util import NEVER, getSqlDatetime
from uds.core.util import calendar
from uds.models.ServicesPool import ServicePool
from django.utils.encoding import python_2_unicode_compatible
# from django.utils.translation import ugettext_lazy as _, ugettext

import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Current posible actions
# Each line describes:
#
CALENDAR_ACTION_PUBLISH = {'id' : 'PUBLISH', 'description': _('Publish'), 'params': ()}
CALENDAR_ACTION_CACHE_L1 = {'id': 'CACHEL1', 'description': _('Set cache size'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Cache size'), 'default': '1'},) }
CALENDAR_ACTION_CACHE_L2 = {'id': 'CACHEL2', 'description': _('Set L2 cache size'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Cache L2 size'), 'default': '1'},)}
CALENDAR_ACTION_INITIAL = {'id': 'INITIAL', 'description': _('Set initial services'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Initial services'), 'default': '1'},)}
CALENDAR_ACTION_MAX = {'id': 'MAX', 'description': _('Set maximum number of services'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Maximum services'), 'default': '10'},)}

CALENDAR_ACTION_DICT = dict(list((c['id'], c) for c in (
    CALENDAR_ACTION_PUBLISH, CALENDAR_ACTION_CACHE_L1,
    CALENDAR_ACTION_CACHE_L2, CALENDAR_ACTION_INITIAL, CALENDAR_ACTION_MAX
)))


@python_2_unicode_compatible
class CalendarAction(UUIDModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    service_pool = models.ForeignKey(ServicePool, on_delete=models.CASCADE)
    action = models.CharField(max_length=64, default='')
    at_start = models.BooleanField(default=False)  # If false, action is done at end of event
    events_offset = models.IntegerField(default=0)  # In minutes
    params = models.CharField(max_length=1024, default='')
    # Not to be edited, just to be used as indicators for executions
    last_execution = models.DateTimeField(default=None, db_index=True, null=True, blank=True)
    next_execution = models.DateTimeField(default=None, db_index=True, null=True, blank=True)

    class Meta:
        """
        Meta class to declare db table
        """
        db_table = 'uds_cal_action'
        app_label = 'uds'

    @property
    def offset(self):
        return datetime.timedelta(minutes=self.events_offset)

    def execute(self, save=True):
        logger.debug('Executing action')
        self.last_execution = getSqlDatetime()
        params = json.loads(self.params)

        saveServicePool = save

        if CALENDAR_ACTION_CACHE_L1['id'] == self.action:
            self.service_pool.cache_l1_srvs = int(params['size'])
        elif CALENDAR_ACTION_CACHE_L2['id'] == self.action:
            self.service_pool.cache_l1_srvs = int(params['size'])
        elif CALENDAR_ACTION_INITIAL['id'] == self.action:
            self.service_pool.initial_srvs = int(params['size'])
        elif CALENDAR_ACTION_MAX['id'] == self.action:
            self.service_pool.max_srvs = int(params['size'])
        elif CALENDAR_ACTION_PUBLISH['id'] == self.action:
            self.service_pool.publish(changeLog='Scheduled publication action')
            saveServicePool = False

        # On save, will regenerate nextExecution
        if save:
            self.save()

        if saveServicePool:
            self.service_pool.save()

    def save(self, *args, **kwargs):
        self.next_execution = calendar.CalendarChecker(self.calendar).nextEvent(checkFrom=self.last_execution, startEvent=self.at_start, offset=self.offset)

        return UUIDModel.save(self, *args, **kwargs)

    def __str__(self):
        return 'Calendar of {}, last_execution = {}, next execution = {}, action = {}, params = {}'.format(
            self.service_pool.name, self.last_execution, self.next_execution, self.action, self.params
        )
