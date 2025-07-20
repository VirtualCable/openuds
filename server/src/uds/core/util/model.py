# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import typing
import logging
from threading import Lock
import datetime
from time import mktime

from django.db import connection

from uds.core import consts
from uds.core.managers.crypto import CryptoManager

logger = logging.getLogger(__name__)

CACHE_TIME_TIMEOUT = 60  # Every 60 second, refresh the time from database (to avoid drifts)


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
    def _fetch_sql_datetime() -> datetime.datetime:
        """Returns the current date/time of the database server.

        We use this time as method to keep all operations betwen different servers in sync.

        We support get database datetime for:
        * mysql
        * sqlite

        Returns:
            datetime: Current datetime of the database server
        """
        if connection.vendor in ('mysql', 'microsoft', 'postgresql'):
            cursor = connection.cursor()
            sentence = (
                'SELECT CURRENT_TIMESTAMP(4)'
                if connection.vendor in ('mysql', 'postgresql')
                else 'SELECT CURRENT_TIMESTAMP'
            )
            cursor.execute(sentence)
            date = (cursor.fetchone() or [datetime.datetime.now()])[0]
        else:
            date = (
                datetime.datetime.now()
            )  # If not know how to get database datetime, returns local datetime (this is fine for sqlite, which is local)

        return date

    @staticmethod
    def sql_now() -> datetime.datetime:
        now = datetime.datetime.now()
        with TimeTrack.lock:
            diff = now - TimeTrack.last_check
            # If in last_check is in the future, or more than CACHE_TIME_TIMEOUT seconds ago, we need to refresh
            # Future is possible if we have a clock update, or a big drift
            if diff > datetime.timedelta(seconds=CACHE_TIME_TIMEOUT) or diff < datetime.timedelta(seconds=0):
                TimeTrack.misses += 1
                TimeTrack.cached_time = TimeTrack._fetch_sql_datetime()
                TimeTrack.last_check = now
            else:
                TimeTrack.hits += 1
        the_time = TimeTrack.cached_time + (now - TimeTrack.last_check)
        # Keep only cent of second precision
        the_time = the_time.replace(microsecond=int(the_time.microsecond / 10000) * 10000)
        return the_time


def sql_now() -> datetime.datetime:
    """Returns the current date/time of the database server.
    Has been updated to use TimeTrack, which reduces the queries to database to get the current time
    """
    return TimeTrack.sql_now()


def sql_stamp_seconds() -> int:
    """Returns the current date/time of the database server as unix timestamp

    Returns:
        int: Unix timestamp
    """
    return int(mktime(sql_now().timetuple()))


def sql_stamp() -> float:
    """Returns the current date/time of the database server as unix timestamp

    Returns:
        float: Unix timestamp
    """
    return float(mktime(sql_now().timetuple())) + sql_now().microsecond / 1000000.0


def generate_uuid(obj: typing.Any = None) -> str:
    """
    Generates a ramdom uuid for models default
    """
    return CryptoManager().uuid(obj=obj).lower()


def process_uuid(uuid: str) -> str:
    if isinstance(uuid, bytes):
        uuid = uuid.decode('utf8')
    return uuid.lower()


def get_my_ip_from_db() -> str:
    """
    Gets, from the database, the IP of the current server.
    """
    # Mysql query:
    # SELECT host FROM information_schema.processlist WHERE ID = CONNECTION_ID();
    # Postgres query: SELECT client_addr FROM pg_stat_activity WHERE pid = pg_backend_pid();
    # sql server: SELECT client_net_address FROM sys.dm_exec_connections WHERE session_id = @@SPID;

    try:
        match connection.vendor:
            case 'mysql':
                query = 'SELECT host FROM information_schema.processlist WHERE ID = CONNECTION_ID();'
            case 'postgresql':
                query = 'SELECT client_addr FROM pg_stat_activity WHERE pid = pg_backend_pid();'
            case 'microsoft':
                query = 'SELECT client_net_address FROM sys.dm_exec_connections WHERE session_id = @@SPID;'
            case _:
                return '0.0.0.0'  # If not known, return a default IP

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                result = result[0] if isinstance(result[0], str) else result[0].decode('utf8')
                return result.split(':')[0]

    except Exception as e:
        logger.error('Error getting my IP: %s', e)

    return '0.0.0.0'
