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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core import consts, types, ui
from uds.core.util import permissions
from uds.core.util.model import getSqlDatetime, processUuid
from uds.REST.exceptions import NotFound, RequestError
from uds.REST.model import DetailHandler, ModelHandler

logger = logging.getLogger(__name__)


# REST API for Server Tokens management (for admin interface)
class ServersTokens(ModelHandler):
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
    table_fields = [
        {'hostname': {'title': _('Hostname')}},
        {'ip': {'title': _('IP')}},
        {'type': {'title': _('Type'), 'type': 'dict', 'dict': dict(types.servers.ServerType.enumerate())}},
        {'os': {'title': _('OS')}},
        {'username': {'title': _('Issued by')}},
        {'stamp': {'title': _('Date'), 'type': 'datetime'}},
    ]

    def item_as_dict(self, item: 'models.Server') -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': str(_('Token isued by {} from {}')).format(item.username, item.ip),
            'stamp': item.stamp,
            'username': item.username,
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

        self.ensureAccess(
            self.model(), types.permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            self.model.objects.get(uuid=processUuid(self._args[0])).delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return consts.OK


# REST API For servers (except tunnel servers nor actors)
class ServersServers(DetailHandler):
    custom_methods = ['maintenance']

    def getItems(self, parent: 'models.ServerGroup', item: typing.Optional[str]):
        try:
            multi = False
            if item is None:
                multi = True
                q = parent.servers.all()
            else:
                q = parent.servers.filter(uuid=processUuid(item))
            res = []
            i = None
            for i in q:
                val = {
                    'id': i.uuid,
                    'hostname': i.hostname,
                    'ip': i.ip,
                    'listen_port': i.listen_port,
                    'mac': i.mac if not multi or i.mac != consts.MAC_UNKNOWN else '',
                    'maintenance_mode': i.maintenance_mode,
                }
                res.append(val)
            if multi:
                return res
            if not i:
                raise Exception('Item not found')
            return res[0]
        except Exception as e:
            logger.exception('REST servers')
            raise self.invalidItemException() from e

    def getTitle(self, parent: 'models.ServerGroup') -> str:
        try:
            return _('Servers of {0}').format(parent.name)
        except Exception:
            return _('Servers')

    def getFields(self, parent: 'models.ServerGroup') -> typing.List[typing.Any]:
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

    def getRowStyle(self, parent: 'models.ServerGroup') -> typing.Dict[str, typing.Any]:
        return {'field': 'maintenance_mode', 'prefix': 'row-maintenance-'}

    def getGui(self, parent: 'models.ServerGroup', forType: str = '') -> typing.List[typing.Any]:
        kind, subkind = parent.server_type, parent.subtype
        title = _('of type') + f' {subkind.upper()} {kind.name.capitalize()}'
        if kind == types.servers.ServerType.UNMANAGED:
            return self.addField(
                [],
                [
                    {
                        'name': 'hostname',
                        'value': '',
                        'label': gettext('Hostname'),
                        'tooltip': gettext('Hostname of the server. It must be resolvable by UDS'),
                        'type': types.ui.FieldType.TEXT,
                        'order': 100,  # At end
                    },
                    {
                        'name': 'ip',
                        'value': '',
                        'label': gettext('IP'),
                        'tooltip': gettext('IP of the server. Used if hostname is not resolvable by UDS'),
                        'type': types.ui.FieldType.TEXT,
                        'order': 101,  # At end
                    },
                    {
                        'name': 'listen_port',
                        'value': 0,
                        'label': gettext('Port'),
                        'tooltip': gettext('Port of server. 0 means "service default"'),
                        'type': types.ui.FieldType.NUMERIC,
                        'order': 102,  # At end
                    },
                    {
                        'name': 'title',
                        'value': title,
                        'type': types.ui.FieldType.INFO,
                    },
                ],
            )
        else:
            return self.addField(
                [],
                [
                    {
                        'name': 'server',
                        'value': '',
                        'label': gettext('Server'),
                        'tooltip': gettext('Server to include on group'),
                        'type': types.ui.FieldType.CHOICE,
                        'choices': [
                            ui.gui.choiceItem(item.uuid, item.hostname)
                            for item in models.Server.objects.filter(type=parent.type, subtype=parent.subtype)
                            if item not in parent.servers.all()
                        ],
                        'order': 100,  # At end
                    },
                    {
                        'name': 'title',
                        'value': title,
                        'type': types.ui.FieldType.INFO,
                    },
                ],
            )

    def saveItem(self, parent: 'models.ServerGroup', item: typing.Optional[str]) -> None:
        # Item is the uuid of the server to add
        server: typing.Optional['models.Server'] = None  # Avoid warning on reference before assignment

        if item is None:
            # Create new, depending on server type
            if parent.type == types.servers.ServerType.UNMANAGED:
                # Create a new one, and add it to group
                server = models.Server.objects.create(
                    ip_from='::1',
                    ip=self._params['ip'],
                    hostname=self._params['hostname'],
                    listen_port=self._params['listen_port'] or 0,
                    type=parent.type,
                    subtype=parent.subtype,
                    stamp=getSqlDatetime(),
                )
                # Add to group
                parent.servers.add(server)
                return
            elif parent.type == types.servers.ServerType.SERVER:
                # Get server
                try:
                    server = models.Server.objects.get(uuid=processUuid(self._params['server']))
                    # Check server type is also SERVER
                    if server.type != types.servers.ServerType.SERVER:
                        logger.error('Server type for %s is not SERVER', server.host)
                        raise self.invalidRequestException() from None
                    parent.servers.add(server)
                except Exception:
                    raise self.invalidItemException() from None
                pass
        else:
            try:
                server = models.Server.objects.get(uuid=processUuid(item))
                parent.servers.add(server)
            except Exception:
                raise self.invalidItemException() from None

            raise self.invalidRequestException() from None

    def deleteItem(self, parent: 'models.ServerGroup', item: str) -> None:
        try:
            server = models.Server.objects.get(uuid=processUuid(item))
            if parent.server_type == types.servers.ServerType.UNMANAGED:
                parent.servers.remove(server)  # Remove reference
                server.delete()  # and delete server
            else:
                parent.servers.remove(server)  # Just remove reference
        except Exception:
            raise self.invalidItemException() from None

    # Custom methods
    def maintenance(self, parent: 'models.ServerGroup', id: str) -> typing.Any:
        """
        Custom method that swaps maintenance mode state for a tunnel server
        :param item:
        """
        item = models.Server.objects.get(uuid=processUuid(id))
        self.ensureAccess(item, types.permissions.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return 'ok'


class ServersGroups(ModelHandler):
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

    save_fields = ['name', 'comments', 'type', 'tags']  # Subtype is appended on beforeSave
    table_title = _('Servers Groups')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'comments': {'title': _('Comments')}},
        {'type_name': {'title': _('Type')}},
        {'type': {'title': '', 'visible': False}},
        {'subtype': {'title': _('Subtype')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def getTypes(self, *args, **kwargs) -> typing.Generator[typing.Dict[str, typing.Any], None, None]:
        for i in types.servers.ServerSubtype.manager().enum():
            v = types.rest.TypeInfo(
                name=i.description, type=f'{i.type.name}@{i.subtype}', description='', icon=i.icon
            ).asDict(group=gettext('Managed') if i.managed else gettext('Unmanaged'))
            yield v

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        if '@' not in type_:  # If no subtype, use default
            type_ += '@default'
        kind, subkind = type_.split('@')[:2]
        if kind == types.servers.ServerType.SERVER.name:
            kind = _('Standard')
        elif kind == types.servers.ServerType.UNMANAGED.name:
            kind = _('Unmanaged')
        title = _('of type') + f' {subkind.upper()} {kind}'
        return self.addField(
            self.addDefaultFields(
                [],
                ['name', 'comments', 'tags'],
            ),
            [
                {
                    'name': 'type',
                    'value': type_,
                    'type': types.ui.FieldType.HIDDEN,
                },
                {
                    'name': 'title',
                    'value': title,
                    'type': types.ui.FieldType.INFO,
                },
            ],
        )

    def beforeSave(self, fields: typing.Dict[str, typing.Any]) -> None:
        # Update type and subtype to correct values
        type, subtype = fields['type'].split('@')
        fields['type'] = types.servers.ServerType[type.upper()].value
        fields['subtype'] = subtype
        return super().beforeSave(fields)

    def item_as_dict(self, item: 'models.ServerGroup') -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'type': f'{types.servers.ServerType(item.type).name}@{item.subtype}',
            'subtype': item.subtype.capitalize(),
            'type_name': types.servers.ServerType(item.type).name.capitalize(),
            'tags': [tag.tag for tag in item.tags.all()],
            'servers_count': item.servers.count(),
            'permission': permissions.getEffectivePermission(self._user, item),
        }

    def deleteItem(self, item: str) -> None:
        """
        Processes a DELETE request
        """
        self.ensureAccess(
            self.model(), permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            obj = models.ServerGroup.objects.get(uuid=processUuid(item))
            if obj.type == types.servers.ServerType.UNMANAGED:
                # Unmanaged has to remove ALSO the servers
                for server in obj.servers.all():
                    server.delete()
            obj.delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None
