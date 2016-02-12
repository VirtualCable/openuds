# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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

'''
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _, ugettext
from uds.models import ServicesPoolGroup, Image
from uds.core.util.model import processUuid
from uds.core.ui.UserInterface import gui
from uds.core.ui.images import DEFAULT_THUMB_BASE64

from uds.REST.model import ModelHandler

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class ServicesPoolGroups(ModelHandler):
    '''
    Handles the gallery REST interface
    '''
    needs_admin = True

    path = 'gallery'
    model = ServicesPoolGroup
    save_fields = ['name', 'comments', 'image_id']

    table_title = _('Services Pool Groups')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'thumb': {'title': _('Image'), 'visible': True, 'type': 'image'}},
    ]

    def beforeSave(self, fields):
        imgId = fields['image_id']
        fields['image_id'] = None
        logger.debug('Image id: {}'.format(imgId))
        try:
            if imgId != '-1':
                image = Image.objects.get(uuid=processUuid(imgId))
                fields['image_id'] = image.id
        except Exception:
            logger.exception('At image recovering')

    # Gui related
    def getGui(self, type_):
        g = self.addDefaultFields([], ['name', 'comments'])

        for f in [{
            'name': 'image_id',
            'values': [gui.choiceImage(-1, '--------', DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]),
            'label': ugettext('Associated Image'),
            'tooltip': ugettext('Image assocciated with this service'),
            'type': gui.InputField.IMAGECHOICE_TYPE,
            'order': 102,
        }]:
            self.addField(g, f)

        return g

    def item_as_dict(self, item):
        return {
            'id': item.uuid,
            'name': item.name,
            'image_id': item.image.uuid,
        }

    def item_as_dict_overview(self, item):
        return {
            'id': item.uuid,
            'name': item.name,
            'thumb': item.image.thumb64,
        }
