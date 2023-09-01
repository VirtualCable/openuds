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
import datetime
import calendar


# Some helpers
def start_of_year() -> datetime.date:
    return datetime.date(datetime.date.today().year, 1, 1)


def end_of_year() -> datetime.date:
    return datetime.date(datetime.date.today().year, 12, 31)


def start_of_month() -> datetime.date:
    return datetime.date(datetime.date.today().year, datetime.date.today().month, 1)


def end_of_month() -> datetime.date:
    return datetime.date(
        datetime.date.today().year,
        datetime.date.today().month,
        calendar.monthrange(datetime.date.today().year, datetime.date.today().month)[1],
    )


def start_of_week() -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())


def end_of_week() -> datetime.date:
    return datetime.date.today() + datetime.timedelta(days=6 - datetime.date.today().weekday())


def yesterday() -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=1)


def today() -> datetime.date:
    return datetime.date.today()


def tomorrow() -> datetime.date:
    return datetime.date.today() + datetime.timedelta(days=1)
