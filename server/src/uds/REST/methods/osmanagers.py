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
import collections.abc

from django.utils.translation import gettext, gettext_lazy as _

from uds.core import osmanagers
from uds.core.environment import Environment
from uds.core.util import permissions, ensure
from uds.models import OSManager
from uds.REST import NotFound, RequestError
from uds.REST.model import ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /osm path


class OsManagers(ModelHandler):
    model = OSManager
    save_fields = ['name', 'comments', 'tags']

    table_title = typing.cast(str, _('OS Managers'))
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'comments': {'title': _('Comments')}},
        {'deployed_count': {'title': _('Used by'), 'type': 'numeric', 'width': '8em'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def osmToDict(self, osm: OSManager) -> dict[str, typing.Any]:
        type_ = osm.get_type()
        return {
            'id': osm.uuid,
            'name': osm.name,
            'tags': [tag.tag for tag in osm.tags.all()],
            'deployed_count': osm.deployedServices.count(),
            'type': type_.get_type(),
            'type_name': type_.name(),
            'servicesTypes': [type_.servicesType],  # A list for backward compatibility. TODO: To be removed when admin interface is changed
            'comments': osm.comments,
            'permission': permissions.effective_permissions(self._user, osm),
        }

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        item = ensure.is_instance(item, OSManager)
        return self.osmToDict(item)

    def checkDelete(self, item: 'Model') -> None:
        item = ensure.is_instance(item, OSManager)
        # Only can delete if no ServicePools attached
        if item.deployedServices.count() > 0:
            raise RequestError(
                gettext('Can\'t delete an OS Manager with services pools associated')
            )

    # Types related
    def enum_types(self) -> collections.abc.Iterable[type[osmanagers.OSManager]]:
        return osmanagers.factory().providers().values()

    # Gui related
    def getGui(self, type_: str) -> list[typing.Any]:
        try:
            osmanagerType = osmanagers.factory().lookup(type_)

            if not osmanagerType:
                raise NotFound('OS Manager type not found')

            osmanager = osmanagerType(Environment.getTempEnv(), None)

            return self.addDefaultFields(
                osmanager.guiDescription(),  # type: ignore  # may raise an exception if lookup fails
                ['name', 'comments', 'tags'],
            )
        except:
            raise NotFound('type not found')
