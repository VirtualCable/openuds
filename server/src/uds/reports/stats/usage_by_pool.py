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

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core.managers.stats import StatsManager
from uds.core.ui import gui
from uds.core.util import stats
from uds.models import ServicePool

from .base import StatsReport

logger = logging.getLogger(__name__)


class UsageByPool(StatsReport):
    filename = 'pools_usage.pdf'
    name = _('Pools usage by users')  # Report name
    description = _('Pools usage by user report')  # Report description
    uuid = '38ec12dc-beaf-11e5-bd0a-10feed05884b'

    # Input fields
    pool = StatsReport.pool
    start_date = StatsReport.start_date
    end_date = StatsReport.end_date

    def init_gui(self) -> None:
        logger.debug('Initializing gui')
        vals = [gui.choice_item('0-0-0-0', gettext('ALL POOLS'))] + [
            gui.choice_item(v.uuid, v.name)
            for v in ServicePool.objects.all().order_by('name')
            if v.uuid
        ]
        self.pool.set_choices(vals)

    def get_data(self) -> tuple[list[dict[str, typing.Any]], str]:
        # Generate the sampling intervals and get dataUsers from db
        start = self.start_date.as_timestamp()
        end = self.end_date.as_timestamp()
        logger.debug(self.pool.value)
        if '0-0-0-0' in self.pool.value:
            pools = ServicePool.objects.all()
        else:
            pools = ServicePool.objects.filter(uuid__in=self.pool.value)
        data: list[dict[str, typing.Any]] = []
        for pool in pools:
            items = (
                StatsManager.manager()
                .enumerate_events(
                    stats.events.types.stats.EventOwnerType.SERVICEPOOL,
                    (stats.events.types.stats.EventType.LOGIN, stats.events.types.stats.EventType.LOGOUT),
                    owner_id=pool.id,
                    since=start,
                    to=end,
                )
                .order_by('stamp')
            )

            logins: dict[str, typing.Any] = {}
            for i in items:
                # if '\\' in i.fld1:
                #    continue
                full_username = i.full_username
                if i.event_type == stats.events.types.stats.EventType.LOGIN:
                    logins[full_username] = i.stamp
                else:
                    if full_username in logins:
                        stamp = typing.cast(int, logins[full_username])
                        del logins[full_username]
                        total = i.stamp - stamp
                        data.append(
                            {
                                'name': full_username,
                                # ipv6 handled by src_ip property
                                'origin': i.src_ip,
                                'date': datetime.datetime.fromtimestamp(stamp),
                                'time': total,
                                'pool': pool.uuid,
                                'pool_name': pool.name,
                            }
                        )

        return data, ','.join([p.name for p in pools])

    def generate(self) -> bytes:
        items, poolname = self.get_data()

        return self.template_as_pdf(
            'uds/reports/stats/usage-by-pool.html',
            dct={
                'data': items,
                'pool': poolname,
            },
            header=gettext('Users usage list'),
            water=gettext('UDS Report of users usage'),
        )


class UsageByPoolCSV(UsageByPool):
    filename = 'usage.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '5f7f0844-beb1-11e5-9a96-10feed05884b'
    encoded = False

    # Input fields
    pool = UsageByPool.pool
    startDate = UsageByPool.start_date
    endDate = UsageByPool.end_date

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        reportData = self.get_data()[0]

        writer.writerow(
            [
                gettext('Date'),
                gettext('User'),
                gettext('Seconds'),
                gettext('Pool'),
                gettext('Origin'),
            ]
        )

        for v in reportData:
            writer.writerow(
                [v['date'], v['name'], v['time'], v['pool_name'], v['origin']]
            )

        return output.getvalue().encode()
