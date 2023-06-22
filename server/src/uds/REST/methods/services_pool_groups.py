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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_lazy as _, gettext
from uds.models import ServicePoolGroup, Image
from uds.core.util.model import processUuid
from uds.core.ui import gui
from uds.core.ui.images import DEFAULT_THUMB_BASE64

from uds.REST.model import ModelHandler

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class ServicesPoolGroups(ModelHandler):
    """
    Handles the gallery REST interface
    """

    # needs_admin = True

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

    def beforeSave(self, fields: typing.Dict[str, typing.Any]) -> None:
        imgId = fields['image_id']
        fields['image_id'] = None
        logger.debug('Image id: %s', imgId)
        try:
            if imgId != '-1':
                image = Image.objects.get(uuid=processUuid(imgId))
                fields['image_id'] = image.id
        except Exception:
            logger.exception('At image recovering')

    # Gui related
    def getGui(self, type_: str) -> typing.List[typing.Any]:
        localGui = self.addDefaultFields([], ['name', 'comments', 'priority'])

        for field in [
            {
                'name': 'image_id',
                'values': [gui.choiceImage(-1, '--------', DEFAULT_THUMB_BASE64)]
                + gui.sortedChoices(
                    [
                        gui.choiceImage(v.uuid, v.name, v.thumb64)  # type: ignore
                        for v in Image.objects.all()
                    ]
                ),
                'label': gettext('Associated Image'),
                'tooltip': gettext('Image assocciated with this service'),
                'type': gui.InputField.Types.IMAGE_CHOICE,
                'order': 102,
            }
        ]:
            self.addField(localGui, field)

        return localGui

    def item_as_dict(self, item: ServicePoolGroup) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'priority': item.priority,
            'name': item.name,
            'comments': item.comments,
            'image_id': item.image.uuid if item.image else None,
        }

    def item_as_dict_overview(
        self, item: ServicePoolGroup
    ) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'priority': item.priority,
            'name': item.name,
            'comments': item.comments,
            'thumb': item.thumb64,
        }
