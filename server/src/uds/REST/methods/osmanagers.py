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
import collections.abc
import dataclasses
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _

from uds.core import exceptions, osmanagers, types
from uds.core.environment import Environment
from uds.core.util import ensure, permissions, ui as ui_utils
from uds.models import OSManager
from uds.REST.model import ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /osm path


@dataclasses.dataclass
class OsManagerItem(types.rest.ManagedObjectItem[OSManager]):
    id: str
    name: str
    tags: list[str]
    deployed_count: int
    servicesTypes: list[str]
    comments: str
    permission: types.permissions.PermissionType


class OsManagers(ModelHandler[OsManagerItem]):

    MODEL = OSManager
    FIELDS_TO_SAVE = ['name', 'comments', 'tags']

    TABLE = (
        ui_utils.TableBuilder(_('OS Managers'))
        .icon(name='name', title=_('Name'))
        .text_column(name='type_name', title=_('Type'))
        .text_column(name='comments', title=_('Comments'))
        .numeric_column(name='deployed_count', title=_('Used by'), width='8em')
        .text_column(name='tags', title=_('Tags'), visible=False)
        .build()
    )

    def os_manager_as_dict(self, item: OSManager) -> OsManagerItem:
        type_ = item.get_type()
        ret_value = OsManagerItem(
            id=item.uuid,
            name=item.name,
            tags=[tag.tag for tag in item.tags.all()],
            deployed_count=item.deployedServices.count(),
            servicesTypes=[
                type_.services_types
            ],  # A list for backward compatibility. TODO: To be removed when admin interface is changed
            comments=item.comments,
            permission=permissions.effective_permissions(self._user, item),
            item=item,
        )
        # Fill type and type_name
        return ret_value

    def get_item(self, item: 'Model') -> OsManagerItem:
        item = ensure.is_instance(item, OSManager)
        return self.os_manager_as_dict(item)

    def validate_delete(self, item: 'Model') -> None:
        item = ensure.is_instance(item, OSManager)
        # Only can delete if no ServicePools attached
        if item.deployedServices.count() > 0:
            raise exceptions.rest.RequestError(
                gettext('Can\'t delete an OS Manager with services pools associated')
            )

    # Types related
    def enum_types(self) -> collections.abc.Iterable[type[osmanagers.OSManager]]:
        return osmanagers.factory().providers().values()

    # Gui related
    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        try:
            osmanager_type = osmanagers.factory().lookup(for_type)

            if not osmanager_type:
                raise exceptions.rest.NotFound('OS Manager type not found')
            with Environment.temporary_environment() as env:
                osmanager = osmanager_type(env, None)
                return (
                    ui_utils.GuiBuilder()
                    .add_stock_field(types.rest.stock.StockField.NAME)
                    .add_stock_field(types.rest.stock.StockField.TAGS)
                    .add_stock_field(types.rest.stock.StockField.COMMENTS)
                    .add_fields(osmanager.gui_description())
                    .build()
                )
        except:
            raise exceptions.rest.NotFound('type not found')
