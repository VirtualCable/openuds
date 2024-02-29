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
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _

from uds.core.util.stats import counters

from .base import StatsReportAuto

if typing.TYPE_CHECKING:
    from uds import models


logger = logging.getLogger(__name__)

MAX_ELEMENTS = 10000
BIG_INTERVAL = 3600 * 24 * 30 * 12  # 12 months


class AuthenticatorsStats(StatsReportAuto):
    dates = 'range'
    intervals = True
    data_source = 'Authenticator'
    multiple = True

    filename = 'auths_stats.pdf'
    name = _('Statistics by authenticator')  # Report name
    description = _(
        'Generates a report with the statistics of an authenticator for a desired period'
    )  # Report description
    uuid = 'a5a43bc0-d543-11ea-af8f-af01fa65994e'

    def generate(self) -> bytes:

        stats: list[dict[str, typing.Any]] = []
        for a in self.get_model_records():
            # Will show a.name on every change...
            stats.append({'date': a.name, 'users': None})

            for i in self.getIntervalsList():
                start = i[0]
                end = i[1]
                data = [0, 0, 0]
                # Get stats for interval
                for counter in counters.enumerate_counters(
                    typing.cast('models.Authenticator', a),
                    counters.types.stats.CounterType.AUTH_SERVICES,
                    since=start,
                    to=end,
                    interval=BIG_INTERVAL,
                    limit=MAX_ELEMENTS,
                    use_max=True,
                ):
                    data[0] += counter[1]

                for counter in counters.enumerate_counters(
                    typing.cast('models.Authenticator', a),
                    counters.types.stats.CounterType.AUTH_USERS_WITH_SERVICES,
                    since=start,
                    to=end,
                    interval=BIG_INTERVAL,
                    limit=MAX_ELEMENTS,
                    use_max=True,
                ):
                    data[1] += counter[1]
                for counter in counters.enumerate_counters(
                    typing.cast('models.Authenticator', a),
                    counters.types.stats.CounterType.AUTH_USERS,
                    since=start,
                    to=end,
                    interval=BIG_INTERVAL,
                    limit=MAX_ELEMENTS,
                    use_max=True,
                ):
                    data[2] += counter[1]

                stats.append(
                    {
                        'date': self.formatDatetimeAsString(start),
                        'users': data[0],
                        'services': data[1],
                        'user_services': data[2],
                    }
                )
        logger.debug('Report Data Done')
        return self.template_as_pdf(
            'uds/reports/stats/authenticator_stats.html',
            dct={'data': stats},
            header=gettext('Users usage list'),
            water=gettext('UDS Report of users usage'),
        )
