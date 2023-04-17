# -*- coding: utf-8 -*-

#
# Copyright (c) 2015-2021 Virtual Cable S.L.U.
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
import io
import csv
import logging

# import openpyxl
# import openpyxl.writer.excel

from django.utils.translation import gettext, gettext_lazy as _

from uds.core.ui import gui
from uds.models import Authenticator

from .base import ListReport


logger = logging.getLogger(__name__)


class ListReportUsers(ListReport):
    filename = 'users.pdf'

    authenticator = gui.ChoiceField(
        label=_("Authenticator"),
        order=1,
        tooltip=_('Authenticator from where to list users'),
        required=True,
    )

    name = _('Users list')  # Report name
    description = _('List users of platform')  # Report description
    uuid = '8cd1cfa6-ed48-11e4-83e5-10feed05884b'

    def initialize(self, values):
        if values:
            auth = Authenticator.objects.get(uuid=self.authenticator.value)
            self.filename = auth.name + '.pdf'

    def initGui(self) -> None:
        logger.debug('Initializing gui')
        vals = [gui.choiceItem(v.uuid, v.name) for v in Authenticator.objects.all()]

        self.authenticator.setValues(vals)

    def generate(self) -> bytes:
        auth = Authenticator.objects.get(uuid=self.authenticator.value)
        users = auth.users.order_by('name')

        return self.templateAsPDF(
            'uds/reports/lists/users.html',
            dct={
                'users': users,
                'auth': auth.name,
            },
            header=gettext('Users List for {}').format(auth.name),
            water=gettext('UDS Report of users in {}').format(auth.name),
        )


class ListReportsUsersCSV(ListReportUsers):
    filename = 'users.csv'
    mime_type = 'text/csv'
    encoded = False

    uuid = '5da93a76-1849-11e5-ac1a-10feed05884b'

    authenticator = ListReportUsers.authenticator

    def initialize(self, values):
        if values:
            auth = Authenticator.objects.get(uuid=self.authenticator.value)
            self.filename = auth.name + '.csv'

    def generate(self) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        auth = Authenticator.objects.get(uuid=self.authenticator.value)
        users = auth.users.order_by('name')

        writer.writerow(
            [gettext('User ID'), gettext('Real Name'), gettext('Last access')]
        )

        for v in users:
            writer.writerow([v.name, v.real_name, v.last_access])

        return output.getvalue().encode()


# Sample XLSX report
# Just for sampling purposses, not used...
# class ListReportsUsersXlsx(ListReportUsers):
#     filename = 'users.xlsx'
#     mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#     encoded = True

#     uuid = 'b81a6680-bd78-11eb-971c-17d9a0bf977a'

#     authenticator = ListReportUsers.authenticator

#     def initialize(self, values):
#         if values:
#             auth = Authenticator.objects.get(uuid=self.authenticator.value)
#             self.filename = auth.name + '.xlsx'

#     def generate(self) -> bytes:
#         wb = openpyxl.Workbook()
#         ws = wb.active

#         auth = Authenticator.objects.get(uuid=self.authenticator.value)
#         users = auth.users.order_by('name')
#         ws.append([gettext('User ID'), gettext('Real Name'), gettext('Last access')])

#         for v in users:
#             ws.append([v.name, v.real_name, v.last_access])

#         output = io.BytesIO()
#         zip = zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
#         writer = openpyxl.writer.excel.ExcelWriter(workbook=wb, archive=zip)
#         writer.save()

#         return output.getvalue()
