# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds.core import types, consts
from uds.core.util.rest.tools import match_args
from uds.core.util import ui as ui_utils
from uds.REST import model
from uds import reports

if typing.TYPE_CHECKING:
    from uds.core.reports.report import Report

logger = logging.getLogger(__name__)

VALID_PARAMS = (
    'authId',
    'authSmallName',
    'auth',
    'username',
    'realname',
    'password',
    'groups',
    'servicePool',
    'transport',
)


class ReportItem(types.rest.BaseRestItem):
    id: str
    mime_type: str
    encoded: bool
    group: str
    name: str
    description: str


# Enclosed methods under /actor path
class Reports(model.BaseModelHandler[ReportItem]):
    """
    Processes reports requests
    """

    min_access_role = consts.UserRole.ADMIN

    table_info = (
        ui_utils.TableBuilder(_('Available reports'))
        .string(name='group', title=_('Group'), visible=True)
        .string(name='name', title=_('Name'), visible=True)
        .string(name='description', title=_('Description'), visible=True)
        .string(name='mime_type', title=_('Generates'), visible=True)
        .row_style(prefix='row-state-', field='state')
        .build()
    )

    # table_title = _('Available reports')
    # xtable_fields = [
    #     {'group': {'title': _('Group')}},
    #     {'name': {'title': _('Name')}},
    #     {'description': {'title': _('Description')}},
    #     {'mime_type': {'title': _('Generates')}},
    # ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....

    def _locate_report(
        self, uuid: str, values: typing.Optional[typing.Dict[str, typing.Any]] = None
    ) -> 'Report':
        found = None
        logger.debug('Looking for report %s', uuid)
        for i in reports.available_reports:
            if i.get_uuid() == uuid:
                found = i(values)
                break

        if not found:
            raise self.invalid_request_response('Invalid report uuid!')

        return found

    def get(self) -> typing.Any:
        logger.debug('method GET for %s, %s', self.__class__.__name__, self._args)

        def error() -> typing.NoReturn:
            raise self.invalid_request_response()

        def report_gui(report_id: str) -> typing.Any:
            return self.get_gui(report_id)

        return match_args(
            self._args,
            error,
            ((), lambda: list(self.get_items())),
            ((consts.rest.OVERVIEW,), lambda: list(self.get_items())),
            (
                (consts.rest.TABLEINFO,),
                lambda: self.table_info.as_dict(),
            ),
            ((consts.rest.GUI, '<report>'), report_gui),
        )

    def put(self) -> typing.Any:
        """
        Processes a PUT request
        """
        logger.debug(
            'method PUT for %s, %s, %s',
            self.__class__.__name__,
            self._args,
            self._params,
        )

        if len(self._args) != 1:
            raise self.invalid_request_response()

        report = self._locate_report(self._args[0], self._params)

        try:
            logger.debug('Report: %s', report)
            result = report.generate_encoded()

            data = {
                'mime_type': report.mime_type,
                'encoded': report.encoded,
                'filename': report.filename,
                'data': result,
            }

            return data
        except Exception as e:
            logger.exception('Generating report')
            raise self.invalid_request_response(str(e))

    # Gui related
    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        report = self._locate_report(for_type)
        return sorted(report.gui_description(), key=lambda f: f['gui']['order'])

    # Returns the list of
    def get_items(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Generator[ReportItem, None, None]:
        for i in reports.available_reports:
            yield {
                'id': i.get_uuid(),
                'mime_type': i.mime_type,
                'encoded': i.encoded,
                'group': i.translated_group(),
                'name': i.translated_name(),
                'description': i.translated_description(),
            }
