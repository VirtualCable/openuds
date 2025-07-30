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
from uds.core import ui
from uds.core.util import ensure, permissions, ui as ui_utils
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


class MetaPoolItem(types.rest.BaseRestItem):
    id: str
    name: str
    short_name: str
    tags: list[str]
    comments: str
    thumb: str
    image_id: str | None
    servicesPoolGroup_id: str | None
    pool_group_name: str | None
    pool_group_thumb: str | None
    user_services_count: int
    user_services_in_preparation: int
    visible: bool
    policy: str
    fallbackAccess: str
    permission: int
    calendar_message: str
    transport_grouping: int
    ha_policy: str


class MetaPools(ModelHandler[MetaPoolItem]):
    """
    Handles Services Pools REST requests
    """

    MODEL = MetaPool
    DETAIL = {
        'pools': MetaServicesPool,
        'services': MetaAssignedService,
        'groups': Groups,
        'access': AccessCalendars,
    }

    FIELDS_TO_SAVE = [
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

    TABLE = (
        ui_utils.TableBuilder(_('Meta Pools'))
        .text_column(name='name', title=_('Name'))
        .text_column(name='comments', title=_('Comments'))
        .dict_column(
            name='policy',
            title=_('Policy'),
            dct=dict(types.pools.LoadBalancingPolicy.enumerate()),
        )
        .dict_column(
            name='ha_policy',
            title=_('HA Policy'),
            dct=dict(types.pools.HighAvailabilityPolicy.enumerate()),
        )
        .numeric_column(name='user_services_count', title=_('User services'))
        .numeric_column(name='user_services_in_preparation', title=_('In Preparation'))
        .boolean(name='visible', title=_('Visible'))
        .text_column(name='pool_group_name', title=_('Pool Group'), width='16em')
        .text_column(name='short_name', title=_('Label'))
        .text_column(name='tags', title=_('tags'), visible=False)
        .build()
    )

    # table_title = _('Meta Pools')
    # xtable_fields = [
    #     {'name': {'title': _('Name')}},
    #     {'comments': {'title': _('Comments')}},
    #     {
    #         'policy': {
    #             'title': _('Policy'),
    #             'type': 'dict',
    #             'dict': dict(types.pools.LoadBalancingPolicy.enumerate()),
    #         }
    #     },
    #     {
    #         'ha_policy': {
    #             'title': _('HA Policy'),
    #             'type': 'dict',
    #             'dict': dict(types.pools.HighAvailabilityPolicy.enumerate()),
    #         }
    #     },
    #     {'user_services_count': {'title': _('User services'), 'type': 'number'}},
    #     {'user_services_in_preparation': {'title': _('In Preparation')}},
    #     {'visible': {'title': _('Visible'), 'type': 'callback'}},
    #     {'pool_group_name': {'title': _('Pool Group')}},
    #     {'label': {'title': _('Label')}},
    #     {'tags': {'title': _('tags'), 'visible': False}},
    # ]

    CUSTOM_METHODS = [
        types.rest.ModelCustomMethod('set_fallback_access', True),
        types.rest.ModelCustomMethod('get_fallback_access', True),
    ]

    def item_as_dict(self, item: 'Model') -> MetaPoolItem:
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

        return {
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

    # Gui related
    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:

        return (
            ui_utils.GuiBuilder()
            .add_stock_field(types.rest.stock.StockField.TAGS)
            .add_text(
                name='short_name',
                label=gettext('Short name'),
                tooltip=gettext('Short name for user service visualization'),
                length=32,
            )
            .add_stock_field(types.rest.stock.StockField.NAME)
            .add_stock_field(types.rest.stock.StockField.COMMENTS)
            .set_order(100)
            .add_multichoice(
                name='policy',
                label=gettext('Load balancing policy'),
                choices=[ui.gui.choice_item(k, str(v)) for k, v in types.pools.LoadBalancingPolicy.enumerate()],
                tooltip=gettext('Service pool load balancing policy'),
            )
            .add_choice(
                name='ha_policy',
                label=gettext('HA Policy'),
                choices=[
                    ui.gui.choice_item(k, str(v)) for k, v in types.pools.HighAvailabilityPolicy.enumerate()
                ],
                tooltip=gettext(
                    'Service pool High Availability policy. If enabled and a pool fails, it will be restarted in another pool. Enable with care!'
                ),
            )
            .new_tab(types.ui.Tab.DISPLAY)
            .add_image_choice()
            .add_image_choice(
                name='servicesPoolGroup_id',
                label=gettext('Pool group'),
                choices=[
                    ui.gui.choice_image(
                        x.uuid, x.name, x.image.thumb64 if x.image is not None else DEFAULT_THUMB_BASE64
                    )
                    for x in ServicePoolGroup.objects.all()
                ],
                tooltip=gettext('Pool group for this pool (for pool classify on display)'),
            )
            .add_checkbox(
                name='visible',
                label=gettext('Visible'),
                tooltip=gettext('If active, metapool will be visible for users'),
                default=True,
            )
            .add_text(
                name='calendar_message',
                label=gettext('Calendar access denied text'),
                tooltip=gettext('Custom message to be shown to users if access is limited by calendar rules.'),
            )
            .add_choice(
                name='transport_grouping',  # Transport Selection
                label=gettext('Transport Selection'),
                choices=[
                    ui.gui.choice_item(k, str(v)) for k, v in types.pools.TransportSelectionPolicy.enumerate()
                ],
                tooltip=gettext('Transport selection policy'),
            )
            .build()
        )

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
            Sets the fallback access for a metapool
        """
        self.check_access(item, types.permissions.PermissionType.MANAGEMENT)

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
