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
from uds.core.reports.tools import UDSGeraldoReport, UDSImage
from uds.core.util.stats import counters


import StringIO
import csv


from .base import StatsReport

from uds.core.util import tools
from uds.models import ServicePool
from geraldo.generators.pdf import PDFGenerator
from geraldo import ReportBand, ObjectValue, Label, BAND_WIDTH, SubReport
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

import cairo
import pycha.line
import pycha.bar
import pycha.stackedbar
from PIL import Image as PILImage


import datetime
import logging
import six

logger = logging.getLogger(__name__)

__updated__ = '2017-05-03'

# several constants as Width height, margins, ..
WIDTH, HEIGHT = 1800, 1000
GERALDO_WIDTH = 120 * mm
GERALDO_HEIGHT = GERALDO_WIDTH * HEIGHT / WIDTH


class CountersPoolsReport(UDSGeraldoReport):
    title = ''
    author = 'UDS'

    header_elements = []

    header_height = 2.5 * cm

    class band_detail(ReportBand):
        height = 400 * mm  # Height bigger than a page, so a new page is launched for listings
        elements = (
            Label(text=_('Services Asignation'), top=0.6 * cm, left=0, width=BAND_WIDTH,
                  style={'fontName': 'Helvetica-Bold', 'fontSize': 10, 'alignment': TA_CENTER}),
            UDSImage(left=4 * cm, top=1 * cm,
                     width=GERALDO_WIDTH, height=GERALDO_HEIGHT,
                     get_image=lambda x: x.instance['image']),
        )

    subreports = [
        SubReport(
            queryset_string='%(object)s["data"]',
            band_header=ReportBand(
                height=1 * cm,
                auto_expand_height=True,
                elements=(
                    Label(text=_('Service asignation by hour'), top=0.2 * cm, left=0, width=BAND_WIDTH,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 12, 'alignment': TA_CENTER}),
                    Label(text=_('Pool'), top=1.0 * cm, left=1.2 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 10}),
                    Label(text=_('Hour'), top=1.0 * cm, left=10 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 10}),
                    Label(text=_('Services'), top=1.0 * cm, left=14 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 10}),
                ),
                # borders={'bottom': True}
            ),
            band_detail=ReportBand(
                height=0.5 * cm,
                elements=(
                    ObjectValue(attribute_name='name', top=0, left=1.2 * cm, width=8.8 * cm, style={'fontName': 'Helvetica', 'fontSize': 9}),
                    ObjectValue(attribute_name='time', top=0, left=10 * cm, width=4 * cm, style={'fontName': 'Helvetica', 'fontSize': 9}),
                    ObjectValue(attribute_name='value', top=0, left=14 * cm, width=4 * cm, style={'fontName': 'Helvetica', 'fontSize': 9}),
                )
            ),
        )
    ]



class CountersPoolAssigned(StatsReport):
    filename = 'pools_counters.pdf'
    name = _('Pools usage on a day')  # Report name
    description = _('Pools usage counters for an specific day')  # Report description
    uuid = '0b429f70-2fc6-11e7-9a2a-8fc37101e66a'

    startDate = gui.DateField(
        order=2,
        label=_('Date'),
        tooltip=_('Date for report'),
        defvalue=datetime.date.min,
        required=True
    )

    pools = gui.MultiChoiceField(
        order=1,
        label=_('Pools'),
        tooltip=_('Pools for report'),
        required=True
    )

    def initialize(self, values):
        pass

    def initGui(self):
        logger.debug('Initializing gui')
        vals = [
            gui.choiceItem(v.uuid, v.name) for v in ServicePool.objects.all()
        ]
        self.pools.setValues(vals)

    def getData(self):
        # Generate the sampling intervals and get dataUsers from db
        start = self.startDate.date()
        end = self.startDate.date() + datetime.timedelta(days=1)

        data = []

        for poolUuid in self.pools.value:
            try:
                pool = ServicePool.objects.get(uuid=poolUuid)
            except Exception:
                pass  # Ignore pool

            hours = {}
            for i in range(24):
                hours[i] = 0

            for x in counters.getCounters(pool, counters.CT_ASSIGNED, since=start, to=end, limit=24, use_max=True, all=False):
                hour = x[0].hour
                val = int(x[1])
                if hours[hour] < val:
                    hours[hour] = val

            data.append({'uuid':pool.uuid, 'name': pool.name, 'hours': hours})


        logger.debug('data: {}'.format(data))

        return data

    def generate(self):
        items = self.getData()

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)  # @UndefinedVariable

        options = {
            'encoding': 'utf-8',
            'axis': {
                'x': {
                    'ticks': [
                        dict(v=i, label='{:02d}'.format(i)) for i in range(24)
                    ],
                    'range': (0, 23),
                    'showLines': True,
                },
                'y': {
                    'tickCount': 10,
                    'showLines': True,
                },
                'tickFontSize': 16,
            },
            'background': {
                'chartColor': '#f0f0f0',
                'baseColor': '#f0f0f0',
                'lineColor': '#187FF2'
            },
            'colorScheme': {
                'name': 'rainbow',
                'args': {
                    'initialColor': 'blue',
                },
            },
            'legend': {
                'hide': False,
                'legendFontSize': 16,
                'position': {
                    'left': 96,
                    'top': 40,
                }
            },
            'padding': {
                'left': 48,
                'top': 16,
                'right': 48,
                'bottom': 48,
            },
            'title': _('Services by hour'),
        }

        # chart = pycha.line.LineChart(surface, options)
        # chart = pycha.bar.VerticalBarChart(surface, options)
        chart = pycha.stackedbar.StackedVerticalBarChart(surface, options)

        dataset = []
        for pool in items:
            logger.debug(pool['hours'])
            ds = list((i, pool['hours'][i]) for i in range(24))
            logger.debug(ds)
            dataset.append((ugettext('Services for {}').format(pool['name']), ds))

        logger.debug('Dataset: {}'.format(dataset))
        chart.addDataset(dataset)

        chart.render()

        img = PILImage.frombuffer("RGBA", (surface.get_width(), surface.get_height()), surface.get_data(), "raw", "BGRA", 0, 1)


        output = StringIO.StringIO()

        # Regenerate data

        # Generate data
        data = []
        for i in items:
            for j in range(24):
                data.append({'name': i['name'], 'time': '{:02d}'.format(j), 'value': i['hours'][j]})

        report = CountersPoolsReport(queryset=[{'data': data, 'image': img}])
        report.title = six.text_type(_('Services usage report'))
        report.generate_by(PDFGenerator, filename=output)
        return output.getvalue()


class CountersPoolAssignedCSV(CountersPoolAssigned):
    filename = 'pools_counters.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '1491148a-2fc6-11e7-a5ad-03d9a417561c'
    encoded = False

    # Input fields
    startDate = CountersPoolAssigned.startDate
    pools = CountersPoolAssigned.pools

    def generate(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)
        writer.writerow([ugettext('Pool'), ugettext('Hour'), ugettext('Services')])

        items = self.getData()

        for i in items:
            for j in range(24):
                writer.writerow([i['name'], '{:02d}'.format(j), i['hours'][j]])

        return output.getvalue()
