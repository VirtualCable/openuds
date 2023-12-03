# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import typing
import collections.abc
import logging

from django.utils.translation import gettext, gettext_lazy as _

from .usage_by_pool import UsageByPool

logger = logging.getLogger(__name__)


class PoolsUsageSummary(UsageByPool):
    filename = 'summary_pools_usage.pdf'
    name = _('Summary of pools usage')  # Report name
    description = _(
        'Summary of Pools usage with time totals, accesses totals, time total by pool'
    )  # Report description
    uuid = 'aba55fe5-c4df-5240-bbe6-36340220cb5d'

    # Input fields
    pool = UsageByPool.pool
    startDate = UsageByPool.startDate
    endDate = UsageByPool.endDate

    def processedData(
        self,
    ) -> typing.Tuple[
        typing.ValuesView[typing.MutableMapping[str, typing.Any]], int, int, int
    ]:
        orig, poolNames = super().getData()  # pylint: disable=unused-variable  # Keep name for reference

        pools: dict[str, dict] = {}
        totalTime: int = 0
        totalCount: int = 0

        uniqueUsers = set()

        for v in orig:
            uuid = v['pool']
            if uuid not in pools:
                pools[uuid] = {
                    'name': v['pool_name'],
                    'time': 0,
                    'count': 0,
                    'users': set(),
                }
            pools[uuid]['time'] += v['time']
            pools[uuid]['count'] += 1
            # Now add user id to pool
            pools[uuid]['users'].add(v['name'])
            uniqueUsers.add(v['name'])

            totalTime += v['time']
            totalCount += 1

        logger.debug('Pools %s', pools)
        # Remove unique users, and keep only counts...
        for _, pn in pools.items():
            pn['users'] = len(pn['users'])

        return pools.values(), totalTime, totalCount or 1, len(uniqueUsers)

    def generate(self):
        pools, totalTime, totalCount, uniqueUsers = self.processedData()

        start = self.startDate.value
        end = self.endDate.value

        logger.debug('Pools: %s --- %s  --- %s', pools, totalTime, totalCount)

        return self.templateAsPDF(
            'uds/reports/stats/pools-usage-summary.html',
            dct={
                'data': (
                    {
                        'name': p['name'],
                        'time': str(datetime.timedelta(seconds=p['time'])),
                        'count': p['count'],
                        'users': p['users'],
                        'mean': str(
                            datetime.timedelta(seconds=p['time'] // int(p['count']))
                        ),
                    }
                    for p in pools
                ),
                'time': str(datetime.timedelta(seconds=totalTime)),
                'count': totalCount,
                'users': uniqueUsers,
                'mean': str(datetime.timedelta(seconds=totalTime // totalCount)),
                'start': start,
                'end': end,
            },
            header=gettext('Summary of Pools usage')
            + ' '
            + start
            + ' '
            + gettext('to')
            + ' '
            + end,
            water=gettext('UDS Report Summary of pools usage'),
        )


class PoolsUsageSummaryCSV(PoolsUsageSummary):
    filename = 'summary_pools_usage.csv'
    mime_type = 'text/csv'  # Report returns pdfs by default, but could be anything else
    uuid = '811b1261-82c4-524e-b1c7-a4b7fe70050f'
    encoded = False

    # Input fields
    pool = PoolsUsageSummary.pool
    startDate = PoolsUsageSummary.startDate
    endDate = PoolsUsageSummary.endDate

    def generate(self):
        output = io.StringIO()
        writer = csv.writer(output)

        reportData, totalTime, totalCount, totalUsers = self.processedData()

        writer.writerow(
            [
                gettext('Pool'),
                gettext('Total Time (seconds)'),
                gettext('Total Accesses'),
                gettext('Unique users'),
                gettext('Mean time (seconds)'),
            ]
        )

        for v in reportData:
            writer.writerow(
                [v['name'], v['time'], v['count'], v['users'], v['time'] // v['count']]
            )

        writer.writerow(
            [
                gettext('Total'),
                totalTime,
                totalCount,
                totalUsers,
                totalTime // totalCount,
            ]
        )

        return output.getvalue()
