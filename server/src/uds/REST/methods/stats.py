# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import datetime
import typing

from uds.core import types
from uds.REST import Handler, HelpPath
from uds import models
from uds.core.util.stats import counters

logger = logging.getLogger(__name__)


# Enclosed methods under /cache path
class Stats(Handler):
    authenticated = True
    needs_admin = True

    help_paths = [
        HelpPath('', 'Returns the last day usage statistics for all authenticators'),
    ]
    help_text = 'Provides access to usage statistics'

    def _usage_stats(self, since: datetime.datetime) -> dict[str, list[dict[str, typing.Any]]]:
        """
        Returns usage stats
        """
        auths: dict[str, list[dict[str, typing.Any]]] = {}
        for a in models.Authenticator.objects.all():
            services: typing.Optional[types.stats.AccumStat] = None
            userservices: typing.Optional[types.stats.AccumStat] = None
            stats: list[dict[str, typing.Any]] = []

            services_counter_iterator = counters.enumerate_accumulated_counters(
                interval_type=models.StatsCountersAccum.IntervalType.HOUR,
                counter_type=types.stats.CounterType.AUTH_SERVICES,
                owner_id=a.id,
                since=since,
                infer_owner_type_from=a,  # To infer the owner type
            )

            user_with_servicescount_iter = iter(
                counters.enumerate_accumulated_counters(
                    interval_type=models.StatsCountersAccum.IntervalType.HOUR,
                    counter_type=types.stats.CounterType.AUTH_USERS_WITH_SERVICES,
                    owner_id=a.id,
                    since=since,
                    infer_owner_type_from=a,  # To infer the owner type
                )
            )

            for user_counter in counters.enumerate_accumulated_counters(
                interval_type=models.StatsCountersAccum.IntervalType.HOUR,
                counter_type=types.stats.CounterType.AUTH_USERS,
                owner_id=a.id,
                since=since,
                infer_owner_type_from=a,  # To infer the owner type
            ):
                try:
                    while True:
                        services_counter = next(services_counter_iterator)
                        if services_counter.stamp >= user_counter.stamp:
                            break
                    if user_counter.stamp == services_counter.stamp:
                        services = services_counter
                except StopIteration:
                    pass

                try:
                    while True:
                        uservices_counter = next(user_with_servicescount_iter)
                        if uservices_counter.stamp >= user_counter.stamp:
                            break
                    if user_counter.stamp == uservices_counter.stamp:
                        userservices = uservices_counter
                except StopIteration:
                    pass

                # Update last seen date
                stats.append(
                    {
                        'stamp': user_counter.stamp,
                        'users': (
                            {'min': user_counter.min, 'max': user_counter.max, 'sum': user_counter.sum}
                            if user_counter
                            else None
                        ),
                        'services': (
                            {'min': services.min, 'max': services.max, 'sum': services.sum}
                            if services
                            else None
                        ),
                        'user_services': (
                            {'min': userservices.min, 'max': userservices.max, 'sum': userservices.sum}
                            if userservices
                            else None
                        ),
                    }
                )
            # print(len(stats), stats[-1], datetime.datetime.fromtimestamp(lastSeen), since)
            auths[a.uuid] = stats

        return auths

    def get(self) -> typing.Any:
        """
        Processes get method. Basically, clears & purges the cache, no matter what params
        """
        # Default returns usage stats for last day
        return self._usage_stats(datetime.datetime.now() - datetime.timedelta(days=1))