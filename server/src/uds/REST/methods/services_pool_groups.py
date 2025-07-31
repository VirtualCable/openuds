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
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds.core import types
from uds.core.util import ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds.models import Image, ServicePoolGroup
from uds.REST.model import ModelHandler

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.db.models import Model


# Enclosed methods under /item path


@dataclasses.dataclass
class ServicePoolGroupItem(types.rest.BaseRestItem):
    id: str
    name: str
    comments: str
    priority: int
    image_id: str | None | types.rest.NotRequired = types.rest.NotRequired.field()
    thumb: str | types.rest.NotRequired = types.rest.NotRequired.field()


class ServicesPoolGroups(ModelHandler[ServicePoolGroupItem]):

    PATH = 'gallery'
    MODEL = ServicePoolGroup
    FIELDS_TO_SAVE = ['name', 'comments', 'image_id', 'priority']

    TABLE = (
        ui_utils.TableBuilder(_('Services Pool Groups'))
        .numeric_column(name='priority', title=_('Priority'), width='6em')
        .image(name='thumb', title=_('Image'), width='96px')
        .text_column(name='name', title=_('Name'))
        .text_column(name='comments', title=_('Comments'))
        .build()
    )

    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        img_id = fields['image_id']
        fields['image_id'] = None
        logger.debug('Image id: %s', img_id)
        try:
            if img_id != '-1':
                image = Image.objects.get(uuid=process_uuid(img_id))
                fields['image_id'] = image.id
        except Exception:
            logger.exception('At image recovering')

    # Gui related
    def get_gui(self, for_type: str) -> list[typing.Any]:
        return (
            ui_utils.GuiBuilder()
            .add_stock_field(types.rest.stock.StockField.NAME)
            .add_stock_field(types.rest.stock.StockField.COMMENTS)
            .add_stock_field(types.rest.stock.StockField.PRIORITY)
            .new_tab(types.ui.Tab.DISPLAY)
            .add_image_choice()
            .build()
        )

    def get_item(self, item: 'Model') -> ServicePoolGroupItem:
        item = ensure.is_instance(item, ServicePoolGroup)
        return ServicePoolGroupItem(
            id=item.uuid,
            name=item.name,
            comments=item.comments,
            priority=item.priority,
            image_id=item.image.uuid if item.image else None,
        )

    def get_item_summary(self, item: 'Model') -> ServicePoolGroupItem:
        item = ensure.is_instance(item, ServicePoolGroup)
        return ServicePoolGroupItem(
            id=item.uuid,
            priority=item.priority,
            name=item.name,
            comments=item.comments,
            thumb=item.thumb64,
        )
