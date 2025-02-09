# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2023 Virtual Cable S.L.
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
import logging
import typing

from django.utils.translation import gettext_lazy as _, gettext

from uds.models import Network
from uds.core import types
from uds.core.util import permissions, ensure

from ..model import ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Networks(ModelHandler):
    """
    Processes REST requests about networks
    Implements specific handling for network related requests using GUI
    """
    class NetworkItem(types.rest.ItemDictType):
        id: str
        name: str
        tags: list[str]
        net_string: str
        transports_count: int
        authenticators_count: int
        permission: types.permissions.PermissionType


    model = Network
    save_fields = ['name', 'net_string', 'tags']

    table_title = _('Networks')
    table_fields = [
        {
            'name': {
                'title': _('Name'),
                'visible': True,
                'type': 'icon',
                'icon': 'fa fa-globe text-success',
            }
        },
        {'net_string': {'title': _('Range')}},
        {
            'transports_count': {
                'title': _('Transports'),
                'type': 'numeric',
                'width': '8em',
            }
        },
        {
            'authenticators_count': {
                'title': _('Authenticators'),
                'type': 'numeric',
                'width': '8em',
            }
        },
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def get_gui(self, type_: str) -> list[typing.Any]:
        return self.add_field(
            self.add_default_fields([], ['name', 'tags']),
            {
                'name': 'net_string',
                'value': '',
                'label': gettext('Network range'),
                'tooltip': gettext(
                    'Network range. Accepts most network definitions formats (range, subnet, host, etc...'
                ),
                'type': types.ui.FieldType.TEXT,
                'order': 100,  # At end
            },
        )
        
    def item_as_dict(self, item: 'Model') -> NetworkItem:
        item = ensure.is_instance(item, Network)
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'net_string': item.net_string,
            'transports_count': item.transports.count(),
            'authenticators_count': item.authenticators.count(),
            'permission': permissions.effective_permissions(self._user, item),
        }
