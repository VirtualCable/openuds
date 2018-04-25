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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import ugettext, ugettext_lazy as _

from uds.core.ui.UserInterface import gui
from uds.core.util.stats import events

import six
import csv

from .base import StatsReport

from uds.models import ServicePool

import datetime
import logging

logger = logging.getLogger(__name__)

__updated__ = '2018-04-25'


class UsageByPool(StatsReport):
    filename = 'pools_usage.pdf'
    name = _('Pools usage by users')  # Report name
    description = _('Pools usage by user report')  # Report description
    uuid = '38ec12dc-beaf-11e5-bd0a-10feed05884b'

    # Input fields
    pool = gui.ChoiceField(
        order=1,
        label=_('Pool'),
        tooltip=_('Pool for report'),
        required=True
    )

    startDate = gui.DateField(
        order=2,
        label=_('Starting date'),
        tooltip=_('starting date for report'),
        defvalue=datetime.date.min,
        required=True
    )

    endDate = gui.DateField(
        order=3,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        defvalue=datetime.date.max,
        required=True
    )

    def initialize(self, values):
        pass

    def initGui(self):
        logger.debug('Initializing gui')
        vals = [
            gui.choiceItem(v.uuid, v.name) for v in ServicePool.objects.all()
        ]
        self.pool.setValues(vals)

    def getData(self):
        # Generate the sampling intervals and get dataUsers from db
        start = self.startDate.stamp()
        end = self.endDate.stamp()
        logger.debug(self.pool.value)
        pool = ServicePool.objects.get(uuid=self.pool.value)

        items = events.statsManager().getEvents(events.OT_DEPLOYED, (events.ET_LOGIN, events.ET_LOGOUT), owner_id=pool.id, since=start, to=end).order_by('stamp')

        logins = {}
        data = []
        for i in items:
            # if '\\' in i.fld1:
            #    continue

            if i.event_type == events.ET_LOGIN:
                logins[i.fld4] = i.stamp
            else:
                if i.fld4 in logins:
                    stamp = logins[i.fld4]
                    del logins[i.fld4]
                    total = i.stamp - stamp
                    data.append({
                        'name': i.fld4,
                        'date': datetime.datetime.fromtimestamp(stamp),
                        'time': total
                    })

        logger.debug('data: {}'.format(data))

        return data, pool.name

    def generate(self):
        items, poolName = self.getData()

        return self.templateAsPDF(
            'uds/reports/stats/usage-by-pool.html',
            dct={
                'data': items,
                'pool': poolName,
            },
            header=ugettext('Users usage list for {}').format(poolName),
            water=ugettext('UDS Report of users in {}').format(poolName)
        )


class UsageByPoolCSV(UsageByPool):
    filename = 'usage.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '5f7f0844-beb1-11e5-9a96-10feed05884b'
    encoded = False

    # Input fields
    pool = UsageByPool.pool
    startDate = UsageByPool.startDate
    endDate = UsageByPool.endDate

    def generate(self):
        output = six.StringIO()
        writer = csv.writer(output)

        reportData, poolName = self.getData()

        writer.writerow([ugettext('Date'), ugettext('User'), ugettext('Seconds')])

        for v in reportData:
            writer.writerow([v['date'], v['name'], v['time']])

        return output.getvalue()
