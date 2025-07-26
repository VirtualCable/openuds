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
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import types, ui
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core.util import ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds.models import Image, ServicePoolGroup
from uds.REST.model import ModelHandler

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.db.models import Model


# Enclosed methods under /item path


class ServicePoolGroupItem(types.rest.ItemDictType):
    id: str
    name: str
    comments: str
    priority: int
    image_id: typing.NotRequired[str | None]
    thumb: typing.NotRequired[str]


class ServicesPoolGroups(ModelHandler[ServicePoolGroupItem]):

    path = 'gallery'
    model = ServicePoolGroup
    save_fields = ['name', 'comments', 'image_id', 'priority']

    table_title = _('Services Pool Groups')
    table_fields = [
        {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
        {
            'thumb': {
                'title': _('Image'),
                'visible': True,
                'type': 'image',
                'width': '96px',
            }
        },
        {'name': {'title': _('Name')}},
        {'comments': {'title': _('Comments')}},
    ]

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
        return self.compose_gui(
            [
                types.rest.stock.StockField.NAME,
                types.rest.stock.StockField.COMMENTS,
                types.rest.stock.StockField.PRIORITY,
            ],
            ui_utils.image_choice_field(
                order=120,
                name='image_id',
                label=gettext('Associated Image'),
                choices=[ui.gui.choice_image(-1, '--------', DEFAULT_THUMB_BASE64)]
                + ui.gui.sorted_choices(
                    [ui.gui.choice_image(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]
                ),
                tooltip=gettext('Image associated with this service'),
                tab=types.ui.Tab.DISPLAY,
            ),
        )

    def item_as_dict(self, item: 'Model') -> ServicePoolGroupItem:
        item = ensure.is_instance(item, ServicePoolGroup)
        return {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'priority': item.priority,
            'image_id': item.image.uuid if item.image else None,
        }

    def item_as_dict_overview(self, item: 'Model') -> ServicePoolGroupItem:
        item = ensure.is_instance(item, ServicePoolGroup)
        return {
            'id': item.uuid,
            'priority': item.priority,
            'name': item.name,
            'comments': item.comments,
            'thumb': item.thumb64,
        }
