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

from django.db import models

from uds.models.Util import NEVER_UNIX
from uds.models.Util import getSqlDatetime

import logging

__updated__ = '2015-05-03'


logger = logging.getLogger(__name__)


class StatsEvents(models.Model):
    '''
    Counter statistocs mpdes the counter statistics
    '''

    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)
    event_type = models.SmallIntegerField(db_index=True, default=0)
    stamp = models.IntegerField(db_index=True, default=0)

    # Variable fields, depends on event
    fld1 = models.CharField(max_length=128, default='')
    fld2 = models.CharField(max_length=128, default='')
    fld3 = models.CharField(max_length=128, default='')
    fld4 = models.CharField(max_length=128, default='')

    class Meta:
        '''
        Meta class to declare db table
        '''
        db_table = 'uds_stats_e'
        app_label = 'uds'

    @staticmethod
    def get_stats(owner_type, event_type, **kwargs):
        '''
        Returns the average stats grouped by interval for owner_type and owner_id (optional)

        Note: if someone cant get this more optimized, please, contribute it!
        '''
        fltr = StatsEvents.objects.filter(event_type=event_type)

        if type(owner_type) in (list, tuple):
            fltr = fltr.filter(owner_type__in=owner_type)
        else:
            fltr = fltr.filter(owner_type=owner_type)

        if kwargs.get('owner_id', None) is not None:
            fltr = fltr.filter(owner_id=kwargs['owner_id'])

        since = kwargs.get('since', None)
        to = kwargs.get('to', None)

        since = since and int(since) or NEVER_UNIX
        to = to and int(to) or getSqlDatetime(True)

        fltr = fltr.filter(stamp__gte=since, stamp__lte=to)

        # We use result as an iterator
        return fltr

    @property
    def username(self):
        return self.fld1

    @property
    def srcIp(self):
        return self.fld2

    @property
    def dstIp(self):
        return self.fld3

    @property
    def uniqueId(self):
        return self.fld4

    def __unicode__(self):
        return u"Log of {0}({1}): {2} - {3} - {4}, {5}, {6}".format(self.owner_type, self.owner_id, self.event_type, self.stamp, self.fld1, self.fld2, self.fld3)
