# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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

'''
@Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import messaging, types
from uds.core.environment import Environment
from uds.core.ui import gui
from uds.core.util import ensure, permissions
from uds.models import LogLevel, Notifier
from uds.REST.model import ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model


logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Notifiers(ModelHandler):
    path = 'messaging'
    model = Notifier
    save_fields = [
        'name',
        'comments',
        'level',
        'tags',
        'enabled',
    ]

    table_title = _('Notifiers')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'level': {'title': _('Level')}},
        {'enabled': {'title': _('Enabled')}},
        {'comments': {'title': _('Comments')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def enum_types(self) -> collections.abc.Iterable[type[messaging.Notifier]]:
        return messaging.factory().providers().values()

    def get_gui(self, type_: str) -> list[typing.Any]:
        notifier_type = messaging.factory().lookup(type_)

        if not notifier_type:
            raise self.invalid_item_response()

        with Environment.temporary_environment() as env:
            notifier = notifier_type(env, None)

            local_gui = self.add_default_fields(
                notifier.gui_description(), ['name', 'comments', 'tags']
            )

            for field in [
                {
                    'name': 'level',
                    'choices': [gui.choice_item(i[0], i[1]) for i in LogLevel.interesting()],
                    'label': gettext('Level'),
                    'tooltip': gettext('Level of notifications'),
                    'type': types.ui.FieldType.CHOICE,
                    'order': 102,
                    'default': str(LogLevel.ERROR.value),
                },
                {
                    'name': 'enabled',
                    'label': gettext('Enabled'),
                    'tooltip': gettext('If checked, this notifier will be used'),
                    'type': types.ui.FieldType.CHECKBOX,
                    'order': 103,
                    'default': True,
                }
            ]:
                self.add_field(local_gui, field)

            return local_gui

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        item = ensure.is_instance(item, Notifier)
        type_ = item.get_type()
        return {
            'id': item.uuid,
            'name': item.name,
            'level': str(item.level),
            'enabled': item.enabled,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'type': type_.mod_type(),
            'type_name': type_.mod_name(),
            'permission': permissions.effective_permissions(self._user, item),
        }
