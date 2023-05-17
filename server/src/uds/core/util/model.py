# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging
from threading import Lock
import datetime
from time import mktime

from django.db import connection, models

from uds.models import consts
from uds.core.managers.crypto import CryptoManager

logger = logging.getLogger(__name__)

CACHE_TIME_TIMEOUT = 60 # Every 60 second, refresh the time from database (to avoid drifts)


# pylint: disable=too-few-public-methods
class TimeTrack:
    """
    Reduces the queries to database to get the current time
    keeping it cached for CACHE_TIME_TIMEOUT seconds (and adjusting it based on local time)
    """
    lock: typing.ClassVar[Lock] = Lock()
    last_check: typing.ClassVar[datetime.datetime] = consts.NEVER
    cached_time: typing.ClassVar[datetime.datetime] = consts.NEVER
    hits: typing.ClassVar[int] = 0
    misses: typing.ClassVar[int] = 0

    @staticmethod
    def _fetchSqlDatetime() -> datetime.datetime:
        """Returns the current date/time of the database server.

        We use this time as method to keep all operations betwen different servers in sync.

        We support get database datetime for:
        * mysql
        * sqlite

        Returns:
            datetime: Current datetime of the database server
        """
        if connection.vendor in ('mysql', 'microsoft'):
            cursor = connection.cursor()
            sentence = (
                'SELECT CURRENT_TIMESTAMP(4)' if connection.vendor == 'mysql' else 'SELECT CURRENT_TIMESTAMP'
            )
            cursor.execute(sentence)
            date = (cursor.fetchone() or [datetime.datetime.now()])[0]
        else:
            date = (
                datetime.datetime.now()
            )  # If not know how to get database datetime, returns local datetime (this is fine for sqlite, which is local)

        return date

    @staticmethod
    def getSqlDatetime() -> datetime.datetime:
        now = datetime.datetime.now()
        with TimeTrack.lock:
            diff = now - TimeTrack.last_check
            # If in last_check is in the future, or more than CACHE_TIME_TIMEOUT seconds ago, we need to refresh
            # Future is possible if we have a clock update, or a big drift
            if diff > datetime.timedelta(seconds=CACHE_TIME_TIMEOUT) or diff < datetime.timedelta(seconds=0):
                TimeTrack.last_check = now
                TimeTrack.misses += 1
                TimeTrack.cached_time = TimeTrack._fetchSqlDatetime()
            else:
                TimeTrack.hits += 1
        return TimeTrack.cached_time + (now - TimeTrack.last_check)


# pylint: disable=too-few-public-methods
class UnsavedForeignKey(models.ForeignKey):
    """
    From 1.8 of django, we need to point to "saved" objects.
    If dont, will raise an InvalidValue exception.

    We need to trick in some cases, because for example, root user is not in DB
    """

    # Allows pointing to an unsaved object
    # allow_unsaved_instance_assignment = True


def getSqlDatetime() -> datetime.datetime:
    """Returns the current date/time of the database server.
    Has been updated to use TimeTrack, which reduces the queries to database to get the current time
    """
    return TimeTrack.getSqlDatetime()


def getSqlDatetimeAsUnix() -> int:
    """Returns the current date/time of the database server as unix timestamp

    Returns:
        int: Unix timestamp
    """
    return int(mktime(getSqlDatetime().timetuple()))

def generateUuid(obj: typing.Any = None) -> str:
    """
    Generates a ramdom uuid for models default
    """
    return CryptoManager().uuid(obj=obj).lower()


def processUuid(uuid: str) -> str:
    if isinstance(uuid, bytes):
        uuid = uuid.decode('utf8')  # type: ignore
    return uuid.lower()
