# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import re
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import types, consts
from uds.core.environment import Environment
from uds.core.ui import gui
from uds.core.util import permissions
from uds.core.util.model import processUuid
from uds.models import RegisteredServerGroup, RegisteredServer
from uds.REST import NotFound
from uds.REST.model import ModelHandler, DetailHandler

from .users_groups import Groups, Users

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db import models

    from uds.core.module import Module

logger = logging.getLogger(__name__)


class TunnelServers(DetailHandler):
    custom_methods = ['maintenance']

    def getItems(self, parent: 'RegisteredServerGroup', item: typing.Optional[str]):
        try:
            multi = False
            if item is None:
                multi = True
                q = parent.servers.all().order_by('name')
            else:
                q = parent.servers.filter(uuid=processUuid(item))
            res = []
            i = None
            for i in q:
                val = {
                    'id': i.uuid,
                    'hostname': i.hostname,
                }
                res.append(val)
            if multi:
                return res
            if not i:
                raise Exception('Item not found')
            return res[0]
        except Exception as e:
            logger.exception('REST groups')
            raise self.invalidItemException() from e

    def getTitle(self, parent: 'RegisteredServerGroup') -> str:
        try:
            return _('Servers of of {0}').format(parent.name)
        except Exception:
            return _('Servers')

    def getFields(self, parent: 'RegisteredServerGroup') -> typing.List[typing.Any]:
        return [
            {
                'hostname': {
                    'title': _('Hostname'),
                }
            },
            {'state': {'title': _('State')}},
        ]

    def saveItem(self, parent: 'RegisteredServerGroup', item: typing.Optional[str]) -> None:
        # Item is always None here, because we can "add" existing servers to a group, but not create new ones
        server: typing.Optional['RegisteredServer'] = None  # Avoid warning on reference before assignment
        if item is not None:
            raise self.invalidRequestException('Cannot create new servers from here')

        try:
            server = RegisteredServer.objects.get(uuid=processUuid(self._params['id']))
            parent.servers.add(server)
        except Exception:
            raise self.invalidItemException() from None

        # TODO: implement this
        raise self.invalidRequestException() from None

    def deleteItem(self, parent: 'RegisteredServerGroup', item: str) -> None:
        try:
            group = parent.servers.remove(RegisteredServer.objects.get(uuid=processUuid(item)))
        except Exception:
            raise self.invalidItemException() from None

    # Custom methods
    def maintenance(self, parent: 'RegisteredServerGroup') -> typing.Any:
        """
        Custom method that swaps maintenance mode state for a provider
        :param item:
        """
        item = RegisteredServer.objects.get(uuid=processUuid(self._params['id']))
        self.ensureAccess(item, permissions.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return 'ok'


# Enclosed methods under /auth path
class Tunnels(ModelHandler):
    model = RegisteredServerGroup
    model_filter = {'kind': types.servers.Type.TUNNEL}

    detail = {'servers': TunnelServers}
    save_fields = ['name', 'comments', 'host:', 'port:0']

    table_title = _('Tunnels')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'comments': {'title': _('Comments')}},
        {'host': {'title': _('Host')}},
        {'servers_count': {'title': _('Users'), 'type': 'numeric', 'width': '1rem'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        return self.addField(
            self.addDefaultFields([], ['name', 'comments', 'tags']),
            {
                'name': 'net_string',
                'value': '',
                'label': gettext('Network range'),
                'tooltip': gettext(
                    'Network range. Accepts most network definitions formats (range, subnet, host, etc...'
                ),
                'type': gui.InputField.Types.TEXT,
                'order': 100,  # At end
            },
        )

    def item_as_dict(self, item: 'RegisteredServerGroup') -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'host': item.pretty_host,
            'tags': [tag.tag for tag in item.tags.all()],
            'transports_count': item.transports.count(),
            'servers_count': item.servers.count(),
            'permission': permissions.getEffectivePermission(self._user, item),
        }
