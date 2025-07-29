# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import datetime

from django.utils.translation import gettext as _
from uds.core import types

from uds.models import UserService, Provider
from uds.core.types.states import State
from uds.core.util.model import process_uuid
from uds.REST.model import DetailHandler
from uds.core.util import ensure, ui as ui_utils

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class ServicesUsageItem(types.rest.BaseRestItem):
    id: str
    state_date: datetime.datetime
    creation_date: datetime.datetime
    unique_id: str
    friendly_name: str
    owner: str
    owner_info: dict[str, str]
    service: str
    service_id: str
    pool: str
    pool_id: str
    ip: str
    source_host: str
    source_ip: str
    in_use: bool


class ServicesUsage(DetailHandler[ServicesUsageItem]):
    """
    Rest handler for Assigned Services, which parent is Service
    """

    @staticmethod
    def item_as_dict(item: UserService) -> ServicesUsageItem:
        """
        Converts an assigned/cached service db item to a dictionary for REST response
        :param item: item to convert
        :param is_cache: If item is from cache or not
        """
        with item.properties as p:
            props = dict(p)

        if item.user is None:
            owner = ''
            owner_info = {'auth_id': '', 'user_id': ''}
        else:
            owner = item.user.pretty_name
            owner_info = {'auth_id': item.user.manager.uuid, 'user_id': item.user.uuid}

        return {
            'id': item.uuid,
            'state_date': item.state_date,
            'creation_date': item.creation_date,
            'unique_id': item.unique_id,
            'friendly_name': item.friendly_name,
            'owner': owner,
            'owner_info': owner_info,
            'service': item.deployed_service.service.name,
            'service_id': item.deployed_service.service.uuid,
            'pool': item.deployed_service.name,
            'pool_id': item.deployed_service.uuid,
            'ip': props.get('ip', _('unknown')),
            'source_host': item.src_hostname,
            'source_ip': item.src_ip,
            'in_use': item.in_use,
        }

    def get_items(
        self, parent: 'Model', item: typing.Optional[str]
    ) -> types.rest.ItemsResult[ServicesUsageItem]:
        parent = ensure.is_instance(parent, Provider)
        try:
            if item is None:
                userservices_query = UserService.objects.filter(deployed_service__service__provider=parent)
            else:
                userservices_query = UserService.objects.filter(
                    deployed_service__service_uuid=process_uuid(item)
                )

            return [
                ServicesUsage.item_as_dict(k)
                for k in userservices_query.filter(state=State.USABLE)
                .order_by('creation_date')
                .prefetch_related('deployed_service', 'deployed_service__service', 'user', 'user__manager')
            ]

        except Exception:
            logger.exception('get_items')
            raise self.invalid_item_response()

    def get_table_info(self, parent: 'Model') -> types.rest.TableInfo:
        parent = ensure.is_instance(parent, Provider)
        return (
            ui_utils.TableBuilder(_('Services Usage'))
            .datetime(name='state_date', title=_('Access'))
            .string(name='owner', title=_('Owner'))
            .string(name='service', title=_('Service'))
            .string(name='pool', title=_('Pool'))
            .string(name='unique_id', title='Unique ID')
            .string(name='ip', title=_('IP'))
            .string(name='friendly_name', title=_('Friendly name'))
            .string(name='source_ip', title=_('Src Ip'))
            .string(name='source_host', title=_('Src Host'))
            .row_style(prefix='row-state-', field='state')
            .build()
        )

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, Provider)
        userservice: UserService
        try:
            userservice = UserService.objects.get(
                uuid=process_uuid(item), deployed_service__service__provider=parent
            )
        except Exception:
            raise self.invalid_item_response()

        logger.debug('Deleting user service')
        if userservice.state in (State.USABLE, State.REMOVING):
            userservice.release()
        elif userservice.state == State.PREPARING:
            userservice.cancel()
        elif userservice.state == State.REMOVABLE:
            raise self.invalid_item_response(_('Item already being removed'))
        else:
            raise self.invalid_item_response(_('Item is not removable'))
