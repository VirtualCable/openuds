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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

from django.utils.translation import gettext_lazy as _, gettext
from uds.core.environment import Environment
from uds.models import Notifier, LogLevel
from uds.core import messaging
from uds.core.ui import gui
from uds.core.util import permissions

from uds.REST.model import ModelHandler


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
    ]

    table_title = _('Notifiers')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'level': {'title': _('Level')}},
        {'comments': {'title': _('Comments')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def enum_types(self) -> typing.Iterable[typing.Type[messaging.Notifier]]:
        return messaging.factory().providers().values()

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        notifierType = messaging.factory().lookup(type_)

        if not notifierType:
            raise self.invalidItemException()

        notifier = notifierType(Environment.getTempEnv(), None)

        localGui = self.addDefaultFields(
            notifier.guiDescription(), ['name', 'comments', 'tags']
        )

        for field in [
            {
                'name': 'level',
                'values': [gui.choiceItem(i[0], i[1]) for i in LogLevel.interesting()],
                'label': gettext('Level'),
                'tooltip': gettext('Level of notifications'),
                'type': gui.InputField.Types.CHOICE,
                'order': 102,
            }
        ]:
            self.addField(localGui, field)

        return localGui

    def item_as_dict(self, item: Notifier) -> typing.Dict[str, typing.Any]:
        type_ = item.getType()
        return {
            'id': item.uuid,
            'name': item.name,
            'level': item.level,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'type': type_.type(),
            'type_name': type_.name(),
            'permission': permissions.getEffectivePermission(self._user, item),
        }
