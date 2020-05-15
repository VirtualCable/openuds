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

from django.utils.translation import ugettext, ugettext_lazy as _

from uds.core.ui.UserInterface import gui
from uds.core.reports.tools import UDSGeraldoReport
from uds.core.util.stats import events


import StringIO
import csv


from .base import StatsReport

from uds.core.util import tools
from uds.models import ServicePool
from geraldo.generators.pdf import PDFGenerator
from geraldo import ReportBand, ObjectValue, Label
from reportlab.lib.units import cm, mm

import datetime
import logging

logger = logging.getLogger(__name__)

__updated__ = '2016-05-17'

# several constants as Width height, margins, ..
WIDTH, HEIGHT = 1800, 1000
GERALDO_WIDTH = 120 * mm
GERALDO_HEIGHT = GERALDO_WIDTH * HEIGHT / WIDTH


class UsersReport(UDSGeraldoReport):
    title = ''
    author = 'UDS'

    header_elements = [
        Label(text=_('Access Datetime'), top=2.0 * cm, left=0.5 * cm),
        Label(text=_('User'), top=2.0 * cm, left=5.5 * cm),
        Label(text=_('Duration(seconds)'), top=2.0 * cm, left=12 * cm),
    ]

    header_height = 2.5 * cm


    class band_detail(ReportBand):
        height = 0.5 * cm
        elements = (
            ObjectValue(attribute_name='date', left=0.5 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
            ObjectValue(attribute_name='name', left=5.5 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
            ObjectValue(attribute_name='time', left=12 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
        )


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
                        'origin': i.fld2.split(':')[0],  # Gets also origin
                        'date': datetime.datetime.fromtimestamp(stamp),
                        'time': total
                    })

        logger.debug('data')

        return data, pool.name

    def generate(self):
        items, poolName = self.getData()

        output = StringIO.StringIO()

        report = UsersReport(queryset=items)
        report.title = _('Users usage list for {}').format(poolName)
        report.generate_by(PDFGenerator, filename=output)
        return output.getvalue()


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
        output = StringIO.StringIO()
        writer = csv.writer(output)

        reportData, poolName = self.getData()

        writer.writerow([ugettext('Date'), ugettext('User'), ugettext('Seconds'), ugettext('Origin')])

        for v in reportData:
            writer.writerow([v['date'], v['name'], v['time'], v['origin']])

        return output.getvalue()
