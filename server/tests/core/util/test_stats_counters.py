# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import datetime
import typing
import collections.abc

from ...fixtures.stats_counters import create_stats_counters

# We use commit/rollback
from ...utils.test import UDSTestCase

from uds.core.util.stats import counters
from uds import models

START_DATE = datetime.datetime(2020, 1, 1, 0, 0, 0)
END_DATE_DAY = datetime.datetime(2020, 1, 2, 0, 0, 0)
END_DATE_MONTH = datetime.datetime(2020, 2, 1, 0, 0, 0)
END_DATE_YEAR = datetime.datetime(2021, 1, 1, 0, 0, 0)

class StatsCountersTest(UDSTestCase):
    def setUp(self) -> None:
        return super().setUp()


    def xtest_create_stats_counters_single(self) -> None:
        l = create_stats_counters(
            counters.OT_AUTHENTICATOR,
            0,
            counters.CT_INUSE,
            START_DATE,
            END_DATE_DAY,
            1
        )

        self.assertEqual(len(l), 1)
        # Now, test it is on DB. If not found, it will raise exception
        models.StatsCounters.objects.get(
            owner_type=counters.OT_AUTHENTICATOR,
            owner_id=0,
            counter_type=counters.CT_INUSE,
            stamp=int(START_DATE.timestamp()),
        )

        # Now test get_grouped
        res = list(models.StatsCounters.get_grouped(
            counters.OT_AUTHENTICATOR,
            counters.CT_INUSE,
        ))
        self.assertEqual(len(res), 1)
        res = list(models.StatsCounters.get_grouped(
            counters.OT_AUTHENTICATOR,
            counters.CT_INUSE,
            owner_id=0,
            since=START_DATE,
            to=END_DATE_DAY,
        ))
        self.assertEqual(len(res), 1)
        
    def test_create_stats_counters_multi(self) -> None:
        NUMBER = 100
        l = create_stats_counters(
            counters.OT_AUTHENTICATOR,
            0,
            counters.CT_INUSE,
            START_DATE,
            END_DATE_DAY,
            NUMBER
        )

        self.assertEqual(len(l), NUMBER)
        # Now, test it is on DB. If not found, it will raise exception
        models.StatsCounters.objects.get(
            owner_type=counters.OT_AUTHENTICATOR,
            owner_id=0,
            counter_type=counters.CT_INUSE,
            stamp=int(START_DATE.timestamp()),
        )


        res = list(models.StatsCounters.get_grouped(
            counters.OT_AUTHENTICATOR,
            counters.CT_INUSE,
            owner_id=0,
            since=START_DATE,
            to=END_DATE_DAY,
            interval=3600,
        ))
        self.assertEqual(len(res), 24)

        # Now test get_grouped
        res = list(models.StatsCounters.get_grouped(
            counters.OT_AUTHENTICATOR,
            counters.CT_INUSE,
        ))
        self.assertEqual(len(res), NUMBER)
        res = list(models.StatsCounters.get_grouped(
            counters.OT_AUTHENTICATOR,
            counters.CT_INUSE,
            owner_id=0,
            since=START_DATE,
            to=END_DATE_DAY,
        ))
        self.assertEqual(len(res), NUMBER)
