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
from django.db.models import Count
import django.template.defaultfilters as filters

from uds.core.ui.UserInterface import gui
from uds.core.reports.tools import UDSImage, UDSGeraldoReport
from uds.core.util.stats import events

import StringIO
import csv

import cairo
import pycha.line
import pycha.bar
import pycha.stackedbar

from .base import StatsReport

from uds.core.util import tools
from uds.models import ServicePool
from geraldo.generators.pdf import PDFGenerator
from geraldo import ReportBand, ObjectValue, BAND_WIDTH, Label, SubReport, SystemField, Line
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib import colors
from PIL import Image as PILImage

import datetime
import logging

logger = logging.getLogger(__name__)

__updated__ = '2017-05-04'

# several constants as Width height, margins, ..
WIDTH, HEIGHT = 1800, 1000
GERALDO_WIDTH = 120 * mm
GERALDO_HEIGHT = GERALDO_WIDTH * HEIGHT / WIDTH


class AccessReport(UDSGeraldoReport):

    header_elements = []

    class band_detail(ReportBand):
        height = 400 * mm  # Height bigger than a page, so a new page is launched for listings
        # auto_expand_height = True
        elements = (
            Label(text=_('Distinct users by pool'), top=0.6 * cm, left=0, width=BAND_WIDTH,
                  style={'fontName': 'Helvetica-Bold', 'fontSize': 10, 'alignment': TA_CENTER}),
            UDSImage(left=4 * cm, top=1 * cm,
                     width=GERALDO_WIDTH, height=GERALDO_HEIGHT,
                     get_image=lambda x: x.instance['image']),

            Label(text=_('Accesses by pool'), top=GERALDO_HEIGHT + 1.2 * cm, left=0, width=BAND_WIDTH,
                  style={'fontName': 'Helvetica-Bold', 'fontSize': 10, 'alignment': TA_CENTER}),
            UDSImage(left=4 * cm, top=GERALDO_HEIGHT + 1.6 * cm,
                     width=GERALDO_WIDTH, height=GERALDO_HEIGHT,
                     get_image=lambda x: x.instance['image2']),
        )

    subreports = [
        SubReport(
            queryset_string='%(object)s["data"]',
            band_header=ReportBand(
                height=1 * cm,
                auto_expand_height=True,
                elements=(
                    # Label(text=_('Users access by date'), top=0.2 * cm, left=0, width=BAND_WIDTH,
                    #      style={'fontName': 'Helvetica-Bold', 'fontSize': 12, 'alignment': TA_CENTER}),

                    Label(text=_('Pool'), top=1.0 * cm, left=1.2 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 9}),
                    Label(text=_('Date range'), top=1.0 * cm, left=8 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 9}),
                    Label(text=_('Users'), top=1.0 * cm, left=14 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 9}),
                    Label(text=_('Accesses'), top=1.0 * cm, left=16 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 9}),
                ),
                # borders={'bottom': True}
            ),
            band_detail=ReportBand(
                height=0.5 * cm,
                elements=(
                    ObjectValue(attribute_name='name', top=0, left=1.2 * cm, width=12 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
                    ObjectValue(attribute_name='date', top=0, left=8 * cm, width=12 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
                    ObjectValue(attribute_name='users', top=0, left=14 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
                    ObjectValue(attribute_name='accesses', top=0, left=16 * cm, style={'fontName': 'Helvetica', 'fontSize': 8}),
                )
            ),
        ),
    ]



class PoolPerformanceReport(StatsReport):
    filename = 'pools_performance.pdf'
    name = _('Pools performance by date')  # Report name
    description = _('Pools performance report by date')  # Report description
    uuid = '88932b48-1fd3-11e5-a776-10feed05884b'

    # Input fields
    pools = gui.MultiChoiceField(
        order=1,
        label=_('Pools'),
        tooltip=_('Pools for report'),
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

    samplingPoints = gui.NumericField(
        order=4,
        label=_('Number of intervals'),
        length=3,
        minValue=0,
        maxValue=32,
        tooltip=_('Number of sampling points used in charts'),
        defvalue='8'
    )

    def initialize(self, values):
        pass

    def initGui(self):
        logger.debug('Initializing gui')
        vals = [
            gui.choiceItem(v.uuid, v.name) for v in ServicePool.objects.all()
        ]
        self.pools.setValues(vals)

    def getRangeData(self):
        start = self.startDate.stamp()
        end = self.endDate.stamp()

        if self.samplingPoints.num() < 2:
            self.samplingPoints.value = (self.endDate.date() - self.startDate.date()).days
        if self.samplingPoints.num() < 2:
            self.samplingPoints.value = 2
        if self.samplingPoints.num() > 32:
            self.samplingPoints.value = 32

        samplingPoints = self.samplingPoints.num()

        pools = [(v.id, v.name) for v in ServicePool.objects.filter(uuid__in=self.pools.value)]
        if len(pools) == 0:
            raise Exception(_('Select at least a service pool for the report'))

        logger.debug('Pools: {}'.format(pools))

        # x axis label format
        if end - start > 3600 * 24 * 2:
            xLabelFormat = 'SHORT_DATE_FORMAT'
        else:
            xLabelFormat = 'SHORT_DATETIME_FORMAT'

        # Generate samplings interval
        samplingIntervals = []
        prevVal = None
        for val in range(start, end, (end - start) / (samplingPoints + 1)):
            if prevVal is None:
                prevVal = val
                continue
            samplingIntervals.append((prevVal, val))
            prevVal = val

        # Store dataUsers for all pools
        poolsData = []

        fld = events.statsManager().getEventFldFor('username')

        reportData = []
        for p in pools:
            dataUsers = []
            dataAccesses = []
            for interval in samplingIntervals:
                key = (interval[0] + interval[1]) / 2
                q = events.statsManager().getEvents(events.OT_DEPLOYED, events.ET_ACCESS, since=interval[0], to=interval[1], owner_id=p[0]).values(fld).annotate(cnt=Count(fld))
                accesses = 0
                for v in q:
                    accesses += v['cnt']

                dataUsers.append((key, len(q)))  # @UndefinedVariable
                dataAccesses.append((key, accesses))
                reportData.append(
                    {
                        'name': p[1],
                        'date': tools.timestampAsStr(interval[0], xLabelFormat) + ' - ' + tools.timestampAsStr(interval[1], xLabelFormat),
                        'users': len(q),
                        'accesses': accesses
                    }
                )
            poolsData.append({
                'pool': p[0],
                'name': p[1],
                'dataUsers': dataUsers,
                'dataAccesses': dataAccesses,
            })

        return (xLabelFormat, poolsData, reportData)

    def generate(self):
        # Generate the sampling intervals and get dataUsers from db
        start = self.startDate.stamp()
        end = self.endDate.stamp()

        xLabelFormat, poolsData, reportData = self.getRangeData()

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)  # @UndefinedVariable

        options = {
            'encoding': 'utf-8',
            'axis': {
                'x': {
                    'ticks': [
                        dict(v=i, label=filters.date(datetime.datetime.fromtimestamp(l), xLabelFormat)) for i, l in enumerate(range(start, end, (end - start) / self.samplingPoints.num()))
                    ],
                    'range': (0, self.samplingPoints.num()),
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
            'title': _('Users by pool'),
        }

        # chart = pycha.line.LineChart(surface, options)
        # chart = pycha.bar.VerticalBarChart(surface, options)
        chart = pycha.stackedbar.StackedVerticalBarChart(surface, options)

        dataset = []
        for pool in poolsData:
            logger.debug(pool['dataUsers'])
            ds = list((i, l[1]) for i, l in enumerate(pool['dataUsers']))
            logger.debug(ds)
            dataset.append((ugettext('Users for {}').format(pool['name']), ds))

        logger.debug('Dataset: {}'.format(dataset))
        chart.addDataset(dataset)

        chart.render()

        img = PILImage.frombuffer("RGBA", (surface.get_width(), surface.get_height()), surface.get_data(), "raw", "BGRA", 0, 1)

        # Accesses
        chart = pycha.stackedbar.StackedVerticalBarChart(surface, options)

        dataset = []
        for pool in poolsData:
            logger.debug(pool['dataAccesses'])
            ds = list((i, l[1]) for i, l in enumerate(pool['dataAccesses']))
            logger.debug(ds)
            dataset.append((ugettext('Accesses for {}').format(pool['name']), ds))

        logger.debug('Dataset: {}'.format(dataset))
        chart.addDataset(dataset)

        chart.render()

        img2 = PILImage.frombuffer("RGBA", (surface.get_width(), surface.get_height()), surface.get_data(), "raw", "BGRA", 0, 1)

        # Generate Data for pools, basically joining all pool data

        queryset = [
            {'image': img, 'image2': img2, 'data': reportData }
        ]

        logger.debug(queryset)

        output = StringIO.StringIO()

        try:
            report = AccessReport(queryset=queryset)
            report.title = ugettext('UDS Pools Performance Report')
            report.generate_by(PDFGenerator, filename=output)
            return output.getvalue()
        except Exception:
            logger.exception('Errool')
            return None


class PoolPerformanceReportCSV(PoolPerformanceReport):
    filename = 'access.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '6445b526-24ce-11e5-b3cb-10feed05884b'
    encoded = False

    # Input fields
    pools = PoolPerformanceReport.pools
    startDate = PoolPerformanceReport.startDate
    endDate = PoolPerformanceReport.endDate
    samplingPoints = PoolPerformanceReport.samplingPoints

    def generate(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        reportData = self.getRangeData()[2]

        writer.writerow([ugettext('Pool'), ugettext('Date range'), ugettext('Users'), ugettext('Accesses')])

        for v in reportData:
            writer.writerow([v['name'], v['date'], v['users'], v['accesses']])

        return output.getvalue()
