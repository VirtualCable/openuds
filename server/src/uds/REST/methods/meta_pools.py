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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _
from uds.models import MetaPool, Image, ServicePoolGroup
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.util.state import State
from uds.core.util.model import processUuid
from uds.core.util import permissions
from uds.REST.model import ModelHandler
from uds.REST import RequestError, ResponseError
from uds.core.ui import gui
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

    save_fields = [
        'name',
        'short_name',
        'comments',
        'tags',
        'image_id',
        'servicesPoolGroup_id',
        'visible',
        'policy',
        'ha_policy',
        'calendar_message',
        'transport_grouping',
    ]

    table_title = _('Meta Pools')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'comments': {'title': _('Comments')}},
        {'policy': {'title': _('Policy'), 'type': 'dict', 'dict': MetaPool.TYPES}},
        {'ha_policy': {'title': _('HA Policy'), 'type': 'dict', 'dict': MetaPool.HA_SELECT}},
        {'user_services_count': {'title': _('User services'), 'type': 'number'}},
        {'user_services_in_preparation': {'title': _('In Preparation')}},
        {'visible': {'title': _('Visible'), 'type': 'callback'}},
        {'pool_group_name': {'title': _('Pool Group')}},
        {'label': {'title': _('Label')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    custom_methods = [('setFallbackAccess', True), ('getFallbackAccess', True)]

    def item_as_dict(self, item: MetaPool) -> typing.Dict[str, typing.Any]:
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

        allPools = item.members.all()
        userServicesCount = sum(
            (
                i.pool.userServices.exclude(state__in=State.INFO_STATES).count()
                for i in allPools
            )
        )
        userServicesInPreparation = sum(
            (i.pool.userServices.filter(state=State.PREPARING).count())
            for i in allPools
        )

        val = {
            'id': item.uuid,
            'name': item.name,
            'short_name': item.short_name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'thumb': item.image.thumb64
            if item.image is not None
            else DEFAULT_THUMB_BASE64,
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
            'calendar_message': item.calendar_message,
            'transport_grouping': item.transport_grouping,
            'ha_policy': item.ha_policy,
        }

        return val

    # Gui related
    def getGui(self, type_: str) -> typing.List[typing.Any]:
        localGUI = self.addDefaultFields([], ['name', 'short_name', 'comments', 'tags'])

        for field in [
            {
                'name': 'policy',
                'values': [
                    gui.choiceItem(k, str(v)) for k, v in MetaPool.TYPES.items()
                ],
                'label': gettext('Policy'),
                'tooltip': gettext('Service pool policy'),
                'type': gui.InputField.Types.CHOICE,
                'order': 100,
            },
            {
                'name': 'ha_policy',
                'values': [
                    gui.choiceItem(k, str(v)) for k, v in MetaPool.HA_SELECT.items()
                ],
                'label': gettext('HA Policy'),
                'tooltip': gettext('Service pool HA policy. Enable with care!'),
                'type': gui.InputField.Types.CHOICE,
                'order': 101,
            },
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
                'order': 120,
                'tab': gui.Tab.DISPLAY,
            },
            {
                'name': 'servicesPoolGroup_id',
                'values': [gui.choiceImage(-1, _('Default'), DEFAULT_THUMB_BASE64)]
                + gui.sortedChoices(
                    [
                        gui.choiceImage(v.uuid, v.name, v.thumb64)  # type: ignore
                        for v in ServicePoolGroup.objects.all()
                    ]
                ),
                'label': gettext('Pool group'),
                'tooltip': gettext(
                    'Pool group for this pool (for pool classify on display)'
                ),
                'type': gui.InputField.Types.IMAGE_CHOICE,
                'order': 121,
                'tab': gui.Tab.DISPLAY,
            },
            {
                'name': 'visible',
                'value': True,
                'label': gettext('Visible'),
                'tooltip': gettext('If active, metapool will be visible for users'),
                'type': gui.InputField.Types.CHECKBOX,
                'order': 123,
                'tab': gui.Tab.DISPLAY,
            },
            {
                'name': 'calendar_message',
                'value': '',
                'label': gettext('Calendar access denied text'),
                'tooltip': gettext(
                    'Custom message to be shown to users if access is limited by calendar rules.'
                ),
                'type': gui.InputField.Types.TEXT,
                'order': 124,
                'tab': gui.Tab.DISPLAY,
            },
            {
                'name': 'transport_grouping',
                'values': [
                    gui.choiceItem(k, str(v))
                    for k, v in MetaPool.TRANSPORT_SELECT.items()
                ],
                'label': gettext('Transport Selection'),
                'tooltip': gettext('Transport selection policy'),
                'type': gui.InputField.Types.CHOICE,
                'order': 125,
                'tab': gui.Tab.DISPLAY,
            },
        ]:
            self.addField(localGUI, field)

        return localGUI

    def beforeSave(self, fields: typing.Dict[str, typing.Any]) -> None:
        # logger.debug(self._params)
        try:
            # **** IMAGE ***
            imgId = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: %s', imgId)
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
                    spgrp = ServicePoolGroup.objects.get(uuid=processUuid(spgrpId))
                    fields['servicesPoolGroup_id'] = spgrp.id
            except Exception:
                logger.exception('At service pool group recovering')

        except (RequestError, ResponseError):
            raise
        except Exception as e:
            raise RequestError(str(e))

        logger.debug('Fields: %s', fields)

    def deleteItem(self, item: MetaPool) -> None:
        item.delete()

    # Set fallback status
    def setFallbackAccess(self, item: MetaPool):
        self.ensureAccess(item, permissions.PermissionType.MANAGEMENT)

        fallback = self._params.get('fallbackAccess')
        logger.debug('Setting fallback of %s to %s', item.name, fallback)
        item.fallbackAccess = fallback
        item.save()
        return ''

    def getFallbackAccess(self, item: MetaPool):
        return item.fallbackAccess

    #  Returns the action list based on current element, for calendars (nothing right now for metapools, because no actions are allowed)
    def actionsList(self, item: MetaPool):
        validActions = ()
        return validActions
