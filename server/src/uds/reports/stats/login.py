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
import django.template.defaultfilters as filters

from uds.core.ui.UserInterface import gui
from uds.core.reports.tools import UDSImage, UDSGeraldoReport
from uds.core.util.stats import events

import StringIO
import csv

import cairo
import pycha.line
import pycha.bar

from .base import StatsReport

from uds.core.util import tools
from geraldo.generators.pdf import PDFGenerator
from geraldo import ReportBand, ObjectValue, BAND_WIDTH, Label, SubReport
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from PIL import Image as PILImage

import datetime
import logging

logger = logging.getLogger(__name__)

__updated__ = '2015-09-04'

# several constants as Width height, margins, ..
WIDTH, HEIGHT = 1800, 1000
GERALDO_WIDTH = 120 * mm
GERALDO_HEIGHT = GERALDO_WIDTH * HEIGHT / WIDTH


class AccessReport(UDSGeraldoReport):

    class band_detail(ReportBand):
        height = 400 * mm  # Height bigger than a page, so a new page is launched
        # auto_expand_height = True
        elements = (
            Label(text=_('Users access by date'), top=0.6 * cm, left=0, width=BAND_WIDTH,
                  style={'fontName': 'Helvetica-Bold', 'fontSize': 10, 'alignment': TA_CENTER}),
            UDSImage(left=4 * cm, top=1 * cm,
                     width=GERALDO_WIDTH, height=GERALDO_HEIGHT,
                     get_image=lambda x: x.instance['image']),

            Label(text=_('Users access by day of week'), top=GERALDO_HEIGHT + 1.2 * cm, left=0, width=BAND_WIDTH,
                  style={'fontName': 'Helvetica-Bold', 'fontSize': 10, 'alignment': TA_CENTER}),
            UDSImage(left=4 * cm, top=GERALDO_HEIGHT + 1.6 * cm,
                     width=GERALDO_WIDTH, height=GERALDO_HEIGHT,
                     get_image=lambda x: x.instance['image2']),

            Label(text=_('Users access by hour'), top=2 * GERALDO_HEIGHT + 2 * cm, left=0, width=BAND_WIDTH,
                  style={'fontName': 'Helvetica-Bold', 'fontSize': 10, 'alignment': TA_CENTER}),
            UDSImage(left=4 * cm, top=2 * GERALDO_HEIGHT + 2.4 * cm,
                     width=GERALDO_WIDTH, height=GERALDO_HEIGHT,
                     get_image=lambda x: x.instance['image3']),
        )

    subreports = [
        SubReport(
            queryset_string='%(object)s["data"]',
            band_header=ReportBand(
                height=1 * cm,
                auto_expand_height=True,
                elements=(
                    Label(text=_('Users access by date'), top=0.2 * cm, left=0, width=BAND_WIDTH,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 12, 'alignment': TA_CENTER}),
                    Label(text=_('Date range'), top=1.0 * cm, left=1.2 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 10}),
                    Label(text=_('Users'), top=1.0 * cm, left=14 * cm,
                          style={'fontName': 'Helvetica-Bold', 'fontSize': 10}),
                ),
                # borders={'bottom': True}
            ),
            band_detail=ReportBand(
                height=0.5 * cm,
                elements=(
                    ObjectValue(attribute_name='date', top=0, left=1.2 * cm, width=12 * cm, style={'fontName': 'Helvetica', 'fontSize': 9}),
                    ObjectValue(attribute_name='users', top=0, left=14 * cm, style={'fontName': 'Helvetica', 'fontSize': 9}),
                )
            ),
        )
    ]


