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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

import uds.core.types.permissions
from uds.core import exceptions, types, consts
from uds.core.util import permissions, validators, ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds import models
from uds.REST.model import DetailHandler, ModelHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class TunnelServerItem(types.rest.ItemDictType):
    id: str
    hostname: str
    ip: str
    mac: str
    maintenance: bool


class TunnelServers(DetailHandler[TunnelServerItem]):
    # tunnels/[id]/servers
    custom_methods = ['maintenance']

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.GetItemsResult[TunnelServerItem]:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            multi = False
            if item is None:
                multi = True
                q = parent.servers.all().order_by('hostname')
            else:
                q = parent.servers.filter(uuid=process_uuid(item))
            res: list[TunnelServerItem] = [
                {
                    'id': i.uuid,
                    'hostname': i.hostname,
                    'ip': i.ip,
                    'mac': i.mac if i.mac != consts.MAC_UNKNOWN else '',
                    'maintenance': i.maintenance_mode,
                }
                for i in q
            ]

            if multi:
                return res
            if not res:
                raise Exception('Item not found')
            return res[0]
        except Exception as e:
            logger.exception('REST groups')
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            return _('Servers of {0}').format(parent.name)
        except Exception:
            return gettext('Servers')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.ServerGroup)
        return [
            {
                'hostname': {
                    'title': _('Hostname'),
                }
            },
            {'ip': {'title': _('Ip')}},
            {'mac': {'title': _('Mac')}},
            {
                'maintenance_mode': {
                    'title': _('State'),
                    'type': 'dict',
                    'dict': {True: _('Maintenance'), False: _('Normal')},
                }
            },
        ]

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-maintenance-', field='maintenance_mode')

    # Cannot save a tunnel server, it's not editable...

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            parent.servers.remove(models.Server.objects.get(uuid=process_uuid(item)))
        except Exception:
            raise self.invalid_item_response() from None

    # Custom methods
    def maintenance(self, parent: 'Model', id: str) -> typing.Any:
        """
        API:
            Custom method that swaps maintenance mode state for a tunnel server

        """
        parent = ensure.is_instance(parent, models.ServerGroup)
        item = models.Server.objects.get(uuid=process_uuid(id))
        self.ensure_has_access(item, uds.core.types.permissions.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return 'ok'

class TunnelItem(types.rest.ItemDictType):
    id: str
    name: str
    comments: str
    host: str
    port: int
    tags: list[str]
    transports_count: int
    servers_count: int
    permission: uds.core.types.permissions.PermissionType

# Enclosed methods under /auth path
class Tunnels(ModelHandler[TunnelItem]):

    path = 'tunnels'
    name = 'tunnels'
    model = models.ServerGroup
    model_filter = {'type': types.servers.ServerType.TUNNEL}
    custom_methods = [
        types.rest.ModelCustomMethod('tunnels', needs_parent=True),
        types.rest.ModelCustomMethod('assign', needs_parent=True),
    ]

    detail = {'servers': TunnelServers}
    save_fields = ['name', 'comments', 'host:', 'port:0']

    table_title = _('Tunnels')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'comments': {'title': _('Comments')}},
        {'host': {'title': _('Host')}},
        {'port': {'title': _('Port')}},
        {'servers_count': {'title': _('Servers'), 'type': 'numeric', 'width': '1rem'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        ORDER: typing.Final[ui_utils.OrderCounter] = ui_utils.OrderCounter(100)
        return self.compose_gui(
            [
                types.rest.stock.StockField.NAME,
                types.rest.stock.StockField.COMMENTS,
                types.rest.stock.StockField.TAGS,
            ],
            ui_utils.text_field(
                order=ORDER.next(),
                name='host',
                default='',
                label=gettext('Hostname'),
                tooltip=gettext(
                    'Hostname or IP address of the server where the tunnel is visible by the users'
                ),
            ),
            ui_utils.numeric_field(
                order=ORDER.next(),
                name='port',
                default=443,
                label=gettext('Port'),
                tooltip=gettext('Port where the tunnel is visible by the users'),
            ),
        )
        

    def item_as_dict(self, item: 'Model') -> TunnelItem:
        item = ensure.is_instance(item, models.ServerGroup)
        return {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'host': item.host,
            'port': item.port,
            'tags': [tag.tag for tag in item.tags.all()],
            'transports_count': item.transports.count(),
            'servers_count': item.servers.count(),
            'permission': permissions.effective_permissions(self._user, item),
        }

    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        fields['type'] = types.servers.ServerType.TUNNEL.value
        fields['port'] = int(fields['port'])
        # Ensure host is a valid IP(4 or 6) or hostname
        validators.validate_host(fields['host'])

    def validate_delete(self, item: 'Model') -> None:
        item = ensure.is_instance(item, models.ServerGroup)
        # Only can delete if no ServicePools attached
        if item.transports.count() > 0:
            raise exceptions.rest.RequestError(
                gettext('Cannot delete a tunnel server group with transports attached')
            )

    def assign(self, parent: 'Model') -> typing.Any:
        parent = ensure.is_instance(parent, models.ServerGroup)
        self.ensure_has_access(parent, uds.core.types.permissions.PermissionType.MANAGEMENT)

        server: typing.Optional['models.Server'] = None  # Avoid warning on reference before assignment

        item = self._args[-1]

        if not item:
            raise self.invalid_item_response('No server specified')

        try:
            server = models.Server.objects.get(uuid=process_uuid(item))
            self.ensure_has_access(server, uds.core.types.permissions.PermissionType.READ)
            parent.servers.add(server)
        except Exception:
            raise self.invalid_item_response() from None

        return 'ok'

    def tunnels(self, parent: 'Model') -> typing.Any:
        parent = ensure.is_instance(parent, models.ServerGroup)
        """
        Custom method that returns all tunnels of a tunnel server NOT already assigned to THIS tunnel group
        :param item:
        """
        all_servers = set(parent.servers.all())
        return [
            {
                'id': i.uuid,
                'name': i.hostname,
            }
            for i in models.Server.objects.filter(type=types.servers.ServerType.TUNNEL)
            if permissions.effective_permissions(self._user, i)
            >= uds.core.types.permissions.PermissionType.READ
            and i not in all_servers
        ]
