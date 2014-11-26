# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Virtual Cable S.L.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from uds.core.util.Config import GlobalConfig
from uds.models import StatsCounters
from uds.models import getSqlDatetime
from uds.models import StatsEvents
from uds.models import optimizeTable
from django.db import connection
import datetime
import time

import logging

logger = logging.getLogger(__name__)


class StatsManager(object):
    '''
    Manager for statistics, so we can provide usefull info about platform usage

    Right now, we are going to provide an interface to "counter stats", that is, statistics
    that has counters (such as how many users is at a time active at platform, how many services
    are assigned, are in use, in cache, etc...
    '''
    _manager = None

    def __init__(self):
        pass

    @staticmethod
    def manager():
        if StatsManager._manager is None:
            StatsManager._manager = StatsManager()
        return StatsManager._manager

    def __doCleanup(self, dbTable):
        minTime = time.mktime((getSqlDatetime() - datetime.timedelta(days=GlobalConfig.STATS_DURATION.getInt())).timetuple())

        # Don't like how django (v1.5 at least) executes this (recovers all IDS and launches "DELETE .. WHERE id IN ...)
        # StatsCounters.objects.filter(stamp__lt=minTime).delete()
        # Used dict, cause environment says _meta is not known :-)
        query = 'DELETE FROM {0} where STAMP < {1}'.format(dbTable, minTime)
        cursor = connection.cursor()
        cursor.execute(query)
        # This table will hold a big amount of data, and mayby we erase a a big number of records also.
        # This will ensure table is in "good" shape (testing right now, will see at future)
        optimizeTable(dbTable)

    # Counter stats
    def addCounter(self, owner_type, owner_id, counterType, counterValue, stamp=None):
        '''
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
        '''
        from uds.models import getSqlDatetime, StatsCounters
        import time

        if stamp is None:
            stamp = getSqlDatetime()

        # To Unix epoch
        stamp = int(time.mktime(stamp.timetuple()))  # pylint: disable=maybe-no-member

        try:
            StatsCounters.objects.create(owner_type=owner_type, owner_id=owner_id, counter_type=counterType, value=counterValue, stamp=stamp)
            return True
        except Exception:
            logger.error('Exception handling counter stats saving (maybe database is full?)')
        return False

    def getCounters(self, ownerType, counterType, ownerIds, since, to, limit, use_max=False):
        '''
        Retrieves counters from item

        Args:

            counterTye: Type of counter to get values
            counterId: (optional), if specified, limit counter to only this id, all ids for specidied type if not
            maxElements: (optional) Maximum number of elements to retrieve, all if nothing specified
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified

        Returns:

            Iterator, containing (date, counter) each element
        '''
        # To Unix epoch
        since = int(time.mktime(since.timetuple()))
        to = int(time.mktime(to.timetuple()))

        return StatsCounters.get_grouped(ownerType, counterType, owner_id=ownerIds, since=since, to=to, limit=limit, use_max=use_max)

    def cleanupCounters(self):
        '''
        Removes all counters previous to configured max keep time for stat information from database.
        '''
        from uds.models import StatsCounters

        self.__doCleanup(StatsCounters.__dict__['_meta'].db_table)

    # Event stats
    # Counter stats
    def addEvent(self, owner_type, owner_id, eventType, stamp=None):
        '''
        Adds a new event stat to database.

        Args:

            toWhat: if of the counter
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:

            Nothing


        '''
        if stamp is None:
            stamp = getSqlDatetime(unix=True)
        else:
            # To Unix epoch
            stamp = int(time.mktime(stamp.timetuple()))  # pylint: disable=maybe-no-member

        try:
            StatsEvents.objects.create(owner_type=owner_type, owner_id=owner_id, event_type=eventType, stamp=stamp)
            return True
        except Exception:
            logger.error('Exception handling event stats saving (maybe database is full?)')
        return False

    def getEvents(self, fromWhat, **kwargs):
        '''
        Retrieves counters from item

        Args:

            fromWhat: From what object to get counters
            maxElements: (optional) Maximum number of elements to retrieve

        Returns:

            Array of lists, containing (date, counter)

        '''

    def cleanupEvents(self):
        '''
        Removes all events previous to configured max keep time for stat information from database.
        '''
        from uds.models import StatsEvents

        self.__doCleanup(StatsEvents.__dict__['_meta'].db_table)
