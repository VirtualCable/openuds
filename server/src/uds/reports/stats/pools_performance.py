# -*- coding: utf-8 -*-

#
# Copyright (c) 2015-2023 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import io
import csv
import datetime
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _
from django.db.models import Count
import django.template.defaultfilters as filters

from uds.core.ui import gui
from uds.core.util.stats import events
from uds.core.util import tools
from uds.core.managers.stats import StatsManager
from uds.core.reports import graphs
from uds.models import ServicePool

from .base import StatsReport

logger = logging.getLogger(__name__)

# several constants as Width height, margins, ..
WIDTH, HEIGHT, DPI = 19.2, 10.8, 100
SIZE = (WIDTH, HEIGHT, DPI)


class PoolPerformanceReport(StatsReport):
    filename = 'pools_performance.pdf'
    name = _('Pools performance by date')  # Report name
    description = _('Pools performance report by date')  # Report description
    uuid = '88932b48-1fd3-11e5-a776-10feed05884b'

    # Input fields
    pools = gui.MultiChoiceField(
        order=1, label=_('Pools'), tooltip=_('Pools for report'), required=True
    )

    startDate = gui.DateField(
        order=2,
        label=_('Starting date'),
        tooltip=_('starting date for report'),
        default=datetime.date.min,
        required=True,
    )

    endDate = gui.DateField(
        order=3,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        default=datetime.date.max,
        required=True,
    )

    samplingPoints = gui.NumericField(
        order=4,
        label=_('Number of intervals'),
        length=3,
        minValue=0,
        maxValue=32,
        tooltip=_('Number of sampling points used in charts'),
        default='8',
    )

    def initGui(self) -> None:
        logger.debug('Initializing gui')
        vals = [
            gui.choiceItem(v.uuid, v.name)
            for v in ServicePool.objects.all().order_by('name')
        ]
        self.pools.setValues(vals)

    def getPools(self) -> typing.Iterable[typing.Tuple[str, str]]:
        for p in ServicePool.objects.filter(uuid__in=self.pools.value):
            yield (str(p.id), p.name)

    def getRangeData(
        self,
    ) -> typing.Tuple[str, typing.List, typing.List]:  # pylint: disable=too-many-locals
        start = self.startDate.stamp()
        end = self.endDate.stamp()
        if self.samplingPoints.num() < 2:
            self.samplingPoints.value = 2
        if self.samplingPoints.num() > 128:
            self.samplingPoints.value = 128

        samplingPoints = self.samplingPoints.num()

        # x axis label format
        if end - start > 3600 * 24 * 2:
            xLabelFormat = 'SHORT_DATE_FORMAT'
        else:
            xLabelFormat = 'SHORT_DATETIME_FORMAT'

        samplingIntervals: typing.List[typing.Tuple[int, int]] = []
        samplingIntervalSeconds = (end - start) / samplingPoints
        for i in range(samplingPoints):
            samplingIntervals.append((int(start + i * samplingIntervalSeconds), int(start + (i + 1) * samplingIntervalSeconds)))

        # Store dataUsers for all pools
        poolsData = []

        fld = StatsManager.manager().getEventFldFor('username')

        reportData = []
        for p in self.getPools():
            dataUsers = []
            dataAccesses = []
            for interval in samplingIntervals:
                key = (interval[0] + interval[1]) // 2
                q = (
                    StatsManager.manager()
                    .getEvents(
                        events.OT_SERVICEPOOL,
                        events.ET_ACCESS,
                        since=interval[0],
                        to=interval[1],
                        owner_id=p[0],
                    )
                    .values(fld)
                    .annotate(cnt=Count(fld))
                )
                accesses = 0
                for v in q:
                    accesses += v['cnt']

                dataUsers.append((key, len(q)))  # @UndefinedVariable
                dataAccesses.append((key, accesses))
                reportData.append(
                    {
                        'name': p[1],
                        'date': tools.timestampAsStr(interval[0], 'SHORT_DATETIME_FORMAT')
                        + ' - '
                        + tools.timestampAsStr(interval[1], 'SHORT_DATETIME_FORMAT'),
                        'users': len(q),
                        'accesses': accesses,
                    }
                )
            poolsData.append(
                {
                    'pool': p[0],
                    'name': p[1],
                    'dataUsers': dataUsers,
                    'dataAccesses': dataAccesses,
                }
            )

        return xLabelFormat, poolsData, reportData

    def generate(self):
        # Generate the sampling intervals and get dataUsers from db
        xLabelFormat, poolsData, reportData = self.getRangeData()

        graph1 = io.BytesIO()
        graph2 = io.BytesIO()

        # surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)  # @UndefinedVariable

        # logger.debug('PoolsData: %s', poolsData)

        X = [v[0] for v in poolsData[0]['dataUsers']]
        data = {
            'title': _('Distinct Users'),
            'x': X,
            'xtickFnc': lambda l: filters.date(
                datetime.datetime.fromtimestamp(X[int(l)]), xLabelFormat
            )
            if int(l) >= 0
            else '',
            'xlabel': _('Date'),
            'y': [
                {'label': p['name'], 'data': [v[1] for v in p['dataUsers']]}
                for p in poolsData
            ],
            'ylabel': _('Users'),
        }

        graphs.barChart(SIZE, data, graph1)

        X = [v[0] for v in poolsData[0]['dataAccesses']]
        data = {
            'title': _('Accesses'),
            'x': X,
            'xtickFnc': lambda l: filters.date(
                datetime.datetime.fromtimestamp(X[int(l)]), xLabelFormat
            )
            if int(l) >= 0
            else '',
            'xlabel': _('Date'),
            'y': [
                {'label': p['name'], 'data': [v[1] for v in p['dataAccesses']]}
                for p in poolsData
            ],
            'ylabel': _('Accesses'),
        }

        graphs.barChart(SIZE, data, graph2)

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
            header=gettext('UDS Pools Performance Report'),
            water=gettext('Pools Performance'),
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
        output = io.StringIO()
        writer = csv.writer(output)

        reportData = self.getRangeData()[2]

        writer.writerow(
            [
                gettext('Pool'),
                gettext('Date range'),
                gettext('Users'),
                gettext('Accesses'),
            ]
        )

        for v in reportData:
            writer.writerow([v['name'], v['date'], v['users'], v['accesses']])

        return output.getvalue()
