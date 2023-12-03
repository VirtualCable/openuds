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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import copy
import typing
import collections.abc
import datetime
import random

from uds import models
from uds.models.calendar_rule import freqs, dunits


# fixtures for calendars and calendar rules
CALENDAR_DATA: collections.abc.Mapping[str, list[dict[str, typing.Union[str,int,None]]]] = {
    'calendars': [
        {
            "modified": "2015-09-18T00:04:31.792",
            "uuid": "2cf6846b-d889-57ce-bb35-e647040a95b6",
            "comments": "Calendar by days",
            "name": "Calendar Dayly",
        },
        {
            "modified": "2015-09-18T00:05:44.386",
            "uuid": "c1221a6d-3848-5fa3-ae98-172662c0f554",
            "comments": "Calendar by weeks",
            "name": "Calendar Weekly",
        },
        {
            "modified": "2015-09-18T00:03:47.362",
            "uuid": "353c4cb8-e02d-5387-a18f-f634729fde81",
            "comments": "Calendar by months",
            "name": "Calendar Monthly",
        },
        {
            "modified": "2015-09-18T00:05:33.958",
            "uuid": "bccfd011-605b-565f-a08e-80bf75114dce",
            "comments": "Calendar by day of week",
            "name": "Calendar Weekdays",
        },
        {
            "modified": "2015-09-18T00:19:51.131",
            "uuid": "60160f94-c8fe-5fdc-bbbe-325010980106",
            "comments": "Calendar tests for durations",
            "name": "Calendar xDurations",
        },
    ],
    'rules': [
        {
            "end": None,
            "uuid": "42846f5f-6a61-5257-beb5-67beb179d6b1",
            "duration_unit": "HOURS",
            "interval": 1,
            "comments": "Rule with 1 day interval, no end",
            "start": "2015-09-01T08:00:00",
            "frequency": "DAILY",
            "duration": 12,
            "calendar": 0,
            "name": "Rule interval 1 day, no end",
        },
        {
            "end": "2015-10-01",
            "uuid": "f20d8841-72d2-5054-b590-37dc19729b80",
            "duration_unit": "MINUTES",
            "interval": 1,
            "comments": "Rule with 1 day interval, with an end",
            "start": "2015-09-01T21:00:00",
            "frequency": "DAILY",
            "duration": 300,
            "calendar": 0,
            "name": "Rule interval 1 day, end",
        },
        {
            "end": None,
            "uuid": "935cceba-4384-50ba-a125-ea40727f0609",
            "duration_unit": "HOURS",
            "interval": 1,
            "comments": "Rule with 1 week interval, no end.",
            "start": "2015-09-01T07:00:00",
            "frequency": "WEEKLY",
            "duration": 2,
            "calendar": 1,
            "name": "Rule with 1 week interval, no end",
        },
        {
            "end": "2015-10-01",
            "uuid": "53c94b8a-6ab4-5c06-b863-083e88bd8469",
            "duration_unit": "MINUTES",
            "interval": 1,
            "comments": "Rule with 1 week interval, with end",
            "start": "2015-09-01T10:00:00",
            "frequency": "WEEKLY",
            "duration": 120,
            "calendar": 1,
            "name": "Rule with 1 week interval, with end",
        },
        {
            "end": None,
            "uuid": "ff8168a4-0c0c-5a48-acee-f8b3f04d52b8",
            "duration_unit": "HOURS",
            "interval": 1,
            "comments": "Rule with 1 month interval, no end",
            "start": "2015-09-01T07:00:00",
            "frequency": "MONTHLY",
            "duration": 2,
            "calendar": 2,
            "name": "Rule with 1 month interval, no end",
        },
        {
            "end": "2015-11-01",
            "uuid": "0c4e2086-f807-5801-889c-3d568e42033f",
            "duration_unit": "MINUTES",
            "interval": 1,
            "comments": "Rule with 1 month interval, with end",
            "start": "2015-09-01T10:00:00",
            "frequency": "MONTHLY",
            "duration": 120,
            "calendar": 2,
            "name": "Rule with 1 month interval, with end",
        },
        {
            "end": None,
            "uuid": "3227f381-c017-5d5c-b2ca-863e5ac643ce",
            "duration_unit": "HOURS",
            "interval": 42,
            "comments": "Rule for Mon, Wed & Fri, no end",
            "start": "2015-09-01T07:00:00",
            "frequency": "WEEKDAYS",
            "duration": 2,
            "calendar": 3,
            "name": "Rule for Mon, Wed & Fri, no end",
        },
        {
            "end": "2015-10-01",
            "uuid": "2c16056e-97b1-5a4e-ae34-ab99c73ddd8f",
            "duration_unit": "MINUTES",
            "interval": 42,
            "comments": "Rule for Mon, Wed & Fri, with end",
            "start": "2015-09-01T10:00:00",
            "frequency": "WEEKDAYS",
            "duration": 120,
            "calendar": 3,
            "name": "Rule for Mon, Wed & Fri, with end",
        },
        {
            "end": "2015-01-01",
            "uuid": "a4dd4e82-65bd-5824-bd78-95eafb40abf5",
            "duration_unit": "MINUTES",
            "interval": 1,
            "comments": "For testing minutes",
            "start": "2015-01-01T00:00:00",
            "frequency": "DAILY",
            "duration": 2,
            "calendar": 4,
            "name": "Test Minutes",
        },
        {
            "end": "2015-02-01",
            "uuid": "9194d314-a6b0-5d7f-a3e3-08ff475e271c",
            "duration_unit": "HOURS",
            "interval": 1,
            "comments": "for testing hours",
            "start": "2015-02-01T00:00:00",
            "frequency": "DAILY",
            "duration": 2,
            "calendar": 4,
            "name": "Test Hours",
        },
        {
            "end": "2015-03-01",
            "uuid": "bffb7290-16eb-5be0-adb2-6b454d6d7b49",
            "duration_unit": "DAYS",
            "interval": 1,
            "comments": "For testing days",
            "start": "2015-03-01T00:00:00",
            "frequency": "DAILY",
            "duration": 2,
            "calendar": 4,
            "name": "Test Days",
        },
        {
            "end": "2015-04-01",
            "uuid": "dc8e30e9-2bf2-5008-a46b-2457376fb2e0",
            "duration_unit": "WEEKS",
            "interval": 1,
            "comments": "for testing weeks",
            "start": "2015-04-01T08:00:00",
            "frequency": "DAILY",
            "duration": 2,
            "calendar": 4,
            "name": "Test Weeks",
        },
    ],
}

def createCalendars() -> typing.Tuple[list[models.Calendar], list[models.CalendarRule]]:
    calendars: list[models.Calendar] = []
    rules: list[models.CalendarRule] = []
    for calendar in CALENDAR_DATA["calendars"]:
        calendars.append(models.Calendar.objects.create(**calendar))
    for r in CALENDAR_DATA["rules"]:
        # Extract parent calendar
        rule = r.copy()
        parent = calendars[typing.cast(int, rule['calendar'])]
        del rule['calendar']
        rules.append(parent.rules.create(**rule))

    return calendars, rules