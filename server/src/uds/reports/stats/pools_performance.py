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

import csv
import six

from django.utils.translation import ugettext, ugettext_lazy as _
from django.db.models import Count
import django.template.defaultfilters as filters

from uds.core.ui.UserInterface import gui
from uds.core.util.stats import events

from uds.core.reports import graphs

from .base import StatsReport

from uds.core.util import tools
from uds.models import ServicePool

import datetime
import logging

logger = logging.getLogger(__name__)

__updated__ = '2018-04-19'

# several constants as Width height, margins, ..
WIDTH, HEIGHT, DPI = 19.2, 10.8, 100


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
            gui.choiceItem(v.uuid, v.name) for v in ServicePool.objects.all().order_by('name')
        ]
        self.pools.setValues(vals)

    def getPools(self):
        return [(v.id, v.name) for v in ServicePool.objects.filter(uuid__in=self.pools.value)]

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

        pools = self.getPools()

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
        for val in range(start, end, int((end - start) / (samplingPoints + 1))):
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

        return xLabelFormat, poolsData, reportData

    def generate(self):
        # Generate the sampling intervals and get dataUsers from db
        start = self.startDate.stamp()
        end = self.endDate.stamp()

        xLabelFormat, poolsData, reportData = self.getRangeData()
        size = (WIDTH, HEIGHT, DPI)

        graph1 = six.BytesIO()
        graph2 = six.BytesIO()

        # surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)  # @UndefinedVariable

        options = {
            'encoding': 'utf-8',
            'axis': {
                'x': {
                    'ticks': [
                        dict(v=i, label=filters.date(datetime.datetime.fromtimestamp(l), xLabelFormat)) for i, l in enumerate(range(start, end, int((end - start) / self.samplingPoints.num())))
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
                'name': 'gradient',
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

        data = {}

        graphs.barChart(size, data, graph1)

        # chart = pycha.stackedbar.StackedVerticalBarChart(surface, options)

        dataset = []
        for pool in poolsData:
            logger.debug(pool['dataUsers'])
            ds = list((i, l[1]) for i, l in enumerate(pool['dataUsers']))
            logger.debug(ds)
            dataset.append((ugettext('Users for {}').format(pool['name']), ds))

        logger.debug('Dataset: {}'.format(dataset))
        # chart.addDataset(dataset)

        # chart.render()

        # surface.write_to_png(graph1)

        # del chart
        # del surface  # calls finish, flushing to image

        # surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)  # @UndefinedVariable

        # Accesses
        # chart = pycha.stackedbar.StackedVerticalBarChart(surface, options)
        data = {
            'x': [1, 2, 3, 4, 5, 6],
            'xticks': [filters.date(datetime.datetime.fromtimestamp(l), xLabelFormat) for l in range(start, end, int((end - start) / self.samplingPoints.num()))],
            'xlabel': _('Date'),
            'y': [
                {
                 'label': 'First',
                 'data': [1, 2, 4, 8, 16, 32],
                },
                {
                 'label': 'Second',
                 'data': [31, 15, 7, 3, 1, 0],
                }
            ],
            'ylabel': 'Data YYYYY'
        }

        graphs.barChart(size, data, graph2)

        dataset = []
        for pool in poolsData:
            logger.debug(pool['dataAccesses'])
            ds = list((i, l[1]) for i, l in enumerate(pool['dataAccesses']))
            logger.debug(ds)
            dataset.append((ugettext('Accesses for {}').format(pool['name']), ds))

        logger.debug('Dataset: {}'.format(dataset))
        # chart.addDataset(dataset)

        # chart.render()

        # surface.write_to_png(graph2)

        # del chart
        # del surface  # calls finish, flushing to image

        # Generate Data for pools, basically joining all pool data

        return self.templateAsPDF(
            'uds/reports/stats/pools-performance.html',
            dct={
                'data': reportData,
                'pools': [i[1] for i in self.getPools()],
                'beginning': self.startDate.date(),
                'ending': self.endDate.date(),
                'intervals': self.samplingPoints.num(),
            },
            header=ugettext('UDS Pools Performance Report'),
            water=ugettext('Pools Performance'),
            images={'graph1': graph1.getvalue(), 'graph2': graph2.getvalue()},
        )


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
        output = six.StringIO()
        writer = csv.writer(output)

        reportData = self.getRangeData()[2]

        writer.writerow([ugettext('Pool'), ugettext('Date range'), ugettext('Users'), ugettext('Accesses')])

        for v in reportData:
            writer.writerow([v['name'], v['date'], v['users'], v['accesses']])

        return output.getvalue()
