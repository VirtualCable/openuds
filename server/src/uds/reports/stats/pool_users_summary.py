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

from uds.core.ui import gui
from uds.core.util.stats import events
from uds.core.managers.stats import StatsManager
from uds.models import ServicePool

from .base import StatsReport

logger = logging.getLogger(__name__)


class UsageSummaryByUsersPool(StatsReport):
    filename = 'pool_user_usage.pdf'
    name = _('Pool Usage by users')  # Report name
    description = _(
        'Generates a report with the summary of users usage for a pool'
    )  # Report description
    uuid = '202c6438-30a8-11e7-80e4-77c1e4cb9e09'

    # Input fields
    pool = gui.ChoiceField(
        order=1, label=_('Pool'), tooltip=_('Pool for report'), required=True
    )

    startDate = gui.DateField(
        order=2,
        label=_('Starting date'),
        tooltip=_('starting date for report'),
        defvalue=datetime.date.min,
        required=True,
    )

    endDate = gui.DateField(
        order=3,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        defvalue=datetime.date.max,
        required=True,
    )

    def initGui(self) -> None:
        logger.debug('Initializing gui')
        vals = [gui.choiceItem(v.uuid, v.name) for v in ServicePool.objects.all()]
        self.pool.setValues(vals)

    def getPoolData(
        self, pool
    ) -> typing.Tuple[typing.List[typing.Dict[str, typing.Any]], str]:
        start = self.startDate.stamp()
        end = self.endDate.stamp()
        logger.debug(self.pool.value)

        items = (
            StatsManager.manager()
            .getEvents(
                events.OT_SERVICEPOOL,
                (events.ET_LOGIN, events.ET_LOGOUT),
                owner_id=pool.id,
                since=start,
                to=end,
            )
            .order_by('stamp')
        )

        logins: typing.Dict[str, int] = {}
        users: typing.Dict[str, typing.Dict] = {}
        for i in items:
            # if '\\' in i.fld1:
            #    continue
            username = i.fld4
            if i.event_type == events.ET_LOGIN:
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

    def getData(self) -> typing.Tuple[typing.List[typing.Dict[str, typing.Any]], str]:
        return self.getPoolData(ServicePool.objects.get(uuid=self.pool.value))

    def generate(self) -> bytes:
        items, poolName = self.getData()

        return self.templateAsPDF(
            'uds/reports/stats/pool-users-summary.html',
            dct={
                'data': items,
                'pool': poolName,
                'beginning': self.startDate.date(),
                'ending': self.endDate.date(),
            },
            header=gettext('Users usage list for {}').format(poolName),
            water=gettext('UDS Report of users in {}').format(poolName),
        )


class UsageSummaryByUsersPoolCSV(UsageSummaryByUsersPool):
    filename = 'usage.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '302e1e76-30a8-11e7-9d1e-6762bbf028ca'
    encoded = False

    # Input fields
    pool = UsageSummaryByUsersPool.pool
    startDate = UsageSummaryByUsersPool.startDate
    endDate = UsageSummaryByUsersPool.endDate

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        reportData = self.getData()[0]

        writer.writerow(
            [
                gettext('User'),
                gettext('Sessions'),
                gettext('Hours'),
                gettext('Average'),
            ]
        )

        for v in reportData:
            writer.writerow([v['user'], v['sessions'], v['hours'], v['average']])

        return output.getvalue().encode()
