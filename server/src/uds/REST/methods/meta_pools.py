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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from django.utils.translation import ugettext, ugettext_lazy as _
from uds.models import MetaPool, Image, ServicesPoolGroup
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.util.State import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.core.util import permissions
from uds.REST.model import ModelHandler
from uds.REST import RequestError, ResponseError
from uds.core.ui.UserInterface import gui
from uds.REST.methods.op_calendars import AccessCalendars

from .user_services import Groups
from .meta_service_pools import MetaServicesPool, MetaAssignedService

logger = logging.getLogger(__name__)


class MetaPools(ModelHandler):
    """
    Handles Services Pools REST requests
    """
    model = MetaPool
    detail = {
        'pools': MetaServicesPool,
        'services': MetaAssignedService,
        'groups': Groups,
        'access': AccessCalendars,
    }

    save_fields = ['name', 'short_name', 'comments', 'tags',
                   'image_id', 'servicesPoolGroup_id', 'visible', 'policy']

    table_title = _('Meta Pools')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'comments': {'title': _('Comments')}},
        {'policy': {'title': _('Policy'), 'type': 'dict', 'dict': MetaPool.TYPES}},
        {'user_services_count': {'title': _('User services'), 'type': 'number'}},
        {'user_services_in_preparation': {'title': _('In Preparation')}},
        {'visible': {'title': _('Visible'), 'type': 'callback'}},
        {'pool_group_name': {'title': _('Pool Group')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    custom_methods = [('setFallbackAccess', True), ('getFallbackAccess', True)]

    def item_as_dict(self, item: MetaPool):
        # if item does not have an associated service, hide it (the case, for example, for a removed service)
        # Access from dict will raise an exception, and item will be skipped
        poolGroupId = None
        poolGroupName = _('Default')
        poolGroupThumb = DEFAULT_THUMB_BASE64
        if item.servicesPoolGroup is not None:
            poolGroupId = item.servicesPoolGroup.uuid
            poolGroupName = item.servicesPoolGroup.name
            if item.servicesPoolGroup.image is not None:
                poolGroupThumb = item.servicesPoolGroup.image.thumb64

        allPools = item.pools.all()
        userServicesCount = sum((i.userServices.exclude(state__in=State.INFO_STATES).count() for i in allPools))
        userServicesInPreparation = sum((i.userServices.filter(state=State.PREPARING).count()) for i in allPools)

        val = {
            'id': item.uuid,
            'name': item.name,
            'short_name': item.short_name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'thumb': item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64,
            'image_id': item.image.uuid if item.image is not None else None,
            'servicesPoolGroup_id': poolGroupId,
            'pool_group_name': poolGroupName,
            'pool_group_thumb': poolGroupThumb,
            'user_services_count': userServicesCount,
            'user_services_in_preparation': userServicesInPreparation,
            'visible': item.visible,
            'policy': item.policy,
            'fallbackAccess': item.fallbackAccess,
            'permission': permissions.getEffectivePermission(self._user, item),
        }

        return val

    # Gui related
    def getGui(self, type_):

        g = self.addDefaultFields([], ['name', 'short_name', 'comments', 'tags'])

        for f in [{
            'name': 'policy',
            'values': [gui.choiceItem(k, str(v)) for k, v in MetaPool.TYPES.items()],
            'label': ugettext('Policy'),
            'tooltip': ugettext('Service pool policy'),
            'type': gui.InputField.CHOICE_TYPE,
            'order': 100,
        }, {
            'name': 'image_id',
            'values': [gui.choiceImage(-1, '--------', DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]),
            'label': ugettext('Associated Image'),
            'tooltip': ugettext('Image assocciated with this service'),
            'type': gui.InputField.IMAGECHOICE_TYPE,
            'order': 120,
            'tab': ugettext('Display'),
        }, {
            'name': 'servicesPoolGroup_id',
            'values': [gui.choiceImage(-1, _('Default'), DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.thumb64) for v in ServicesPoolGroup.objects.all()]),
            'label': ugettext('Pool group'),
            'tooltip': ugettext('Pool group for this pool (for pool classify on display)'),
            'type': gui.InputField.IMAGECHOICE_TYPE,
            'order': 121,
            'tab': ugettext('Display'),
        }, {
            'name': 'visible',
            'value': True,
            'label': ugettext('Visible'),
            'tooltip': ugettext('If active, metapool will be visible for users'),
            'type': gui.InputField.CHECKBOX_TYPE,
            'order': 123,
            'tab': ugettext('Display'),
        }]:
            self.addField(g, f)

        return g

    def beforeSave(self, fields):
        # logger.debug(self._params)
        try:
            # **** IMAGE ***
            imgId = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: {}'.format(imgId))
            try:
                if imgId != '-1':
                    image = Image.objects.get(uuid=processUuid(imgId))
                    fields['image_id'] = image.id
            except Exception:
                logger.exception('At image recovering')

            # Servicepool Group
            spgrpId = fields['servicesPoolGroup_id']
            fields['servicesPoolGroup_id'] = None
            logger.debug('servicesPoolGroup_id: %s', spgrpId)
            try:
                if spgrpId != '-1':
                    spgrp = ServicesPoolGroup.objects.get(uuid=processUuid(spgrpId))
                    fields['servicesPoolGroup_id'] = spgrp.id
            except Exception:
                logger.exception('At service pool group recovering')

        except (RequestError, ResponseError):
            raise
        except Exception as e:
            raise RequestError(str(e))

        logger.debug('Fields: %s', fields)

    def deleteItem(self, item):
        item.delete()

    # Logs
    def getLogs(self, item):
        try:
            return log.getLogs(item)
        except Exception:
            return []

    # Set fallback status
    def setFallbackAccess(self, item):
        self.ensureAccess(item, permissions.PERMISSION_MANAGEMENT)

        fallback = self._params.get('fallbackAccess')
        logger.debug('Setting fallback of {} to {}'.format(item.name, fallback))
        item.fallbackAccess = fallback
        item.save()
        return ''

    def getFallbackAccess(self, item):
        return item.fallbackAccess

    #  Returns the action list based on current element, for calendar
    def actionsList(self, item):
        validActions = ()
        return validActions

