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
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import ui
from uds.core.managers.stats import StatsManager
from uds.core.ui import gui
from uds.core.util.stats import events
from uds.models import ServicePool

from .base import StatsReport

logger = logging.getLogger(__name__)


class UsageSummaryByUsersPool(StatsReport):
    filename = 'pool_user_usage.pdf'
    name = _('Pool Usage by users')  # Report name
    description = _('Generates a report with the summary of users usage for a pool')  # Report description
    uuid = '202c6438-30a8-11e7-80e4-77c1e4cb9e09'

    # UserInterface will ignore all fields that are not from FINAL class
    # so we must redeclare them here
    pool = ui.gui.ChoiceField(
        order=1,
        label=_('Pool'),
        tooltip=_('Pool for report'),
        required=True,
    )

    start_date = StatsReport.start_date
    end_date = StatsReport.end_date

    def init_gui(self) -> None:
        logger.debug('Initializing gui')
        vals = [gui.choice_item(v.uuid, v.name) for v in ServicePool.objects.all()]
        self.pool.set_choices(vals)

    def get_pool_data(self, pool: 'ServicePool') -> tuple[list[dict[str, typing.Any]], str]:
        start = self.start_date.as_timestamp()
        end = self.end_date.as_timestamp()
        logger.debug(self.pool.value)

        items = (
            StatsManager.manager()
            .enumerate_events(
                events.types.stats.EventOwnerType.SERVICEPOOL,
                (events.types.stats.EventType.LOGIN, events.types.stats.EventType.LOGOUT),
                owner_id=pool.id,
                since=start,
                to=end,
            )
            .order_by('stamp')
        )

        logins: dict[str, int] = {}
        users: dict[str, dict[str, typing.Any]] = {}
        for i in items:
            # if '\\' in i.fld1:
            #    continue
            username = i.fld4
            if i.event_type == events.types.stats.EventType.LOGIN:
                logins[username] = i.stamp
            else:
                if username in logins:
                    stamp = logins[username]
                    del logins[username]
                    total = i.stamp - stamp
                    if username not in users:
                        users[username] = {'sessions': 0, 'time': 0}
                    users[username]['sessions'] += 1
                    users[username]['time'] += total
                    # data.append({
                    #    'name': i.fld4,
                    #    'date': datetime.datetime.fromtimestamp(stamp),
                    #    'time': total
                    # })

        # Extract different number of users
        data = [
            {
                'user': k,
                'sessions': v['sessions'],
                'hours': '{:.2f}'.format(float(v['time']) / 3600),
                'average': '{:.2f}'.format(float(v['time']) / 3600 / v['sessions']),
            }
            for k, v in users.items()
        ]

        return data, pool.name

    def get_data(self) -> tuple[list[dict[str, typing.Any]], str]:
        return self.get_pool_data(ServicePool.objects.get(uuid=self.pool.value))

    def generate(self) -> bytes:
        items, pool_name = self.get_data()

        return self.template_as_pdf(
            'uds/reports/stats/pool-users-summary.html',
            dct={
                'data': items,
                'pool': pool_name,
                'beginning': self.start_date.as_date(),
                'ending': self.end_date.as_date(),
            },
            header=gettext('Users usage list for {}').format(pool_name),
            water=gettext('UDS Report of users in {}').format(pool_name),
        )


class UsageSummaryByUsersPoolCSV(UsageSummaryByUsersPool):
    filename = 'usage.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '302e1e76-30a8-11e7-9d1e-6762bbf028ca'
    encoded = False

    # Input fields
    pool = UsageSummaryByUsersPool.pool
    start_date = UsageSummaryByUsersPool.start_date
    end_date = UsageSummaryByUsersPool.end_date

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        report_data = self.get_data()[0]

        writer.writerow(
            [
                gettext('User'),
                gettext('Sessions'),
                gettext('Hours'),
                gettext('Average'),
            ]
        )

        for v in report_data:
            writer.writerow([v['user'], v['sessions'], v['hours'], v['average']])

        return output.getvalue().encode()
