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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import ugettext_lazy as _
from uds.models import Calendar
from uds.core.util import permissions

from uds.REST.model import ModelHandler
from .calendarrules import CalendarRules


logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Calendars(ModelHandler):
    """
    Processes REST requests about calendars
    """
    model = Calendar
    detail = {'rules': CalendarRules}

    save_fields = ['name', 'comments', 'tags']

    table_title = _('Calendars')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'icon', 'icon': 'fa fa-calendar text-success'}},
        {'comments': {'title': _('Comments')}},
        {'modified': {'title': _('Modified'), 'type': 'datetime'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def item_as_dict(self, item: Calendar) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'modified': item.modified,
            'permission': permissions.getEffectivePermission(self._user, item)
        }

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        return self.addDefaultFields([], ['name', 'comments', 'tags'])
