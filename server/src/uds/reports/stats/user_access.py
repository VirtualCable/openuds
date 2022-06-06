# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2020 Virtual Cable S.L.U.
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
import csv
import io
import datetime
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _
import django.template.defaultfilters as filters

from uds.core.ui import gui
from uds.core.util.stats import events
from uds.core.util import tools
from uds.core.managers.stats import StatsManager
from uds.core.reports import graphs

from .base import StatsReport


logger = logging.getLogger(__name__)

# several constants as Width height
WIDTH, HEIGHT, DPI = 19.2, 10.8, 100
SIZE = (WIDTH, HEIGHT, DPI)


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
        required=True,
    )

    endDate = gui.DateField(
        order=2,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        defvalue=datetime.date.max,
        required=True,
    )

    samplingPoints = gui.NumericField(
        order=3,
        label=_('Number of intervals'),
        length=3,
        minValue=0,
        maxValue=128,
        tooltip=_('Number of sampling points used in charts'),
        defvalue='64',
    )

    def initialize(self, values):
        pass

    def initGui(self):
        pass

    def getRangeData(self) -> typing.Tuple[str, typing.List, typing.List]:
        start = self.startDate.stamp()
        end = self.endDate.stamp()
        # if self.samplingPoints.num() < 8:
        #    self.samplingPoints.value = (
        #        self.endDate.date() - self.startDate.date()
        #    ).days
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

        data = []
        reportData = []
        for interval in samplingIntervals:
            key = (interval[0] + interval[1]) / 2
            val = (
                StatsManager.manager()
                .getEvents(
                    events.OT_AUTHENTICATOR,
                    events.ET_LOGIN,
                    since=interval[0],
                    to=interval[1],
                )
                .count()
            )
            data.append((key, val))  # @UndefinedVariable
            reportData.append(
                {
                    'date': tools.timestampAsStr(interval[0], xLabelFormat)
                    + ' - '
                    + tools.timestampAsStr(interval[1], xLabelFormat),
                    'users': val,
                }
            )

        return xLabelFormat, data, reportData

    def getWeekHourlyData(self):
        start = self.startDate.stamp()
        end = self.endDate.stamp()

        dataWeek = [0] * 7
        dataHour = [0] * 24
        dataWeekHour = [[0] * 24 for _ in range(7)]
        for val in StatsManager.manager().getEvents(
            events.OT_AUTHENTICATOR, events.ET_LOGIN, since=start, to=end
        ):
            s = datetime.datetime.fromtimestamp(val.stamp)
            dataWeek[s.weekday()] += 1
            dataHour[s.hour] += 1
            dataWeekHour[s.weekday()][s.hour] += 1
            logger.debug('Data: %s %s', s.weekday(), s.hour)

        return dataWeek, dataHour, dataWeekHour

    def generate(self):
        # Sample query:
        #   'SELECT *, count(*) as number, CEIL(stamp/(3600))*3600 as block'
        #   ' FROM {table}'
        #   ' WHERE event_type = 0 and stamp >= {start} and stamp <= {end}'
        #   ' GROUP BY CEIL(stamp/(3600))'
        #   ' ORDER BY block'

        xLabelFormat, data, reportData = self.getRangeData()

        #
        # User access by date graph
        #
        graph1 = io.BytesIO()

        X = [v[0] for v in data]
        d = {
            'title': _('Users Access (global)'),
            'x': X,
            'xtickFnc': lambda l: filters.date(
                datetime.datetime.fromtimestamp(l), xLabelFormat
            ),
            'xlabel': _('Date'),
            'y': [{'label': 'Users', 'data': [v[1] for v in data]}],
            'ylabel': 'Users',
            'allTicks': False,
        }

        graphs.lineChart(SIZE, d, graph1)

        graph2 = io.BytesIO()
        graph3 = io.BytesIO()
        graph4 = io.BytesIO()
        dataWeek, dataHour, dataWeekHour = self.getWeekHourlyData()

        X = list(range(7))
        d = {
            'title': _('Users Access (by week)'),
            'x': X,
            'xtickFnc': lambda l: [
                _('Monday'),
                _('Tuesday'),
                _('Wednesday'),
                _('Thursday'),
                _('Friday'),
                _('Saturday'),
                _('Sunday'),
            ][l],
            'xlabel': _('Day of week'),
            'y': [{'label': 'Users', 'data': [v for v in dataWeek]}],
            'ylabel': 'Users',
        }

        graphs.barChart(SIZE, d, graph2)

        X = list(range(24))
        d = {
            'title': _('Users Access (by hour)'),
            'x': X,
            'xlabel': _('Hour'),
            'y': [{'label': 'Users', 'data': [v for v in dataHour]}],
            'ylabel': 'Users',
        }

        graphs.barChart(SIZE, d, graph3)

        X = list(range(24))
        Y = list(range(7))
        d = {
            'title': _('Users Access (by hour)'),
            'x': X,
            'xlabel': _('Hour'),
            'xtickFnc': lambda l: l,
            'y': Y,
            'ylabel': _('Day of week'),
            'ytickFnc': lambda l: [
                _('Monday'),
                _('Tuesday'),
                _('Wednesday'),
                _('Thursday'),
                _('Friday'),
                _('Saturday'),
                _('Sunday'),
            ][l],
            'z': dataWeekHour,
            'zlabel': _('Users'),
        }

        graphs.surfaceChart(SIZE, d, graph4)

        return self.templateAsPDF(
            'uds/reports/stats/user-access.html',
            dct={
                'data': reportData,
                'beginning': self.startDate.date(),
                'ending': self.endDate.date(),
                'intervals': self.samplingPoints.num(),
            },
            header=gettext('Users access to UDS'),
            water=gettext('UDS Report for users access'),
            images={
                'graph1': graph1.getvalue(),
                'graph2': graph2.getvalue(),
                'graph3': graph3.getvalue(),
                'graph4': graph4.getvalue(),
            },
        )


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
        output = io.StringIO()
        writer = csv.writer(output)

        reportData = self.getRangeData()[2]

        writer.writerow([gettext('Date range'), gettext('Users')])

        for v in reportData:
            writer.writerow([v['date'], v['users']])

        return output.getvalue()
