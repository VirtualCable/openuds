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
import io
import datetime
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _

from uds.core.ui import gui
from uds.core.util.stats import counters
from uds.core.reports import graphs
from uds.models import ServicePool


from .base import StatsReport


logger = logging.getLogger(__name__)

# several constants as Width height, margins, ..
WIDTH, HEIGHT, DPI = 19.2, 10.8, 100
SIZE = (WIDTH, HEIGHT, DPI)


class CountersPoolAssigned(StatsReport):
    filename = 'pools_counters.pdf'
    name = _('Pools usage on a day')  # Report name
    description = _('Pools usage counters for an specific day')  # Report description
    uuid = '0b429f70-2fc6-11e7-9a2a-8fc37101e66a'

    pools = StatsReport.pools
    start_date = StatsReport.start_date

    def init_gui(self) -> None:
        logger.debug('Initializing gui')
        vals = [gui.choice_item(v.uuid, v.name) for v in ServicePool.objects.all().order_by('name')]
        self.pools.set_choices(vals)

    def get_data(self) -> list[dict[str, typing.Any]]:
        # Generate the sampling intervals and get dataUsers from db
        start = self.start_date.as_date()

        data: list[dict[str, typing.Any]] = []

        pool: ServicePool
        for pool_uuid in self.pools.value:
            try:
                pool = ServicePool.objects.get(uuid=pool_uuid)
            except Exception:  # nosec:  If not found, simple ignore it and go for next
                continue

            hours = [0] * 24
            
            # Convert start to datetime
            start_datetime = datetime.datetime.combine(start, datetime.time.min)

            for x in counters.enumerate_counters(
                pool,
                counters.types.stats.CounterType.ASSIGNED,
                since=start_datetime,
                to=start_datetime + datetime.timedelta(days=1),
                interval=3600,
                use_max=True,
                all=False,
            ):
                hour = x[0].hour
                val = int(x[1])
                hours[hour] = max(hours[hour], val)

            data.append({'uuid': pool.uuid, 'name': pool.name, 'hours': hours})

        logger.debug('data: %s', data)

        return data

    def generate(self) -> bytes:
        items = self.get_data()

        graph1 = io.BytesIO()

        X = list(range(24))
        d = {
            'title': _('Services by hour'),
            'x': X,
            'xtickFnc': '{:02d}'.format,  # Two digits
            'xlabel': _('Hour'),
            'y': [{'label': i['name'], 'data': [i['hours'][v] for v in X]} for i in items],
            'ylabel': 'Services',
        }

        graphs.bar_chart(SIZE, d, graph1)

        return self.template_as_pdf(
            'uds/reports/stats/pools-usage-day.html',
            dct={
                'data': items,
                'pools': [v.name for v in ServicePool.objects.filter(uuid__in=self.pools.value)],
                'beginning': self.start_date.as_date(),
            },
            header=gettext('Services usage report for a day'),
            water=gettext('Service usage report'),
            images={'graph1': graph1.getvalue()},
        )


class CountersPoolAssignedCSV(CountersPoolAssigned):
    filename = 'pools_counters.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '1491148a-2fc6-11e7-a5ad-03d9a417561c'
    encoded = False

    # Input fields
    start_date = CountersPoolAssigned.start_date
    pools = CountersPoolAssigned.pools

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([gettext('Pool'), gettext('Hour'), gettext('Services')])

        items = self.get_data()

        for i in items:
            for j in range(24):
                writer.writerow([i['name'], f'{j:02d}', i['hours'][j]])

        return output.getvalue().encode()
