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
import csv
import datetime
import io
import logging
import typing
import collections.abc

import django.template.defaultfilters as filters
from django.db.models import Count
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core.managers.stats import StatsManager
from uds.core.reports import graphs
from uds.core.ui import gui
from uds.core.util import utils
from uds.core.util.stats import events
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
    pools = StatsReport.pools
    start_date = StatsReport.start_date
    end_date = StatsReport.end_date

    sampling_points = StatsReport.sampling_points

    def init_gui(self) -> None:
        logger.debug('Initializing gui')
        vals = [gui.choice_item(v.uuid, v.name) for v in ServicePool.objects.all().order_by('name')]
        self.pools.set_choices(vals)

    def list_pools(self) -> collections.abc.Iterable[tuple[int, str]]:
        for p in ServicePool.objects.filter(uuid__in=self.pools.value):
            yield (p.id, p.name)

    def get_range_data(
        self,
    ) -> tuple[
        str, list[dict[str, typing.Any]], list[dict[str, typing.Any]]
    ]:  # pylint: disable=too-many-locals
        start = self.start_date.as_timestamp()
        end = self.end_date.as_timestamp()
        if self.sampling_points.as_int() < 2:
            self.sampling_points.value = 2
        if self.sampling_points.as_int() > 128:
            self.sampling_points.value = 128

        sampling_points = self.sampling_points.as_int()

        # x axis label format
        if end - start > 3600 * 24 * 2:
            x_label_format = 'SHORT_DATE_FORMAT'
        else:
            x_label_format = 'SHORT_DATETIME_FORMAT'

        sampling_intervals: list[tuple[int, int]] = []
        sampling_interval_seconds = (end - start) / sampling_points
        for i in range(sampling_points):
            sampling_intervals.append(
                (int(start + i * sampling_interval_seconds), int(start + (i + 1) * sampling_interval_seconds))
            )

        # Store dataUsers for all pools
        pools_data: list[dict[str, typing.Any]] = []

        fld = StatsManager.manager().get_event_field_for('username')

        report_data: list[dict[str, typing.Any]] = []
        for p in self.list_pools():
            data_users: list[tuple[int, int]] = []
            data_accesses: list[tuple[int, int]] = []
            for interval in sampling_intervals:
                key = (interval[0] + interval[1]) // 2
                q = (
                    StatsManager.manager()
                    .enumerate_events(
                        events.types.stats.EventOwnerType.SERVICEPOOL,
                        events.types.stats.EventType.ACCESS,
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

                data_users.append((key, len(q)))  # @UndefinedVariable
                data_accesses.append((key, accesses))
                report_data.append(
                    {
                        'name': p[1],
                        'date': utils.timestamp_as_str(interval[0], 'SHORT_DATETIME_FORMAT')
                        + ' - '
                        + utils.timestamp_as_str(interval[1], 'SHORT_DATETIME_FORMAT'),
                        'users': len(q),
                        'accesses': accesses,
                    }
                )
            pools_data.append(
                {
                    'pool': p[0],
                    'name': p[1],
                    'dataUsers': data_users,
                    'dataAccesses': data_accesses,
                }
            )

        return x_label_format, pools_data, report_data

    def generate(self) -> bytes:
        # Generate the sampling intervals and get dataUsers from db
        x_label_format, pools_data, report_data = self.get_range_data()

        graph1 = io.BytesIO()
        graph2 = io.BytesIO()

        # surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)  # @UndefinedVariable

        # logger.debug('PoolsData: %s', poolsData)
        def _tick_fnc1(l: int) -> str:
            return filters.date(datetime.datetime.fromtimestamp(l), x_label_format) if int(l) >= 0 else ''

        x = [v[0] for v in pools_data[0]['dataUsers']]
        data = {
            'title': _('Distinct Users'),
            'x': x,
            'xtickFnc': _tick_fnc1,
            'xlabel': _('Date'),
            'y': [{'label': p['name'], 'data': [v[1] for v in p['dataUsers']]} for p in pools_data],
            'ylabel': _('Users'),
        }

        graphs.bar_chart(SIZE, data, graph1)
        
        def _tick_fnc2(l: int) -> str:
            return filters.date(datetime.datetime.fromtimestamp(l), x_label_format) if int(l) >= 0 else ''

        x = [v[0] for v in pools_data[0]['dataAccesses']]
        data = {
            'title': _('Accesses'),
            'x': x,
            'xtickFnc': _tick_fnc2,
            'xlabel': _('Date'),
            'y': [{'label': p['name'], 'data': [v[1] for v in p['dataAccesses']]} for p in pools_data],
            'ylabel': _('Accesses'),
        }

        graphs.bar_chart(SIZE, data, graph2)

        # Generate Data for pools, basically joining all pool data

        return self.template_as_pdf(
            'uds/reports/stats/pools-performance.html',
            dct={
                'data': report_data,
                'pools': [i[1] for i in self.list_pools()],
                'beginning': self.start_date.as_date(),
                'ending': self.end_date.as_date(),
                'intervals': self.sampling_points.as_int(),
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
    start_date = PoolPerformanceReport.start_date
    end_date = PoolPerformanceReport.end_date
    sampling_points = PoolPerformanceReport.sampling_points

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        report_data = self.get_range_data()[2]

        writer.writerow(
            [
                gettext('Pool'),
                gettext('Date range'),
                gettext('Users'),
                gettext('Accesses'),
            ]
        )

        for v in report_data:
            writer.writerow([v['name'], v['date'], v['users'], v['accesses']])

        return output.getvalue().encode('utf-8')
