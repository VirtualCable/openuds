# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import time
import logging
import typing

from uds.core.util.config import GlobalConfig
from uds.core.util import singleton
from uds.models import StatsCounters, StatsCountersAccum
from uds.models import getSqlDatetime, getSqlDatetimeAsUnix
from uds.models import StatsEvents

if typing.TYPE_CHECKING:
    from django.db import models

logger = logging.getLogger(__name__)

FLDS_EQUIV: typing.Mapping[str, typing.Iterable[str]] = {
    'fld1': ('username', 'platform', 'duration'),
    'fld2': ('source', 'srcip', 'browser', 'sent'),
    'fld3': ('destination', 'dstip', 'received'),
    'fld4': ('uniqueid', 'tunnel'),
}

REVERSE_FLDS_EQUIV: typing.Mapping[str, str] = {
    i: fld for fld, aliases in FLDS_EQUIV.items() for i in aliases
}


class StatsManager(metaclass=singleton.Singleton):
    """
    Manager for statistics, so we can provide usefull info about platform usage

    Right now, we are going to provide an interface to "counter stats", that is, statistics
    that has counters (such as how many users is at a time active at platform, how many services
    are assigned, are in use, in cache, etc...
    """

    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'StatsManager':
        return StatsManager()  # Singleton pattern will return always the same instance

    def __doCleanup(self, model: typing.Type[typing.Union['StatsCounters', 'StatsEvents']]) -> None:
        minTime = time.mktime(
            (
                getSqlDatetime()
                - datetime.timedelta(days=GlobalConfig.STATS_DURATION.getInt())
            ).timetuple()
        )
        model.objects.filter(stamp__lt=minTime).delete()

    # Counter stats
    def addCounter(
        self,
        owner_type: int,
        owner_id: int,
        counterType: int,
        counterValue: int,
        stamp: typing.Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Adds a new counter stats to database.

        Args:

            owner_type: type of owner (integer, from internal tables)
            owner_id:  id of the owner
            counterType: The type of counter that will receive the value (look at uds.core.util.stats.counters module)
            counterValue: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:

            Nothing
        """
        if stamp is None:
            stamp = typing.cast(datetime.datetime, getSqlDatetime())

        # To Unix epoch
        stampInt = int(
            time.mktime(stamp.timetuple())
        )  # pylint: disable=maybe-no-member

        try:
            StatsCounters.objects.create(
                owner_type=owner_type,
                owner_id=owner_id,
                counter_type=counterType,
                value=counterValue,
                stamp=stampInt,
            )
            return True
        except Exception:
            logger.error(
                'Exception handling counter stats saving (maybe database is full?)'
            )
        return False

    def getCounters(
        self,
        ownerType: int,
        counterType: int,
        ownerIds: typing.Union[typing.Iterable[int], int, None],
        since: datetime.datetime,
        to: datetime.datetime,
        interval: typing.Optional[int],
        max_intervals: typing.Optional[int],
        limit: typing.Optional[int],
        use_max: bool = False,
    ) -> typing.Iterable:
        """
        Retrieves counters from item

        Args:

            counterTye: Type of counter to get values
            counterId: (optional), if specified, limit counter to only this id, all ids for specidied type if not
            maxElements: (optional) Maximum number of elements to retrieve, all if nothing specified
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified

        Returns:

            Iterator, containing (date, counter) each element
        """
        # To Unix epoch
        sinceInt = int(time.mktime(since.timetuple()))
        toInt = int(time.mktime(to.timetuple()))

        return StatsCounters.get_grouped(
            ownerType,
            counterType,
            owner_id=ownerIds,
            since=sinceInt,
            to=toInt,
            interval=interval,
            max_intervals=max_intervals,
            limit=limit,
            use_max=use_max,
        )

    def cleanupCounters(self):
        """
        Removes all counters previous to configured max keep time for stat information from database.
        """
        self.__doCleanup(StatsCounters)

    def getEventFldFor(self, fld: str) -> str:
        '''
        Get equivalency between "cool names" and field. Will raise "KeyError" if no equivalency
        '''
        return REVERSE_FLDS_EQUIV[fld]

    # Event stats
    def addEvent(self, owner_type: int, owner_id: int, eventType: int, **kwargs):
        """
        Adds a new event stat to database.

        stamp=None, fld1=None, fld2=None, fld3=None
        Args:

            toWhat: if of the counter
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:

            Nothing
        """
        logger.debug('Adding event stat')
        stamp = kwargs.get('stamp')
        if stamp is None:
            stamp = getSqlDatetimeAsUnix()
        else:
            # To Unix epoch
            stamp = int(
                time.mktime(stamp.timetuple())
            )  # pylint: disable=maybe-no-member

        try:

            def getKwarg(fld: str) -> str:
                val = kwargs.get(fld)
                if val is None:
                    for i in FLDS_EQUIV[fld]:
                        val = kwargs.get(i)
                        if val is not None:
                            break
                return val or ''

            fld1 = getKwarg('fld1')
            fld2 = getKwarg('fld2')
            fld3 = getKwarg('fld3')
            fld4 = getKwarg('fld4')

            StatsEvents.objects.create(
                owner_type=owner_type,
                owner_id=owner_id,
                event_type=eventType,
                stamp=stamp,
                fld1=fld1,
                fld2=fld2,
                fld3=fld3,
                fld4=fld4,
            )
            return True
        except Exception:
            logger.exception(
                'Exception handling event stats saving (maybe database is full?)'
            )
        return False

    def getEvents(
        self,
        ownerType: typing.Union[int, typing.Iterable[int]],
        eventType: typing.Union[int, typing.Iterable[int]],
        **kwargs
    ) -> 'models.QuerySet[StatsEvents]':
        """
        Retrieves counters from item

        Args:

            ownerType: Type of counter to get values
            eventType:
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified

        Returns:

            Iterator, containing (date, counter) each element
        """
        return StatsEvents.get_stats(ownerType, eventType, **kwargs)

    def tailEvents(
        self,
        *,
        fromId: typing.Optional[str] = None,
        number: typing.Optional[int] = None
    ) -> 'models.QuerySet[StatsEvents]':
        # If number is not specified, we return five last events
        number = number or 5
        if fromId:
            return StatsEvents.objects.filter(id__gt=fromId).order_by('-id')[:number]  # type: ignore  # Slicing is not supported by pylance right now
        return StatsEvents.objects.order_by('-id')[:number]  # type: ignore  # Slicing is not supported by pylance right now

    def cleanupEvents(self):
        """
        Removes all events previous to configured max keep time for stat information from database.
        """

        self.__doCleanup(StatsEvents)

    def acummulate(self, max_days: int = 7):
        for interval in StatsCountersAccum.IntervalType:
            StatsCountersAccum.acummulate(interval, max_days)
