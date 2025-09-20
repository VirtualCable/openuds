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
import collections.abc
import dataclasses
import logging
import typing

from django.db.models import Model
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import exceptions, messaging, types
from uds.core.environment import Environment
from uds.core.ui import gui
from uds.core.util import ensure, permissions
from uds.core.util import ui as ui_utils
from uds.models import LogLevel, Notifier
from uds.REST.model import ModelHandler

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


@dataclasses.dataclass
class NotifierItem(types.rest.BaseRestItem):
    id: str
    name: str
    level: str
    enabled: bool
    tags: list[str]
    comments: str
    type: str
    type_name: str
    permission: types.permissions.PermissionType


class Notifiers(ModelHandler[NotifierItem]):

    PATH = 'messaging'
    MODEL = Notifier
    FIELDS_TO_SAVE = [
        'name',
        'comments',
        'level',
        'tags',
        'enabled',
    ]

    TABLE = (
        ui_utils.TableBuilder(_('Notifiers'))
        .icon(name='name', title=_('Name'))
        .text_column(name='type_name', title=_('Type'))
        .text_column(name='level', title=_('Level'))
        .boolean(name='enabled', title=_('Enabled'))
        .text_column(name='comments', title=_('Comments'))
        .text_column(name='tags', title=_('Tags'), visible=False)
    ).build()

    # Rest api related information to complete the auto-generated API
    REST_API_INFO = types.rest.api.RestApiInfo(
        typed=types.rest.api.RestApiInfoGuiType.MULTIPLE_TYPES,
    )

    @classmethod
    def possible_types(cls: type[typing.Self]) -> collections.abc.Iterable[type[messaging.Notifier]]:
        return messaging.factory().providers().values()

    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        notifier_type = messaging.factory().lookup(for_type)

        if not notifier_type:
            raise exceptions.rest.NotFound(_('Notifier type not found: {}').format(for_type))

        with Environment.temporary_environment() as env:
            notifier = notifier_type(env, None)

            return (
                (
                    ui_utils.GuiBuilder(100)
                    .add_stock_field(types.rest.stock.StockField.NAME)
                    .add_stock_field(types.rest.stock.StockField.COMMENTS)
                    .add_stock_field(types.rest.stock.StockField.TAGS)
                )
                .add_fields(notifier.gui_description())
                .add_choice(
                    name='level',
                    choices=[gui.choice_item(i[0], i[1]) for i in LogLevel.interesting()],
                    label=gettext('Level'),
                    tooltip=gettext('Level of notifications'),
                    default=str(LogLevel.ERROR.value),
                )
                .add_checkbox(
                    name='enabled',
                    label=gettext('Enabled'),
                    tooltip=gettext('If checked, this notifier will be used'),
                    default=True,
                )
                .build()
            )

    def get_item(self, item: 'Model') -> NotifierItem:
        item = ensure.is_instance(item, Notifier)
        type_ = item.get_type()
        return NotifierItem(
            id=item.uuid,
            name=item.name,
            level=str(item.level),
            enabled=item.enabled,
            tags=[tag.tag for tag in item.tags.all()],
            comments=item.comments,
            type=type_.mod_type(),
            type_name=type_.mod_name(),
            permission=permissions.effective_permissions(self._user, item),
        )
