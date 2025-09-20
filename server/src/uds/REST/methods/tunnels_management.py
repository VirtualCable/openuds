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
import dataclasses
import logging
import typing

from django.utils.translation import gettext, gettext_lazy as _
from django.db.models import Model

import uds.core.types.permissions
from uds.core import exceptions, types, consts
from uds.core.types.rest import TableInfo
from uds.core.util import permissions, validators, ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds import models
from uds.REST.model import DetailHandler, ModelHandler


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class TunnelServerItem(types.rest.BaseRestItem):
    id: str
    hostname: str
    ip: str
    mac: str
    maintenance: bool


class TunnelServers(DetailHandler[TunnelServerItem]):
    CUSTOM_METHODS = ['maintenance']

    REST_API_INFO = types.rest.api.RestApiInfo(
        name='TunnelServers', description='Tunnel servers assigned to a tunnel'
    )

    def get_items(
        self, parent: 'Model', item: typing.Optional[str]
    ) -> types.rest.ItemsResult[TunnelServerItem]:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            multi = False
            if item is None:
                multi = True
                q = self.filter_queryset(parent.servers.all())
            else:
                q = parent.servers.filter(uuid=process_uuid(item))
            res: list[TunnelServerItem] = [
                TunnelServerItem(
                    id=i.uuid,
                    hostname=i.hostname,
                    ip=i.ip,
                    mac=i.mac if i.mac != consts.MAC_UNKNOWN else '',
                    maintenance=i.maintenance_mode,
                )
                for i in q
            ]

            if multi:
                return res
            if not res:
                raise exceptions.rest.NotFound(f'Tunnel server {item} not found')
            return res[0]
        except exceptions.rest.HandlerError:
            raise
        except Exception as e:
            logger.error('Error getting tunnel servers for %s: %s', parent, e)
            raise exceptions.rest.ResponseError(_('Error getting tunnel servers')) from e

    def get_table(self, parent: 'Model') -> TableInfo:
        parent = ensure.is_instance(parent, models.ServerGroup)
        return (
            ui_utils.TableBuilder(_('Servers of {0}').format(parent.name))
            .text_column(name='hostname', title=_('Hostname'))
            .text_column(name='ip', title=_('Ip'))
            .text_column(name='mac', title=_('Mac'))
            .dict_column(
                name='maintenance',
                title=_('State'),
                dct={True: _('Maintenance'), False: _('Normal')},
            )
            .row_style(prefix='row-maintenance-', field='maintenance')
        ).build()

    # Cannot save a tunnel server, it's not editable...

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            parent.servers.remove(models.Server.objects.get(uuid=process_uuid(item)))
        except models.Server.DoesNotExist:
            raise exceptions.rest.NotFound(_('Tunnel server not found')) from None
        except Exception as e:
            logger.error('Error deleting tunnel server %s from %s: %s', item, parent, e)
            raise exceptions.rest.ResponseError(_('Error deleting tunnel server')) from None

    # Custom methods
    def maintenance(self, parent: 'Model', id: str) -> typing.Any:
        """
        API:
            Custom method that swaps maintenance mode state for a tunnel server

        """
        parent = ensure.is_instance(parent, models.ServerGroup)
        item = models.Server.objects.get(uuid=process_uuid(id))
        self.check_access(item, uds.core.types.permissions.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return 'ok'


@dataclasses.dataclass
class TunnelItem(types.rest.BaseRestItem):
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

    PATH = 'tunnels'
    NAME = 'tunnels'
    MODEL = models.ServerGroup
    FILTER = {'type': types.servers.ServerType.TUNNEL}
    CUSTOM_METHODS = [
        types.rest.ModelCustomMethod('tunnels', needs_parent=True),
        types.rest.ModelCustomMethod('assign', needs_parent=True),
    ]

    DETAIL = {'servers': TunnelServers}
    FIELDS_TO_SAVE = ['name', 'comments', 'host:', 'port:0']

    TABLE = (
        ui_utils.TableBuilder(_('Tunnels'))
        .icon(name='name', title=_('Name'))
        .text_column(name='comments', title=_('Comments'))
        .text_column(name='host', title=_('Host'))
        .numeric_column(name='port', title=_('Port'), width='6em')
        .numeric_column(name='servers_count', title=_('Servers'), width='1rem')
        .text_column(name='tags', title=_('tags'), visible=False)
        .build()
    )

    REST_API_INFO = types.rest.api.RestApiInfo(
        name='Tunnels',
        description='Tunnel management',
        gui_type=types.rest.api.RestApiInfoGuiType.UNTYPED,
    )

    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        return (
            ui_utils.GuiBuilder()
            .add_stock_field(types.rest.stock.StockField.NAME)
            .add_stock_field(types.rest.stock.StockField.COMMENTS)
            .add_stock_field(types.rest.stock.StockField.TAGS)
            .add_text(
                name='host',
                label=gettext('Hostname'),
                tooltip=gettext(
                    'Hostname or IP address of the server where the tunnel is visible by the users'
                ),
            )
            .add_numeric(
                name='port',
                default=443,
                label=gettext('Port'),
                tooltip=gettext('Port where the tunnel is visible by the users'),
            )
            .build()
        )

    def get_item(self, item: 'Model') -> TunnelItem:
        item = ensure.is_instance(item, models.ServerGroup)
        return TunnelItem(
            id=item.uuid,
            name=item.name,
            comments=item.comments,
            host=item.host,
            port=item.port,
            tags=[tag.tag for tag in item.tags.all()],
            transports_count=item.transports.count(),
            servers_count=item.servers.count(),
            permission=permissions.effective_permissions(self._user, item),
        )

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
        self.check_access(parent, uds.core.types.permissions.PermissionType.MANAGEMENT)

        server: typing.Optional['models.Server'] = None  # Avoid warning on reference before assignment

        item = self._args[-1]

        if not item:
            raise exceptions.rest.RequestError('No server specified')

        try:
            server = models.Server.objects.get(uuid=process_uuid(item))
            self.check_access(server, uds.core.types.permissions.PermissionType.READ)
            parent.servers.add(server)
        except models.Server.DoesNotExist:
            raise exceptions.rest.NotFound(_('Tunnel server not found')) from None
        except Exception as e:
            logger.error('Error assigning server %s to %s: %s', item, parent, e)
            raise exceptions.rest.ResponseError(_('Error assigning server')) from None

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
