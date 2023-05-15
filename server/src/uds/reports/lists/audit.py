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
import re
import io
import typing
import csv
import datetime
import logging

from django.utils.translation import gettext, gettext_lazy as _

from uds.core.ui import gui
from uds.core.util import log
from uds.core.managers.log.objects import LogObjectType
from uds.models import Log

from .base import ListReport


logger = logging.getLogger(__name__)


class ListReportAuditCSV(ListReport):
    name = _('Audit Log list')  # Report name
    description = _('List administration audit logs')  # Report description
    filename = 'audit.csv'
    mime_type = 'text/csv'
    encoded = False
    # PDF Report of audit logs is extremely slow on pdf, so we will use csv only

    startDate = gui.DateField(
        order=2,
        label=_('Starting date'),
        tooltip=_('starting date for report'),
        defvalue=datetime.date.min,
        required=True,
    )

    endDate = gui.DateField(
        order=3,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        defvalue=datetime.date.max,
        required=True,
    )

    uuid = 'b5f5ebc8-44e9-11ed-97a9-efa619da6a49'

    # Generator of data
    def genData(self) -> typing.Generator[typing.Tuple, None, None]:
        # Xtract user method, response_code and request from data
        # the format is "user: [method/response_code] request"
        rx = re.compile(
            r'(?P<ip>[^ ]*) (?P<user>.*?): \[(?P<method>[^/]*)/(?P<response_code>[^\]]*)\] (?P<request>.*)'
        )

        start = self.startDate.datetime().replace(hour=0, minute=0, second=0, microsecond=0)
        end = self.endDate.datetime().replace(hour=23, minute=59, second=59, microsecond=999999)
        for i in Log.objects.filter(
            created__gte=start,
            created__lte=end,
            source=log.LogSource.REST,
            owner_type=LogObjectType.SYSLOG,
        ).order_by('-created'):
            # extract user, method, response_code and request from data field
            m = rx.match(i.data)

            if m is not None:
                # Convert response code to an string if 200, else, to an error
                response_code = {
                    '200': 'OK',
                    '400': 'Bad Request',
                    '401': 'Unauthorized',
                    '403': 'Forbidden',
                    '404': 'Not Found',
                    '405': 'Method Not Allowed',
                    '500': 'Internal Server Error',
                    '501': 'Not Implemented',
                }.get(m.group('response_code'), 'Code: ' + m.group('response_code'))
                yield (
                    i.created,
                    i.level_str,
                    m.group('ip'),
                    m.group('user'),
                    m.group('method'),
                    response_code,
                    m.group('request'),
                )

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                gettext('Date'),
                gettext('Level'),
                gettext('IP'),
                gettext('User'),
                gettext('Method'),
                gettext('Response code'),
                gettext('Request'),
            ]
        )

        for l in self.genData():
            writer.writerow(l)

        return output.getvalue().encode()
