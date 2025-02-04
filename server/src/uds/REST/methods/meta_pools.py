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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import types, exceptions
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core.ui import gui
from uds.core.util import ensure, permissions
from uds.core.util.model import process_uuid
from uds.core.types.states import State
from uds.models import Image, MetaPool, ServicePoolGroup
from uds.REST.methods.op_calendars import AccessCalendars
from uds.REST.model import ModelHandler

from .meta_service_pools import MetaAssignedService, MetaServicesPool
from .user_services import Groups

if typing.TYPE_CHECKING:
    from django.db.models import Model

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
        {
            'policy': {
                'title': _('Policy'),
                'type': 'dict',
                'dict': dict(types.pools.LoadBalancingPolicy.enumerate()),
            }
        },
        {
            'ha_policy': {
                'title': _('HA Policy'),
                'type': 'dict',
                'dict': dict(types.pools.HighAvailabilityPolicy.enumerate()),
            }
        },
        {'user_services_count': {'title': _('User services'), 'type': 'number'}},
        {'user_services_in_preparation': {'title': _('In Preparation')}},
        {'visible': {'title': _('Visible'), 'type': 'callback'}},
        {'pool_group_name': {'title': _('Pool Group')}},
        {'label': {'title': _('Label')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    custom_methods = [
        types.rest.ModelCustomMethod('set_fallback_access', True),
        types.rest.ModelCustomMethod('get_fallback_access', True),
    ]

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        item = ensure.is_instance(item, MetaPool)
        # if item does not have an associated service, hide it (the case, for example, for a removed service)
        # Access from dict will raise an exception, and item will be skipped
        pool_group_id = None
        pool_group_name = _('Default')
        pool_group_thumb = DEFAULT_THUMB_BASE64
        if item.servicesPoolGroup is not None:
            pool_group_id = item.servicesPoolGroup.uuid
            pool_group_name = item.servicesPoolGroup.name
            if item.servicesPoolGroup.image is not None:
                pool_group_thumb = item.servicesPoolGroup.image.thumb64

        all_pools = item.members.all()
        userservices_total = sum(
            (i.pool.userServices.exclude(state__in=State.INFO_STATES).count() for i in all_pools)
        )
        userservices_in_preparation = sum(
            (i.pool.userServices.filter(state=State.PREPARING).count()) for i in all_pools
        )

        val = {
            'id': item.uuid,
            'name': item.name,
            'short_name': item.short_name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'thumb': item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64,
            'image_id': item.image.uuid if item.image is not None else None,
            'servicesPoolGroup_id': pool_group_id,
            'pool_group_name': pool_group_name,
            'pool_group_thumb': pool_group_thumb,
            'user_services_count': userservices_total,
            'user_services_in_preparation': userservices_in_preparation,
            'visible': item.visible,
            'policy': str(item.policy),
            'fallbackAccess': item.fallbackAccess,
            'permission': permissions.effective_permissions(self._user, item),
            'calendar_message': item.calendar_message,
            'transport_grouping': item.transport_grouping,
            'ha_policy': str(item.ha_policy),
        }

        return val

    # Gui related
    def get_gui(self, type_: str) -> list[typing.Any]:
        local_gui = self.add_default_fields([], ['name', 'comments', 'tags'])

        for field in [
            {
                'name': 'short_name',
                'type': 'text',
                'label': _('Short name'),
                'tooltip': _('Short name for user service visualization'),
                'required': False,
                'length': 32,
                'order': 0 - 95,
            },
            {
                'name': 'policy',
                'choices': [gui.choice_item(k, str(v)) for k, v in types.pools.LoadBalancingPolicy.enumerate()],
                'label': gettext('Load balancing policy'),
                'tooltip': gettext('Service pool load balancing policy'),
                'type': types.ui.FieldType.CHOICE,
                'order': 100,
            },
            {
                'name': 'ha_policy',
                'choices': [
                    gui.choice_item(k, str(v)) for k, v in types.pools.HighAvailabilityPolicy.enumerate()
                ],
                'label': gettext('HA Policy'),
                'tooltip': gettext(
                    'Service pool High Availability policy. If enabled and a pool fails, it will be restarted in another pool. Enable with care!.'
                ),
                'type': types.ui.FieldType.CHOICE,
                'order': 101,
            },
            {
                'name': 'image_id',
                'choices': [gui.choice_image(-1, '--------', DEFAULT_THUMB_BASE64)]
                + gui.sorted_choices(
                    [gui.choice_image(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]
                ),
                'label': gettext('Associated Image'),
                'tooltip': gettext('Image assocciated with this service'),
                'type': types.ui.FieldType.IMAGECHOICE,
                'order': 120,
                'tab': types.ui.Tab.DISPLAY,
            },
            {
                'name': 'servicesPoolGroup_id',
                'choices': [gui.choice_image(-1, _('Default'), DEFAULT_THUMB_BASE64)]
                + gui.sorted_choices(
                    [gui.choice_image(v.uuid, v.name, v.thumb64) for v in ServicePoolGroup.objects.all()]
                ),
                'label': gettext('Pool group'),
                'tooltip': gettext('Pool group for this pool (for pool classify on display)'),
                'type': types.ui.FieldType.IMAGECHOICE,
                'order': 121,
                'tab': types.ui.Tab.DISPLAY,
            },
            {
                'name': 'visible',
                'value': True,
                'label': gettext('Visible'),
                'tooltip': gettext('If active, metapool will be visible for users'),
                'type': types.ui.FieldType.CHECKBOX,
                'order': 123,
                'tab': types.ui.Tab.DISPLAY,
            },
            {
                'name': 'calendar_message',
                'value': '',
                'label': gettext('Calendar access denied text'),
                'tooltip': gettext(
                    'Custom message to be shown to users if access is limited by calendar rules.'
                ),
                'type': types.ui.FieldType.TEXT,
                'order': 124,
                'tab': types.ui.Tab.DISPLAY,
            },
            {
                'name': 'transport_grouping',
                'choices': [
                    gui.choice_item(k, str(v)) for k, v in types.pools.TransportSelectionPolicy.enumerate()
                ],
                'label': gettext('Transport Selection'),
                'tooltip': gettext('Transport selection policy'),
                'type': types.ui.FieldType.CHOICE,
                'order': 125,
                'tab': types.ui.Tab.DISPLAY,
            },
        ]:
            self.add_field(local_gui, field)

        return local_gui

    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        # logger.debug(self._params)
        try:
            # **** IMAGE ***
            imgid = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: %s', imgid)
            try:
                if imgid != '-1':
                    image = Image.objects.get(uuid=process_uuid(imgid))
                    fields['image_id'] = image.id
            except Exception:
                logger.exception('At image recovering')

            # Servicepool Group
            servicespool_group_id = fields['servicesPoolGroup_id']
            fields['servicesPoolGroup_id'] = None
            logger.debug('servicesPoolGroup_id: %s', servicespool_group_id)
            try:
                if servicespool_group_id != '-1':
                    spgrp = ServicePoolGroup.objects.get(uuid=process_uuid(servicespool_group_id))
                    fields['servicesPoolGroup_id'] = spgrp.id
            except Exception:
                logger.exception('At service pool group recovering')

        except (exceptions.rest.RequestError, exceptions.rest.ResponseError):
            raise
        except Exception as e:
            raise exceptions.rest.RequestError(str(e))

        logger.debug('Fields: %s', fields)

    def delete_item(self, item: 'Model') -> None:
        item = ensure.is_instance(item, MetaPool)
        item.delete()

    # Set fallback status
    def set_fallback_access(self, item: MetaPool) -> typing.Any:
        """
        API:
            Description:
                Sets the fallback access for a metapool

            Response:
                200: All fine, no data returned
        """
        self.ensure_has_access(item, types.permissions.PermissionType.MANAGEMENT)

        fallback = self._params.get('fallbackAccess', 'ALLOW')
        logger.debug('Setting fallback of %s to %s', item.name, fallback)
        item.fallbackAccess = fallback
        item.save()
        return ''

    def get_fallback_access(self, item: MetaPool) -> typing.Any:
        return item.fallbackAccess

    #  Returns the action list based on current element, for calendars (nothing right now for metapools, because no actions are allowed)
    def actions_list(self, item: MetaPool) -> typing.Any:
        valid_actions = ()
        return valid_actions
