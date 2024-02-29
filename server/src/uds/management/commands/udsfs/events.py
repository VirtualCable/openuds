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
import logging

from django.db.models import QuerySet

from uds.models import StatsEvents
from uds.core.util.stats.events import get_owner
from uds.core.types import stats as events_types

from . import types

logger = logging.getLogger(__name__)

LINELEN = 160


# Helper, returns a "pretty print" of an event
def pretty_print(event: StatsEvents) -> str:
    # convert unix timestamp to human readable
    dt = datetime.datetime.fromtimestamp(event.stamp)
    # Get owner, if it already exists
    owner = get_owner(events_types.EventOwnerType.from_int(event.owner_type), event.owner_id)
    name = getattr(owner, 'name', '') if hasattr(owner, 'name') else '[*Deleted*]'
    # Get event name
    event_name = events_types.EventType.from_int(event.event_type).event_name
    # Get event description
    return f'{dt} - {event_name} {name} - {event.fld1}|{event.fld2}|{event.fld3}|{event.fld3}'


class EventFS(types.UDSFSInterface):
    """
    Class to handle events fs in UDS.
    """

    _directory_stats: typing.ClassVar[types.StatType] = types.StatType(
        st_mode=(stat.S_IFDIR | 0o755), st_nlink=1
    )
    _months: typing.ClassVar[list[str]] = [
        '01',
        '02',
        '03',
        '04',
        '05',
        '06',
        '07',
        '08',
        '09',
        '10',
        '11',
        '12',
    ]

    def getattr(self, path: list[str]) -> types.StatType:
        if len(path) < 1:
            return EventFS._directory_stats

        years = EventFS.last_years()
        if len(path) >= 1 and path[0] not in years:
            raise FileNotFoundError('No such file or directory')
        if len(path) == 1:
            return EventFS._directory_stats  # Directory
        if len(path) >= 2 and path[1] in EventFS._months:
            if len(path) == 2:
                return EventFS._directory_stats
            if len(path) == 3 and int(path[2]) in range(
                1, EventFS.number_of_days(int(path[0]), int(path[1])) + 1
            ):
                size = LINELEN * EventFS.get_events(int(path[0]), int(path[1]), int(path[2]), 0).count()
                return types.StatType(st_mode=stat.S_IFREG | 0o444, st_size=size)

        raise FileNotFoundError('No such file or directory')

    def readdir(self, path: list[str]) -> list[str]:
        if len(path) == 0:
            # List ., .. and last 4 years as folders
            return ['.', '..'] + EventFS.last_years()
        last_years = EventFS.last_years()
        if len(path) >= 1 and path[0] in last_years:
            year = int(path[0])
            # Return months as folders
            if len(path) == 1:
                return ['.', '..'] + EventFS._months

            if len(path) == 2 and path[1] in EventFS._months:  # Return days of month as indicated on path
                month = int(path[1])
                return ['.', '..'] + [f'{x:02d}' for x in range(1, EventFS.number_of_days(year, month) + 1)]

        raise FileNotFoundError('No such file or directory')

    def read(self, path: list[str], size: int, offset: int) -> bytes:
        logger.debug('Reading events for %s: offset: %s, size: %s', path, offset, size)
        # Compose
        # Everly line is 256, calculate skip
        skip = offset // LINELEN
        # Calculate number of lines to read
        lines = size // LINELEN + 1
        # Read lines from get_events
        year, month, day = int(path[0]), int(path[1]), int(path[2])
        logger.debug(
            'Reading %a lines, skiping %s for day %s/%s/%s',
            lines,
            skip,
            year,
            month,
            day,
        )
        events = EventFS.get_events(year, month, day, skip)
        # Compose lines, adjsting each line length to LINELEN
        theLines = [pretty_print(x).encode('utf-8') for x in events[:lines]]
        # Adjust each line length to LINELEN (after encoding from utf8)
        theLines = [x + b' ' * (LINELEN - len(x) - 1) + b'\n' for x in theLines]
        # Return lines
        return b''.join(theLines)[offset : offset + size]

    @staticmethod
    def last_years() -> list[str]:
        return [str(x) for x in range(datetime.datetime.now().year - 4, datetime.datetime.now().year + 1)]

    @staticmethod
    def number_of_days(year: int, month: int) -> int:
        return calendar.monthrange(year, month)[1]

    # retrieve Events from a year as a list of events
    @staticmethod
    def get_events(year: int, month: int, day: int, skip: int = 0) -> QuerySet[StatsEvents]:
        # Calculate starting and ending stamp as unix timestamp from year and month
        start = calendar.timegm((year, month, day, 0, 0, 0, 0, 0, 0))
        end = calendar.timegm((year, month, day, 23, 59, 59, 0, 0, 0))
        logger.debug('Reading stats events from %s to %s, skiping %s first', start, end, skip)
        return StatsEvents.objects.filter(stamp__gte=start, stamp__lte=end).order_by('stamp')[skip:]