class StatsReportLogin(StatsReport):
    filename = 'access.pdf'
    name = _('Users access report by date')  # Report name
    description = _('Report of user access to platform by date')  # Report description
    uuid = '0f62f19a-f166-11e4-8f59-10feed05884b'

    # Input fields
    startDate = gui.DateField(
        order=1,
        label=_('Starting date'),
        tooltip=_('starting date for report'),
        defvalue=datetime.date.min,
        required=True
    )

    endDate = gui.DateField(
        order=2,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        defvalue=datetime.date.max,
        required=True
    )

    samplingPoints = gui.NumericField(
        order=3,
        label=_('Number of intervals'),
        length=3,
        minValue=16,
        maxValue=128,
        tooltip=_('Number of sampling points used in charts'),
        defvalue='64'
    )

    def initialize(self, values):
        pass

    def initGui(self):
        pass

    def getRangeData(self):
        start = self.startDate.stamp()
        end = self.endDate.stamp()
        samplingPoints = self.samplingPoints.num()

        # x axis label format
        if end - start > 3600 * 24 * 2:
            xLabelFormat = 'SHORT_DATE_FORMAT'
        else:
            xLabelFormat = 'SHORT_DATETIME_FORMAT'

        samplingIntervals = []
        prevVal = None
        for val in range(start, end, (end - start) / (samplingPoints + 1)):
            if prevVal is None:
                prevVal = val
                continue
            samplingIntervals.append((prevVal, val))
            prevVal = val

        data = []
        reportData = []
        for interval in samplingIntervals:
            key = (interval[0] + interval[1]) / 2
            val = events.statsManager().getEvents(events.OT_AUTHENTICATOR, events.ET_LOGIN, since=interval[0], to=interval[1]).count()
            data.append((key, val))  # @UndefinedVariable
            reportData.append(
                {
                    'date': tools.timestampAsStr(interval[0], xLabelFormat) + ' - ' + tools.timestampAsStr(interval[1], xLabelFormat),
                    'users': val
                }
            )

        return (xLabelFormat, data, reportData)

    def getWeekHourlyData(self):
        start = self.startDate.stamp()
        end = self.endDate.stamp()

        dataWeek = [0] * 7
        dataHour = [0] * 24
        for val in events.statsManager().getEvents(events.OT_AUTHENTICATOR, events.ET_LOGIN, since=start, to=end):
            s = datetime.datetime.fromtimestamp(val.stamp)
            dataWeek[s.weekday()] += 1
            dataHour[s.hour] += 1

        return (dataWeek, dataHour)

    def generate(self):
        # Sample query:
        #   'SELECT *, count(*) as number, CEIL(stamp/(3600))*3600 as block'
        #   ' FROM {table}'
        #   ' WHERE event_type = 0 and stamp >= {start} and stamp <= {end}'
        #   ' GROUP BY CEIL(stamp/(3600))'
        #   ' ORDER BY block'

        # Generate the sampling intervals and get data from db
        start = self.startDate.stamp()
        end = self.endDate.stamp()

        xLabelFormat, data, reportData = self.getRangeData()

        #
        # User access by date graph
        #

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)

        dataset = ((ugettext('Users access to UDS'), data),)

        options = {
            'encoding': 'utf-8',
            'axis': {
                'x': {
                    'ticks': [
                        dict(v=i, label=filters.date(datetime.datetime.fromtimestamp(i), xLabelFormat)) for i in range(start, end, (end - start) / 11)
                    ],
                    'range': (start, end),
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
                'name': 'gradient',
                'args': {
                    'initialColor': '#B8CA16',
                },
            },
            'legend': {
                'hide': False,
                'legendFontSize': 16,
                'position': {
                    'left': 48,
                    'bottom': 8,
                }
            },
            'padding': {
                'left': 48,
                'top': 16,
                'right': 48,
                'bottom': 48,
            },
            'title': _('Users access to UDS')
        }

        chart = pycha.line.LineChart(surface, options)
        chart.addDataset(dataset)
        chart.render()

        img = PILImage.frombuffer("RGBA", (surface.get_width(), surface.get_height()), surface.get_data(), "raw", "BGRA", 0, 1)

        #
        # User access by day of week
        #
        dataWeek, dataHour = self.getWeekHourlyData()

        dataset = ((ugettext('Users access to UDS'), [(i, dataWeek[i]) for i in range(0, 7)]),)

        options['axis'] = {
            'x': {
                'ticks': [
                    dict(v=i, label='Day {}'.format(i)) for i in range(0, 7)
                ],
                'range': (0, 6),
                'showLines': True,
            },
            'y': {
                'tickCount': 10,
                'showLines': True,
            },
            'tickFontSize': 16,
        }

        chart = pycha.bar.VerticalBarChart(surface, options)
        chart.addDataset(dataset)
        chart.render()

        img2 = PILImage.frombuffer("RGBA", (surface.get_width(), surface.get_height()), surface.get_data(), "raw", "BGRA", 0, 1)


        # Hourly chart
        dataset = ((ugettext('Users access to UDS'), [(i, dataHour[i]) for i in range(0, 24)]),)

        options['axis'] = {
            'x': {
                'ticks': [
                    dict(v=i, label='{}:00'.format(i)) for i in range(0, 24)
                ],
                'range': (0, 24),
                'showLines': True,
            },
            'y': {
                'tickCount': 10,
                'showLines': True,
            },
            'tickFontSize': 16,
        }

        chart = pycha.bar.VerticalBarChart(surface, options)
        chart.addDataset(dataset)
        chart.render()

        img3 = PILImage.frombuffer("RGBA", (surface.get_width(), surface.get_height()), surface.get_data(), "raw", "BGRA", 0, 1)

        output = StringIO.StringIO()

        queryset = [
            {'image': img, 'image2': img2, 'image3': img3, 'data': reportData}
        ]

        logger.debug(queryset)

        try:
            report = AccessReport(queryset=queryset)
            report.title = ugettext('Users access to UDS')
            # report = UsersReport(queryset=users)
            report.generate_by(PDFGenerator, filename=output)
            return output.getvalue()
        except Exception:
            logger.exception('Errool')
            return None


class StatsReportLoginCSV(StatsReportLogin):
    filename = 'access.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    name = _('Users access report by date')  # Report name
    description = _('Report of user access to platform by date')  # Report description
    uuid = '765b5580-1840-11e5-8137-10feed05884b'
    encoded = False

    # Input fields
    startDate = StatsReportLogin.startDate
    endDate = StatsReportLogin.endDate
    samplingPoints = StatsReportLogin.samplingPoints

    def generate(self):
        output = StringIO.StringIO()
        writer = csv.writer(output)

        reportData = self.getRangeData()[2]

        writer.writerow([ugettext('Date range'), ugettext('Users')])

        for v in reportData:
            writer.writerow([v['date'], v['users']])

        return output.getvalue()
