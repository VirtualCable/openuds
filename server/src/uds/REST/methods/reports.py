# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

import six

from django.utils.translation import ugettext_lazy as _

from uds.REST import model
from uds import reports


logger = logging.getLogger(__name__)

VALID_PARAMS = ('authId', 'authSmallName', 'auth', 'username', 'realname', 'password', 'groups', 'servicePool', 'transport')


# Enclosed methods under /actor path
class Reports(model.BaseModelHandler):
    """
    Processes actor requests
    """
    needs_admin = True  # By default, staff is lower level needed

    table_title = _('Available reports')
    table_fields = [
        {'group': {'title': _('Group')}},
        {'name': {'title': _('Name')}},  # Will process this field on client in fact, not sent by server
        {'description': {'title': _('Description')}},  # Will process this field on client in fact, not sent by server
        {'mime_type': {'title': _('Generates')}},  # Will process this field on client in fact, not sent by server
    ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....
    table_row_style = {'field': 'state', 'prefix': 'row-state-'}

    def _findReport(self, uuid, values=None):
        found = None
        logger.debug('Looking for report %s', uuid)
        for i in reports.availableReports:
            if i.getUuid() == uuid:
                found = i(values)
                break

        if found is None:
            self.invalidRequestException('Invalid report!')

        return found

    def get(self):
        logger.debug('method GET for %s, %s', self.__class__.__name__, self._args)
        nArgs = len(self._args)

        if nArgs == 0:
            return list(self.getItems())

        if nArgs == 1:
            if self._args[0] == model.OVERVIEW:
                return list(self.getItems())
            elif self._args[0] == model.TABLEINFO:
                return self.processTableFields(self.table_title, self.table_fields, self.table_row_style)

        if nArgs == 2:
            if self._args[0] == model.GUI:
                return self.getGui(self._args[1])

        return self.invalidRequestException()

    def put(self):
        """
        Processes a PUT request
        """
        logger.debug('method PUT for %s, %s, %s', self.__class__.__name__, self._args, self._params)

        if len(self._args) != 1:
            return self.invalidRequestException()

        report = self._findReport(self._args[0], self._params)

        try:
            logger.debug('Report: %s', report)
            result = report.generateEncoded()

            data = {
                'mime_type': report.mime_type,
                'encoded': report.encoded,
                'filename': report.filename,
                'data': result
            }

            return data
        except Exception as e:
            logger.exception('Generating report')
            return self.invalidRequestException(six.text_type(e))

    # Gui related
    def getGui(self, uuid):
        report = self._findReport(uuid)
        return sorted(report.guiDescription(report), key=lambda f: f['gui']['order'])

    # Returns the list of
    def getItems(self):
        return [
            {
                'id': i.getUuid(),
                'mime_type': i.mime_type,
                'encoded': i.encoded,
                'group': i.translated_group(),
                'name': i.translated_name(),
                'description': i.translated_description()
            } for i in reports.availableReports
        ]
