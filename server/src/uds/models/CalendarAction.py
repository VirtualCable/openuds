# -*- coding: utf-8 -*-

# Model based on https://github.com/llazzaro/django-scheduler
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

__updated__ = '2016-03-29'

from django.utils.translation import ugettext_lazy as _
from django.db import models
from uds.models.Calendar import Calendar
from uds.models.UUIDModel import UUIDModel
from uds.models.ServicesPool import ServicePool
from django.utils.encoding import python_2_unicode_compatible
# from django.utils.translation import ugettext_lazy as _, ugettext

import logging

logger = logging.getLogger(__name__)

# Current posible actions
# Each line describes:
#
CALENDAR_ACTION_PUBLISH = { 'id' : 'PUBLISH', 'description': _('Publish'), 'params': () }
CALENDAR_ACTION_CACHE_L1 = { 'id': 'CACHEL1', 'description': _('Sets cache size'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Cache size') },) }
CALENDAR_ACTION_CACHE_L2 = { 'id': 'CACHEL2', 'description': _('Sets L2 cache size'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Cache L2 size') },) }
CALENDAR_ACTION_INITIAL = { 'id': 'INITIAL', 'description': _('Set initial services'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Initial services') },) }
CALENDAR_ACTION_MAX = { 'id': 'MAX', 'description': _('Change maximum number of services'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Maximum services') },) }

class CalendarAction(UUIDModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    servicePool = models.ForeignKey(ServicePool, on_delete=models.CASCADE)
    action = models.CharField(max_length=64, default='')
    atStart = models.BooleanField(default=False)  # If false, action is done at end of event
    eventsOffset = models.IntegerField(default=0)  # In minutes
    params = models.CharField(max_length=1024, default='')

    class Meta:
        '''
        Meta class to declare db table
        '''
        db_table = 'uds_cal_action'
        app_label = 'uds'

