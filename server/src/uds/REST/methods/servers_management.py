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
import datetime
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core import consts, types
from uds.core.util import net, permissions, ensure, ui as ui_utils
from uds.core.util.model import sql_now, process_uuid
from uds.core.exceptions.rest import NotFound, RequestError
from uds.REST.model import DetailHandler, ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class TokenItem(types.rest.BaseRestItem):
    id: str
    name: str
    stamp: datetime.datetime
    username: str
    ip: str
    hostname: str
    listen_port: int
    mac: str
    token: str
    type: str
    os: str


# REST API for Server Tokens management (for admin interface)
class ServersTokens(ModelHandler[TokenItem]):

    # servers/groups/[id]/servers
    model = models.Server
    model_exclude = {
        'type__in': [
            types.servers.ServerType.ACTOR,
            types.servers.ServerType.UNMANAGED,
        ]
    }
    path = 'servers'
    name = 'tokens'

    table_title = _('Registered Servers')
    table_fields = (
        ui_utils.TableBuilder(_('Registered Servers'))
        .string(name='hostname', title=_('Hostname'), visible=True)
        .string(name='ip', title=_('IP'), visible=True)
        .string(name='mac', title=_('MAC'), visible=True)
        .string(name='type', title=_('Type'), visible=False)
        .string(name='os', title=_('OS'), visible=True)
        .string(name='username', title=_('Issued by'), visible=True)
        .datetime(name='stamp', title=_('Date'), visible=True)
        .build()
    )
    
    # xtable_fields = [
    #     {'hostname': {'title': _('Hostname')}},
    #     {'ip': {'title': _('IP')}},
    #     {'type': {'title': _('Type'), 'type': 'dict', 'dict': dict(types.servers.ServerType.enumerate())}},
    #     {'os': {'title': _('OS')}},
    #     {'username': {'title': _('Issued by')}},
    #     {'stamp': {'title': _('Date'), 'type': 'datetime'}},
    # ]

    def item_as_dict(self, item: 'Model') -> TokenItem:
        item = typing.cast('models.Server', item)  # We will receive for sure
        return {
            'id': item.uuid,
            'name': str(_('Token isued by {} from {}')).format(item.register_username, item.ip),
            'stamp': item.stamp,
            'username': item.register_username,
            'ip': item.ip,
            'hostname': item.hostname,
            'listen_port': item.listen_port,
            'mac': item.mac,
            'token': item.token,
            'type': types.servers.ServerType(item.type).as_str(),
            'os': item.os_type,
        }

    def delete(self) -> str:
        """
        Processes a DELETE request
        """
        if len(self._args) != 1:
            raise RequestError('Delete need one and only one argument')

        self.check_access(
            self.model(), types.permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            self.model.objects.get(uuid=process_uuid(self._args[0])).delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return consts.OK


class ServerItem(types.rest.BaseRestItem):
    id: str
    hostname: str
    ip: str
    listen_port: int
    mac: str
    maintenance_mode: bool
    register_username: str
    stamp: datetime.datetime


# REST API For servers (except tunnel servers nor actors)
class ServersServers(DetailHandler[ServerItem]):

    custom_methods = ['maintenance', 'importcsv']

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.ItemsResult[ServerItem]:
        parent = typing.cast('models.ServerGroup', parent)  # We will receive for sure
        try:
            if item is None:
                q = parent.servers.all()
            else:
                q = parent.servers.filter(uuid=process_uuid(item))
            res: list[ServerItem] = []
            i = None
            for i in q:
                res.append(
                    {
                        'id': i.uuid,
                        'hostname': i.hostname,
                        'ip': i.ip,
                        'listen_port': i.listen_port,
                        'mac': i.mac if i.mac != consts.MAC_UNKNOWN else '',
                        'maintenance_mode': i.maintenance_mode,
                        'register_username': i.register_username,
                        'stamp': i.stamp,
                    }
                )
            if item is None:
                return res
            if not i:
                raise Exception('Item not found')  # Threated on the except below
            return res[0]
        except Exception as e:
            logger.exception('REST servers')
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            return (_('Servers of {0}')).format(parent.name)
        except Exception:
            return str(_('Servers'))

    def get_fields(self, parent: 'Model') -> list[types.rest.TableField]:
        parent = ensure.is_instance(parent, models.ServerGroup)
        
        fields = (
            ui_utils.TableBuilder(_('Servers'))
            .string(name='hostname', title=_('Hostname'))
            .string(name='ip', title=_('Ip'))
            .string(name='mac', title=_('Mac'))
        )
        
        if parent.is_managed():
            fields.string(name='listen_port', title=_('Port'))
            
        return fields.dictionary(
            name='maintenance_mode',
            title=_('State'),
            dct={True: _('Maintenance'), False: _('Normal')},
        ).build()

        # return (
        #     [
        #         {
        #             'hostname': {
        #                 'title': _('Hostname'),
        #             }
        #         },
        #         {'ip': {'title': _('Ip')}},
        #     ]  # If not managed, we can show mac, else listen port (related to UDS Server)
        #     + (
        #         [
        #             {'mac': {'title': _('Mac')}},
        #         ]
        #         if not parent.is_managed()
        #         else [
        #             {'mac': {'title': _('Mac')}},
        #             {'listen_port': {'title': _('Port')}},
        #         ]
        #     )
        #     + [
        #         {
        #             'maintenance_mode': {
        #                 'title': _('State'),
        #                 'type': 'dict',
        #                 'dict': {True: _('Maintenance'), False: _('Normal')},
        #             }
        #         },
        #     ]
        # )

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-maintenance-', field='maintenance_mode')

    def get_gui(self, parent: 'Model', for_type: str = '') -> list[types.ui.GuiElement]:
        parent = ensure.is_instance(parent, models.ServerGroup)
        kind, subkind = parent.server_type, parent.subtype
        title = _('of type') + f' {subkind.upper()} {kind.name.capitalize()}'
        gui_builder = ui_utils.GuiBuilder(order=100)
        if kind == types.servers.ServerType.UNMANAGED:
            return (
                gui_builder.add_text(
                    name='hostname',
                    label=gettext('Hostname'),
                    tooltip=gettext('Hostname of the server. It must be resolvable by UDS'),
                    default='',
                )
                .add_text(
                    name='ip',
                    label=gettext('IP'),
                )
                .add_text(
                    name='mac',
                    label=gettext('Server MAC'),
                    tooltip=gettext('Optional MAC address of the server'),
                    default='',
                )
                .add_info(
                    name='title',
                    default=title,
                )
                .build()
            )

        return (
            gui_builder.add_text(
                name='server',
                label=gettext('Server'),
                tooltip=gettext('Server to include on group'),
                default='',
            )
            .add_info(name='title', default=title)
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, models.ServerGroup)
        # Item is the uuid of the server to add
        server: typing.Optional['models.Server'] = None  # Avoid warning on reference before assignment
        mac: str = ''
        if item is None:
            # Create new, depending on server type
            if parent.type == types.servers.ServerType.UNMANAGED:
                # Ensure mac is emty or valid
                mac = self._params['mac'].strip().upper()
                if mac and not net.is_valid_mac(mac):
                    raise self.invalid_request_response('Invalid MAC address')
                # Create a new one, and add it to group
                server = models.Server.objects.create(
                    register_username=self._user.pretty_name,
                    register_ip=self._request.ip,
                    ip=self._params['ip'],
                    hostname=self._params['hostname'],
                    listen_port=0,
                    mac=mac,
                    type=parent.type,
                    subtype=parent.subtype,
                    stamp=sql_now(),
                )
                # Add to group
                parent.servers.add(server)
                return {'id': server.uuid}
            elif parent.type == types.servers.ServerType.SERVER:
                # Get server
                try:
                    server = models.Server.objects.get(uuid=process_uuid(self._params['server']))
                    # Check server type is also SERVER
                    if server and server.type != types.servers.ServerType.SERVER:
                        logger.error('Server type for %s is not SERVER', server.host)
                        raise self.invalid_request_response() from None
                    parent.servers.add(server)
                except Exception:
                    raise self.invalid_item_response() from None
                return {'id': server.uuid}
        else:
            if parent.type == types.servers.ServerType.UNMANAGED:
                mac = self._params['mac'].strip().upper()
                if mac and not net.is_valid_mac(mac):
                    raise self.invalid_request_response('Invalid MAC address')
                try:
                    models.Server.objects.filter(uuid=process_uuid(item)).update(
                        # Update register info also on update
                        register_username=self._user.pretty_name,
                        register_ip=self._request.ip,
                        hostname=self._params['hostname'],
                        ip=self._params['ip'],
                        mac=mac,
                        stamp=sql_now(),  # Modified now
                    )
                except Exception:
                    raise self.invalid_item_response() from None

            else:
                try:
                    server = models.Server.objects.get(uuid=process_uuid(item))
                    parent.servers.add(server)
                except Exception:
                    raise self.invalid_item_response() from None
            return {'id': item}

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServerGroup)
        try:
            server = models.Server.objects.get(uuid=process_uuid(item))
            if parent.server_type == types.servers.ServerType.UNMANAGED:
                parent.servers.remove(server)  # Remove reference
                server.delete()  # and delete server
            else:
                parent.servers.remove(server)  # Just remove reference
        except Exception:
            raise self.invalid_item_response() from None

    # Custom methods
    def maintenance(self, parent: 'Model', id: str) -> typing.Any:
        parent = ensure.is_instance(parent, models.ServerGroup)
        """
        Custom method that swaps maintenance mode state for a server
        :param item:
        """
        item = models.Server.objects.get(uuid=process_uuid(id))
        self.check_access(item, types.permissions.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return 'ok'

    def importcsv(self, parent: 'Model') -> typing.Any:
        """
        We receive a json with string[][] format with the data.
        Has no header, only the data.
        """
        parent = ensure.is_instance(parent, models.ServerGroup)
        data: list[list[str]] = self._params.get('data', [])
        logger.debug('Data received: %s', data)
        # String lines can have 1, 2 or 3 fields.
        # if 1, it's a IP
        # if 2, it's a IP and a hostname. Hostame can be empty, in this case, it will be the same as IP
        # if 3, it's a IP, a hostname and a MAC. MAC can be empty, in this case, it will be UNKNOWN
        # if ip is empty and has a hostname, it will be kept, but if it has no hostname, it will be skipped
        # If the IP is invalid and has no hostname, it will be skipped
        import_errors: list[str] = []
        for line_number, row in enumerate(data, 1):
            if len(row) == 0:
                continue
            hostname = row[0].strip()
            ip = ''
            mac = consts.MAC_UNKNOWN
            if len(row) > 1:
                ip = row[1].strip()
            if len(row) > 2:
                mac = row[2].strip().upper().strip() or consts.MAC_UNKNOWN
                if mac and not net.is_valid_mac(mac):
                    import_errors.append(f'Line {line_number}: MAC {mac} is invalid, skipping')
                    continue  # skip invalid macs
            if ip and not net.is_valid_ip(ip):
                import_errors.append(f'Line {line_number}: IP {ip} is invalid, skipping')
                continue  # skip invalid ips if not empty
            # Must have at least a valid ip or a valid hostname
            if not ip and not hostname:
                import_errors.append(f'Line {line_number}: No IP or hostname, skipping')
                continue

            if hostname and not net.is_valid_host(hostname):
                # Log it has been skipped
                import_errors.append(f'Line {line_number}: Hostname {hostname} is invalid, skipping')
                continue  # skip invalid hostnames

            # Seems valid, create server if not exists already (by ip OR hostname)
            logger.debug('Creating server with ip %s, hostname %s and mac %s', ip, hostname, mac)
            try:
                q = parent.servers.all()
                if ip != '':
                    q = q.filter(ip=ip)
                if hostname != '':
                    q = q.filter(hostname=hostname)
                if q.count() == 0:
                    server = models.Server.objects.create(
                        register_username=self._user.pretty_name,
                        register_ip=self._request.ip,
                        ip=ip,
                        hostname=hostname,
                        listen_port=0,
                        mac=mac,
                        type=parent.type,
                        subtype=parent.subtype,
                        stamp=sql_now(),
                    )
                    parent.servers.add(server)  # And register it on group
                else:
                    # Log it has been skipped
                    import_errors.append(f'Line {line_number}: duplicated server, skipping')
            except Exception as e:
                import_errors.append(f'Error creating server on line {line_number}: {str(e)}')
                logger.exception('Error creating server on line %s', line_number)

        return import_errors


class GroupItem(types.rest.BaseRestItem):
    id: str
    name: str
    comments: str
    type: str
    subtype: str
    type_name: str
    tags: list[str]
    servers_count: int
    permission: types.permissions.PermissionType


class ServersGroups(ModelHandler[GroupItem]):

    custom_methods = [
        types.rest.ModelCustomMethod('stats', True),
    ]
    model = models.ServerGroup
    model_filter = {
        'type__in': [
            types.servers.ServerType.SERVER,
            types.servers.ServerType.UNMANAGED,
        ]
    }
    detail = {'servers': ServersServers}

    path = 'servers'
    name = 'groups'

    save_fields = ['name', 'comments', 'type', 'tags']  # Subtype is appended on pre_save
    table_title = _('Servers Groups')
    
    table_fields = (
        ui_utils.TableBuilder(_('Servers Groups'))
        .string(name='name', title=_('Name'), visible=True)
        .string(name='comments', title=_('Comments'))
        .string(name='type_name', title=_('Type'), visible=True)
        .string(name='type', title='', visible=False)
        .string(name='subtype', title=_('Subtype'), visible=True)
        .number(name='servers_count', title=_('Servers'), width='5rem')
        .string(name='tags', title=_('tags'), visible=False)
        .build()
    )
    
    # xtable_fields = [
    #     {'name': {'title': _('Name')}},
    #     {'comments': {'title': _('Comments')}},
    #     {'type_name': {'title': _('Type')}},
    #     {'type': {'title': '', 'visible': False}},
    #     {'subtype': {'title': _('Subtype')}},
    #     {'servers_count': {'title': _('Servers')}},
    #     {'tags': {'title': _('tags'), 'visible': False}},
    # ]

    def get_types(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[types.rest.TypeInfo, None, None]:
        for i in types.servers.ServerSubtype.manager().enum():
            yield types.rest.TypeInfo(
                name=i.description,
                type=f'{i.type.name}@{i.subtype}',
                description='',
                icon=i.icon,
                group=gettext('Managed') if i.managed else gettext('Unmanaged'),
            )

    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        if '@' not in for_type:  # If no subtype, use default
            for_type += '@default'
        kind, subkind = for_type.split('@')[:2]
        if kind == types.servers.ServerType.SERVER.name:
            kind = _('Standard')
        elif kind == types.servers.ServerType.UNMANAGED.name:
            kind = _('Unmanaged')
        title = _('of type') + f' {subkind.upper()} {kind}'

        return (
            ui_utils.GuiBuilder(
                types.rest.stock.StockField.NAME,
                types.rest.stock.StockField.COMMENTS,
                types.rest.stock.StockField.TAGS,
                order=100,
            )
            .add_hidden(name='type', default=for_type)
            .add_info(
                name='title',
                default=title,
            )
            .build()
        )

    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        # Update type and subtype to correct values
        type, subtype = fields['type'].split('@')
        fields['type'] = types.servers.ServerType[type.upper()].value
        fields['subtype'] = subtype
        return super().pre_save(fields)

    def item_as_dict(self, item: 'Model') -> GroupItem:
        item = ensure.is_instance(item, models.ServerGroup)
        return {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'type': f'{types.servers.ServerType(item.type).name}@{item.subtype}',
            'subtype': item.subtype.capitalize(),
            'type_name': types.servers.ServerType(item.type).name.capitalize(),
            'tags': [tag.tag for tag in item.tags.all()],
            'servers_count': item.servers.count(),
            'permission': permissions.effective_permissions(self._user, item),
        }

    def delete_item(self, item: 'Model') -> None:
        item = ensure.is_instance(item, models.ServerGroup)
        """
        Processes a DELETE request
        """
        self.check_access(
            self.model(), permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            if item.type == types.servers.ServerType.UNMANAGED:
                # Unmanaged has to remove ALSO the servers
                for server in item.servers.all():
                    server.delete()
            item.delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

    def stats(self, item: 'Model') -> typing.Any:
        # Avoid circular imports
        from uds.core.managers.servers import ServerManager

        item = ensure.is_instance(item, models.ServerGroup)

        return [
            {
                'stats': s[0].as_dict() if s[0] else None,
                'server': {
                    'id': s[1].uuid,
                    'hostname': s[1].hostname,
                    'mac': s[1].mac if s[1].mac != consts.MAC_UNKNOWN else '',
                    'ip': s[1].ip,
                    'load': s[0].load() if s[0] else 0,
                },
            }
            for s in ServerManager.manager().get_server_stats(item.servers.all())
        ]
