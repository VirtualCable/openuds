# -*- coding: utf-8 -*-

#
# Copyright (c) 2020 Virtual Cable S.L.
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
import io
import csv
import datetime
import typing
import logging

from django.utils.translation import ugettext, ugettext_lazy as _

from .usage_by_pool import UsageByPool

logger = logging.getLogger(__name__)

class PoolsUsageSummary(UsageByPool):
    filename = 'summary_pools_usage.pdf'
    name = _('Summary of pools usage')  # Report name
    description = _('Summary of Pools usage with time totals, accesses totals, time total by pool')  # Report description
    uuid = 'aba55fe5-c4df-5240-bbe6-36340220cb5d'

    # Input fields
    pool = UsageByPool.pool
    startDate = UsageByPool.startDate
    endDate = UsageByPool.endDate

    def getData(self):
        orig, poolNames = super().getData()

        pools: typing.Dict[str, typing.Dict] = {}
        totalTime: int = 0
        totalCount: int = 0

        for v in orig:
            uuid = v['pool']
            if uuid not in pools:
                pools[uuid] = {
                    'name': v['pool_name'],
                    'time': 0,
                    'count': 0
                }
            logger.debug('V: %s', v)
            pools[uuid]['time'] += v['time']
            pools[uuid]['count'] += 1

            totalTime += v['time']
            totalCount += 1

        logger.debug('Pools: \n%s\n', pools)

        return pools.values(), totalTime, totalCount

    def generate(self):
        pools, totalTime, totalCount = self.getData()

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
                        'count': p['count']
                    }
                    for p in pools
                ),
                'time': str(datetime.timedelta(seconds=totalTime)),
                'count': totalCount,
                'start': start,
                'end': end,
            },
            header=ugettext('Summary of Pools usage') + ' ' + start + ' ' + ugettext('to') + ' ' + end,
            water=ugettext('UDS Report Summary of pools usage')
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

        reportData, totalTime, totalCount = self.getData()

        writer.writerow([ugettext('Pool'), ugettext('Total Time (seconds)'), ugettext('Total Accesses')])

        for v in reportData:
            writer.writerow([v['name'], v['time'], v['count']])

        writer.writerow([ugettext('Total'), totalTime, totalCount])

        return output.getvalue()
