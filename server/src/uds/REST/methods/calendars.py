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
@Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import dataclasses
import datetime
import logging
import typing

from django.utils.translation import gettext_lazy as _
from django.db import models

from uds.core import types
from uds.models import Calendar
from uds.core.util import permissions, ensure, ui as ui_utils

from uds.REST.model import ModelHandler
from .calendarrules import CalendarRules



logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CalendarItem(types.rest.BaseRestItem):
    id: str
    name: str
    tags: list[str]
    comments: str
    modified: datetime.datetime
    number_rules: int
    number_access: int
    number_actions: int
    permission: types.permissions.PermissionType

class Calendars(ModelHandler[CalendarItem]):
    """
    Processes REST requests about calendars
    """

    MODEL = Calendar
    DETAIL = {'rules': CalendarRules}

    FIELDS_TO_SAVE = ['name', 'comments', 'tags']

    TABLE = (
        ui_utils.TableBuilder(_('Calendars'))
        .text_column(name='name', title=_('Name'), visible=True)
        .text_column(name='comments', title=_('Comments'))
        .datetime_column(name='modified', title=_('Modified'))
        .numeric_column(name='number_rules', title=_('Rules'), width='5rem')
        .numeric_column(name='number_access', title=_('Pools with Accesses'), width='5rem')
        .numeric_column(name='number_actions', title=_('Pools with Actions'), width='5rem')
        .text_column(name='tags', title=_('tags'), visible=False)
        .build()
    )

    def get_item(self, item: 'models.Model') -> CalendarItem:
        item = ensure.is_instance(item, Calendar)
        return CalendarItem(
            id=item.uuid,
            name=item.name,
            tags=[tag.tag for tag in item.tags.all()],
            comments=item.comments,
            modified=item.modified,
            number_rules=item.rules.count(),
            number_access=item.calendaraccess_set.all().values('service_pool').distinct().count(),
            number_actions=item.calendaraction_set.all().values('service_pool').distinct().count(),
            permission=permissions.effective_permissions(self._user, item),
        )

    def get_gui(self, for_type: str) -> list[typing.Any]:
        return (
            ui_utils.GuiBuilder()
            .add_stock_field(types.rest.stock.StockField.NAME)
            .add_stock_field(types.rest.stock.StockField.COMMENTS)
            .add_stock_field(types.rest.stock.StockField.TAGS)
            .build()
        )
