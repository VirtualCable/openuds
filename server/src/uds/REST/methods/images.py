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
from django.db import models

from uds.models import Image
from uds.core import types
from uds.core.util import ensure, ui as ui_utils

from uds.REST.model import ModelHandler


logger = logging.getLogger(__name__)

# Enclosed methods under /item path


@dataclasses.dataclass
class ImageItem(types.rest.BaseRestItem):
    id: str
    name: str
    data: str = ''
    size: str = ''
    thumb: str = ''


class Images(ModelHandler[ImageItem]):
    """
    Handles the gallery REST interface
    """

    PATH = 'gallery'
    MODEL = Image
    FIELDS_TO_SAVE = ['name', 'data']

    TABLE = (
        ui_utils.TableBuilder(_('Image Gallery'))
        .image('thumb', _('Image'), width='96px')
        .text_column('name', _('Name'))
        .text_column('size', _('Size'))
        .build()
    )

    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        fields['image'] = fields['data']
        del fields['data']
        # fields['data'] = Image.prepareForDb(Image.decode64(fields['data']))[2]

    def post_save(self, item: 'models.Model') -> None:
        item = ensure.is_instance(item, Image)
        # Updates the thumbnail and re-saves it
        logger.debug('After save: item = %s', item)
        # item.updateThumbnail()
        # item.save()

    # Note:
    # This has no get_gui because its treated on the admin or client.
    # We expect an Image List

    def get_item(self, item: 'models.Model') -> ImageItem:
        item = ensure.is_instance(item, Image)
        return ImageItem(
            id=item.uuid,
            name=item.name,
            data=item.data64,
        )

    def get_item_summary(self, item: 'models.Model') -> ImageItem:
        item = ensure.is_instance(item, Image)
        return ImageItem(
            id=item.uuid,
            size='{}x{}, {} bytes (thumb {} bytes)'.format(
                item.width, item.height, len(item.data), len(item.thumb)
            ),
            name=item.name,
            thumb=item.thumb64,
        )
