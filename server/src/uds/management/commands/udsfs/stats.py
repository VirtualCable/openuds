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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import stat
import calendar
import datetime
import typing
import collections.abc
import logging

from uds import models
from uds.core.util.cache import Cache

from . import types


logger = logging.getLogger(__name__)


# Custom types
class StatInterval(typing.NamedTuple):
    start: datetime.datetime
    end: datetime.datetime

    @property
    def start_timestamp(self) -> int:
        return calendar.timegm(self.start.timetuple())

    @property
    def end_timestamp(self) -> int:
        return calendar.timegm(self.end.timetuple())


class VirtualFileInfo(typing.NamedTuple):
    name: str
    size: int
    mtime: int

    # Cache stamp
    stamp: int = -1


# Dispatcher needs an Interval, an extensio, the size and the offset
DispatcherType = collections.abc.Callable[[StatInterval, str, int, int], bytes]


class StatsFS(types.UDSFSInterface):
    """
    Class to handle stats fs in UDS.
    """

    _directory_stats: typing.ClassVar[types.StatType] = types.StatType(
        st_mode=(stat.S_IFDIR | 0o755), st_nlink=1
    )
    # Dictionary containing a mapping between a relative day and the corresponding
    # today start timestamp + first element of tuple, today start timestamp + second element of tuple
    _interval: typing.ClassVar[collections.abc.Mapping[str, tuple[datetime.timedelta, datetime.timedelta]]] = {
        'today': (
            datetime.timedelta(days=0),
            datetime.timedelta(days=1),
        ),
        'yesterday': (
            datetime.timedelta(days=-1),
            datetime.timedelta(days=0),
        ),
        'lastweek': (
            datetime.timedelta(days=-7),
            datetime.timedelta(days=0),
        ),
        'lastmonth': (
            datetime.timedelta(days=-30),
            datetime.timedelta(days=0),
        ),
    }

    _dispatchers: collections.abc.Mapping[str, tuple[DispatcherType, bool]]
    _cache: typing.ClassVar[Cache] = Cache('fsevents')

    def __init__(self) -> None:
        # Initialize _dispatchers, Second element of tuple is True if the dispatcher has "intervals"
        self._dispatchers = {
            'events': (self._read_events, True),
            'pools': (self._read_pools, False),
            'auths': (self._read_auths, False),
        }

    # Splits the filename and returns a tuple with "dispatcher", "interval", "extension"
    def getFilenameComponents(
        self, filename: list[str]
    ) -> tuple[DispatcherType, StatInterval, str]:
        if len(filename) != 1:
            raise FileNotFoundError()

        # Extract components
        try:
            dispatcher, interval, extension = (filename[0].split('.') + [''])[:3]
        except ValueError:
            raise FileNotFoundError() from None

        logger.debug(
            'Dispatcher: %s, interval: %s, extension: %s',
            dispatcher,
            interval,
            extension,
        )

        if dispatcher not in self._dispatchers:
            raise FileNotFoundError()

        fnc, requiresInterval = self._dispatchers[dispatcher]

        if extension == '' and requiresInterval is True:
            raise FileNotFoundError()

        if requiresInterval:
            if interval not in self._interval:
                raise FileNotFoundError()

            range = self._interval[interval]
        else:
            range = StatsFS._interval['lastmonth']  # Any value except "today" will do the trick
            extension = interval

        if extension != 'csv':
            raise FileNotFoundError()

        todayStart = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            fnc,
            StatInterval(
                start=todayStart + range[0],
                end=todayStart + range[1],
            ),
            extension,
        )

    def readdir(self, path: list[str]) -> list[str]:
        # If len(path) == 0, return the list of possible stats files (from _dispatchers)
        # else, raise an FileNotFoundError
        if len(path) == 0:
            return (
                ['.', '..']
                + [
                    f'{dispatcher}.{interval}.csv'
                    for dispatcher in filter(lambda x: self._dispatchers[x][1], self._dispatchers)
                    for interval in self._interval
                ]
                + [
                    f'{dispatcher}.csv'
                    for dispatcher in filter(lambda x: self._dispatchers[x][1] is False, self._dispatchers)
                ]
            )

        raise FileNotFoundError

    def getattr(self, path: list[str]) -> types.StatType:
        logger.debug('Getting attributes for %s', path)
        # stats folder
        if len(path) == 0:
            return self._directory_stats

        dispatcher, interval, extension = self.getFilenameComponents(path)

        # if interval is today, cache time is 10 seconds, else cache time is 60 seconds
        if interval == StatsFS._interval['today']:
            cacheTime = 10
        else:
            cacheTime = 60

        # Check if the file info is cached
        cached = self._cache.get(path[0] + extension)
        if cached is not None:
            logger.debug('Cache hit for %s', path[0])
            data = cached
        else:
            logger.debug('Cache miss for %s', path[0])
            data = dispatcher(interval, extension, 0, 0)
            self._cache.put(path[0] + extension, data, cacheTime)

        # Calculate the size of the file
        size = len(data)
        logger.debug('Size of %s: %s', path[0], size)

        return types.StatType(
            st_mode=(stat.S_IFREG | 0o755),
            st_nlink=1,
            st_size=size,
            st_mtime=interval.start_timestamp,
        )

    def read(self, path: list[str], size: int, offset: int) -> bytes:
        logger.debug('Reading data from %s: offset: %s, size: %s', path, offset, size)

        dispatcher, interval, extension = self.getFilenameComponents(path)

        # if interval is today, cache time is 10 seconds, else cache time is 60 seconds
        if interval == StatsFS._interval['today']:
            cacheTime = 10
        else:
            cacheTime = 60

        # Check if the file info is cached
        cached = self._cache.get(path[0] + extension)
        if cached is not None:
            logger.debug('Cache hit for %s', path[0])
            data = cached
        else:
            logger.debug('Cache miss for %s', path[0])
            data = dispatcher(interval, extension, 0, 0)
            self._cache.put(path[0] + extension, data, cacheTime)

        # Dispatch the read to the dispatcher
        data = dispatcher(interval, extension, size, offset)
        logger.debug('Readed %s data length', len(data))
        return data[offset : offset + size]

    # Dispatchers for different stats files
    def _read_events(self, interval: StatInterval, extension: str, size: int, offset: int) -> bytes:
        logger.debug(
            'Reading events. Interval=%s, extension=%s, offset=%s, size=%s',
            interval,
            extension,
            offset,
            size,
        )
        # Get stats events from last 24 hours (in UTC) stamp is unix timestamp
        virtualFile = models.StatsEvents.get_csv_header().encode() + b'\n'
        # stamp is unix timestamp
        for record in models.StatsEvents.objects.filter(
            stamp__gte=interval.start_timestamp, stamp__lte=interval.end_timestamp
        ):
            virtualFile += record.as_csv().encode() + b'\n'

        return virtualFile

    def _read_pools(self, interval: StatInterval, extension: str, size: int, offset: int) -> bytes:
        logger.debug(
            'Reading pools. Interval=%s, extension=%s, offset: %s, size: %s',
            interval,
            extension,
            offset,
            size,
        )
        # Compose the csv file from what we now of service pools
        virtualFile = models.ServicePool.get_cvs_header().encode() + b'\n'
        # First, get the list of service pools
        for pool in models.ServicePool.objects.all().order_by('name'):
            virtualFile += pool.as_cvs().encode() + b'\n'
        return virtualFile

    def _read_auths(self, interval: StatInterval, extension: str, size: int, offset: int) -> bytes:
        logger.debug(
            'Reading auths. Interval=%s, extension=%s, offset: %s, size: %s',
            interval,
            extension,
            offset,
            size,
        )
        # Compose the csv file from what we now of service pools
        virtualFile = models.Authenticator.get_cvs_header().encode() + b'\n'
        # First, get the list of service pools
        for auth in models.Authenticator.objects.all().order_by('name'):
            virtualFile += auth.to_csv().encode() + b'\n'
        return virtualFile
