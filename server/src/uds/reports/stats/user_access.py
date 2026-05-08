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

import django.template.defaultfilters as filters
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core.managers.stats import StatsManager
from uds.core.reports import graphs
from uds.core.ui import gui
from uds.core.util import stats, utils

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
    start_date = StatsReport.start_date

    end_date = StatsReport.end_date

    sampling_points = gui.NumericField(
        order=4,
        label=_('Number of intervals'),
        length=3,
        min_value=2,
        max_value=128,
        tooltip=_('Number of sampling points used in charts'),
        default=64,
    )

    def get_range_data(self) -> tuple[str, list[tuple[int, int]], list[dict[str, typing.Any]]]:
        start = self.start_date.as_timestamp()
        end = self.end_date.as_timestamp()
        sampling_points = max(2, min(128, self.sampling_points.as_int()))

        # x axis label format
        if end - start > 3600 * 24 * 2:
            x_label_format = 'SHORT_DATE_FORMAT'
        else:
            x_label_format = 'SHORT_DATETIME_FORMAT'

        sampling_interval_seconds = (end - start) / sampling_points
        bucket_bounds: list[tuple[int, int, int]] = []
        for i in range(sampling_points):
            b_start = int(start + i * sampling_interval_seconds)
            b_end = int(start + (i + 1) * sampling_interval_seconds)
            bucket_bounds.append((b_start, b_end, (b_start + b_end) // 2))

        # Single query covering the full range; bucketize in Python.
        # Was: sampling_points queries (up to 128) doing COUNT(*) each.
        counts = [0] * sampling_points
        last_idx = sampling_points - 1
        for row in (
            StatsManager.manager()
            .enumerate_events(
                stats.events.types.stats.EventOwnerType.AUTHENTICATOR,
                stats.events.types.stats.EventType.LOGIN,
                since=start,
                to=end,
            )
            .values('stamp')
        ):
            idx = int((row['stamp'] - start) // sampling_interval_seconds)
            if idx < 0:
                continue
            if idx > last_idx:
                idx = last_idx
            counts[idx] += 1

        data: list[tuple[int, int]] = []
        report_data: list[dict[str, typing.Any]] = []
        for i, (b_start, b_end, key) in enumerate(bucket_bounds):
            val = counts[i]
            data.append((key, val))
            report_data.append(
                {
                    'date': utils.timestamp_as_str(b_start, 'SHORT_DATETIME_FORMAT')
                    + ' - '
                    + utils.timestamp_as_str(b_end, 'SHORT_DATETIME_FORMAT'),
                    'users': val,
                }
            )

        return x_label_format, data, report_data

    def get_week_hourly_data(self) -> tuple[list[int], list[int], list[list[int]]]:
        start = self.start_date.as_timestamp()
        end = self.end_date.as_timestamp()

        data_week = [0] * 7
        data_hour = [0] * 24
        data_week_hour = [[0] * 24 for _ in range(7)]
        # Hoisted: 1 tz lookup + tz-aware fromtimestamp per row instead of
        # make_aware() (which re-resolves the tz internally on every call).
        tz = timezone.get_current_timezone()
        from_ts = datetime.datetime.fromtimestamp
        for row in (
            StatsManager.manager()
            .enumerate_events(
                stats.events.types.stats.EventOwnerType.AUTHENTICATOR,
                stats.events.types.stats.EventType.LOGIN,
                since=start,
                to=end,
            )
            .values('stamp')
        ):
            s = from_ts(row['stamp'], tz)
            wd = s.weekday()
            hr = s.hour
            data_week[wd] += 1
            data_hour[hr] += 1
            data_week_hour[wd][hr] += 1

        return data_week, data_hour, data_week_hour

    def generate(self) -> bytes:
        x_label_format, data, report_data = self.get_range_data()

        #
        # User access by date graph
        #
        graph1 = io.BytesIO()
        
        def _tick_fnc1(l: int) -> str:
            return filters.date(timezone.make_aware(datetime.datetime.fromtimestamp(l)), x_label_format)

        x = [v[0] for v in data]
        d: dict[str, typing.Any] = {
            'title': _('Users Access (global)'),
            'x': x,
            'xtickFnc': _tick_fnc1,
            'xlabel': _('Date'),
            'y': [{'label': 'Users', 'data': [v[1] for v in data]}],
            'ylabel': 'Users',
            'allTicks': False,
        }

        graphs.line_chart(SIZE, d, graph1)

        graph2 = io.BytesIO()
        graph3 = io.BytesIO()
        graph4 = io.BytesIO()
        data_week, data_hour, data_week_hour = self.get_week_hourly_data()
        
        def _tick_fnc2(l: int) -> str:
            return [
                _('Monday'),
                _('Tuesday'),
                _('Wednesday'),
                _('Thursday'),
                _('Friday'),
                _('Saturday'),
                _('Sunday'),
            ][l]

        x = list(range(7))
        d = {
            'title': _('Users Access (by week)'),
            'x': x,
            'xtickFnc': _tick_fnc2,
            'xlabel': _('Day of week'),
            'y': [{'label': 'Users', 'data': list(data_week)}],
            'ylabel': 'Users',
        }

        graphs.bar_chart(SIZE, d, graph2)

        x = list(range(24))
        d = {
            'title': _('Users Access (by hour)'),
            'x': x,
            'xlabel': _('Hour'),
            'y': [{'label': 'Users', 'data': list(data_hour)}],
            'ylabel': 'Users',
        }

        graphs.bar_chart(SIZE, d, graph3)
        
        def _tick_fnc3(l: int) -> str:
            return str(l)

        x = list(range(24))
        Y = list(range(7))
        d = {
            'title': _('Users Access (by hour)'),
            'x': x,
            'xlabel': _('Hour'),
            'xtickFnc': _tick_fnc3,
            'y': Y,
            'ylabel': _('Day of week'),
            'ytickFnc': _tick_fnc2,
            'z': data_week_hour,
            'zlabel': _('Users'),
        }

        graphs.surface_chart(SIZE, d, graph4)

        return self.template_as_pdf(
            'uds/reports/stats/user-access.html',
            dct={
                'data': report_data,
                'beginning': self.start_date.as_date(),
                'ending': self.end_date.as_date(),
                'intervals': max(2, min(128, self.sampling_points.as_int())),
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
    start_date = StatsReportLogin.start_date
    end_date = StatsReportLogin.end_date
    sampling_points = StatsReportLogin.sampling_points

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        report_data = self.get_range_data()[2]

        writer.writerow([gettext('Date range'), gettext('Users')])

        for v in report_data:
            writer.writerow([v['date'], v['users']])

        return output.getvalue().encode()
