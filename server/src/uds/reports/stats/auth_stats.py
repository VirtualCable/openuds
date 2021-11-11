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
import logging
import typing

from django.utils.translation import ugettext, ugettext_lazy as _

from uds.core.ui import gui
from uds.core.util.stats import counters

from .base import StatsReportAuto

if typing.TYPE_CHECKING:
    from uds import models


logger = logging.getLogger(__name__)

MAX_ELEMENTS = 10000


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

    def generate(self) -> typing.Any:
        since = self.date_start.date()
        to = self.date_end.date()
        interval = self.getIntervalInHours() * 3600

        stats = []
        for a in self.getModelItems():
            # Will show a.name on every change...
            stats.append({'date': a.name, 'users': None})

            services = 0
            userServices = 0
            servicesCounterIter = iter(
                counters.getCounters(
                    typing.cast('models.Authenticator', a),
                    counters.CT_AUTH_SERVICES,
                    since=since,
                    to=to,
                    interval=interval,
                    limit=MAX_ELEMENTS,
                    use_max=True,
                )
            )
            usersWithServicesCounterIter = iter(
                counters.getCounters(
                    typing.cast('models.Authenticator', a),
                    counters.CT_AUTH_USERS_WITH_SERVICES,
                    since=since,
                    to=to,
                    interval=interval,
                    limit=MAX_ELEMENTS,
                    use_max=True,
                )
            )
            for userCounter in counters.getCounters(
                typing.cast('models.Authenticator', a),
                counters.CT_AUTH_USERS,
                since=since,
                to=to,
                interval=interval,
                limit=MAX_ELEMENTS,
                use_max=True,
            ):
                try:
                    while True:
                        servicesCounter = next(servicesCounterIter)
                        if servicesCounter[0] >= userCounter[0]:
                            break
                    if userCounter[0] == servicesCounter[0]:
                        services = servicesCounter[1]
                except StopIteration:
                    pass

                try:
                    while True:
                        uservicesCounter = next(usersWithServicesCounterIter)
                        if uservicesCounter[0] >= userCounter[0]:
                            break
                    if userCounter[0] == uservicesCounter[0]:
                        userServices = uservicesCounter[1]
                except StopIteration:
                    pass

                stats.append(
                    {
                        'date': userCounter[0],
                        'users': userCounter[1] or 0,
                        'services': services,
                        'user_services': userServices,
                    }
                )
        logger.debug('Report Data Done')
        return self.templateAsPDF(
            'uds/reports/stats/authenticator_stats.html',
            dct={'data': stats},
            header=ugettext('Users usage list'),
            water=ugettext('UDS Report of users usage'),
        )
