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
import datetime
import logging
import typing

from django.utils.translation import gettext_lazy as _
from uds.core import types
from uds.models import Calendar
from uds.core.util import permissions, ensure

from uds.REST.model import ModelHandler
from .calendarrules import CalendarRules

if typing.TYPE_CHECKING:
    from django.db.models import Model


logger = logging.getLogger(__name__)

class CalendarItem(types.rest.ItemDictType):
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

    model = Calendar
    detail = {'rules': CalendarRules}

    save_fields = ['name', 'comments', 'tags']

    table_title = _('Calendars')
    table_fields = [
        {
            'name': {
                'title': _('Name'),
                'visible': True,
                'type': 'icon',
                'icon': 'fa fa-calendar text-success',
            }
        },
        {'comments': {'title': _('Comments')}},
        {'modified': {'title': _('Modified'), 'type': 'datetime'}},
        {'number_rules': {'title': _('Rules')}},
        {'number_access': {'title': _('Pools with Accesses')}},
        {'number_actions': {'title': _('Pools with Actions')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def item_as_dict(self, item: 'Model') -> CalendarItem:
        item = ensure.is_instance(item, Calendar)
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'modified': item.modified,
            'number_rules': item.rules.count(),
            'number_access': item.calendaraccess_set.all().values('service_pool').distinct().count(),
            'number_actions': item.calendaraction_set.all().values('service_pool').distinct().count(),
            'permission': permissions.effective_permissions(self._user, item),
        }

    def get_gui(self, type_: str) -> list[typing.Any]:
        return self.add_default_fields([], ['name', 'comments', 'tags'])
