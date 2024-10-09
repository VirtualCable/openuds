# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import collections.abc
import datetime
import typing

from uds import models
from uds.core import types
from uds.core.util.stats import counters


def create_stats_counters(
    owner_type: types.stats.CounterOwnerType,
    owner_id: int,
    counter_type: types.stats.CounterType,
    since: datetime.datetime,
    to: datetime.datetime,
    number: typing.Optional[int] = None,
    interval: typing.Optional[int] = None,
) -> list[models.StatsCounters]:
    '''
    Create a list of counters with the given type, counter_type, since and to, save it in the database
    and return it
    '''
    # Convert datetime to unix timestamp
    since_stamp = int(since.timestamp())
    to_stamp = int(to.timestamp())

    # Calculate the time interval between each counter
    if number is None:
        if interval is None:
            raise ValueError('Either number or interval must be provided')
        number = (to_stamp - since_stamp) // interval
    interval = (to_stamp - since_stamp) // number

    counters = [
        models.StatsCounters(
            owner_id=owner_id,
            owner_type=owner_type,
            counter_type=counter_type,
            stamp=since_stamp + interval * i,
            value=i*10,
        )
        for i in range(number)
    ]
    # Bulk create the counters
    models.StatsCounters.objects.bulk_create(counters)
    return counters


def create_stats_interval_total(
    id: int,
    counter_type: list[types.stats.CounterType],
    since: datetime.datetime,
    days: int,
    number_per_hour: int,
    value: typing.Union[int, collections.abc.Callable[[int, int], int]],
    owner_type: int = counters.types.stats.CounterOwnerType.SERVICEPOOL,
) -> list[models.StatsCounters]:
    '''
    Creates a list of counters with the given type, counter_type, since and to, save it in the database
    and return it
    '''
    # Calculate the time interval between each counter
    # Ensure number_per hour fix perfectly in an hour
    if 3600 % number_per_hour != 0:
        raise ValueError('Number of counters per hour must be a divisor of 3600')

    interval = 3600 // number_per_hour

    since_stamp = int(since.timestamp())

    if isinstance(value, int):
        xv = value
        value = lambda x, y: xv

    cntrs = [
        models.StatsCounters(
            owner_id=id,
            owner_type=owner_type,
            counter_type=ct,
            stamp=since_stamp + interval * i,
            value=value(i, ct),
        ) for ct in counter_type for i in range(days * 24 * number_per_hour)
    ]

    # Bulk create the counters
    models.StatsCounters.objects.bulk_create(cntrs)
    return cntrs
