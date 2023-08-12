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
from uds.core import types
from uds.core.types import permissions as permtypes
from uds.core.types import rest, servers
from uds.core.ui import gui
from uds.core.util import permissions
from uds.core.util.model import processUuid
from uds.REST.exceptions import NotFound, RequestError
from uds.REST.model import OK, DetailHandler, ModelHandler

logger = logging.getLogger(__name__)


# REST API for Server Tokens management (for admin interface)
class ServersTokens(ModelHandler):
    model = models.RegisteredServer
    model_exclude = {
        'type__in': [
            types.servers.ServerType.ACTOR,
        ]
    }
    path = 'servers'
    name = 'tokens'

    table_title = _('Registered Servers')
    table_fields = [
        {'hostname': {'title': _('Hostname')}},
        {'ip': {'title': _('IP')}},
        {'type': {'title': _('Type')}},
        {'os': {'title': _('OS')}},
        {'username': {'title': _('Issued by')}},
        {'stamp': {'title': _('Date'), 'type': 'datetime'}},
    ]

    def item_as_dict(self, item: models.RegisteredServer) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': str(_('Token isued by {} from {}')).format(item.username, item.ip),
            'stamp': item.stamp,
            'username': item.username,
            'ip': item.ip,
            'hostname': item.hostname,
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
            self.model(), permtypes.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            self.model.objects.get(uuid=processUuid(self._args[0])).delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return OK


# REST API For servers (except tunnel servers nor actors)
class ServersServers(DetailHandler):
    path = 'servers'
    name = 'servers'
    custom_methods = ['maintenance']

    def getItems(self, parent: 'models.RegisteredServerGroup', item: typing.Optional[str]):
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
                    'maintenance': i.maintenance_mode,
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

    def getTitle(self, parent: 'models.RegisteredServerGroup') -> str:
        try:
            return _('Servers of {0}').format(parent.name)
        except Exception:
            return _('Servers')

    def getFields(self, parent: 'models.RegisteredServerGroup') -> typing.List[typing.Any]:
        return [
            {
                'hostname': {
                    'title': _('Hostname'),
                }
            },
            {'ip': {'title': _('Ip')}},
        ]

    def saveItem(self, parent: 'models.RegisteredServerGroup', item: typing.Optional[str]) -> None:
        # Item is the uuid of the server to add
        server: typing.Optional[
            'models.RegisteredServer'
        ] = None  # Avoid warning on reference before assignment

        if item is None:
            raise self.invalidItemException('No server specified')

        try:
            server = models.RegisteredServer.objects.get(uuid=processUuid(item))
            parent.servers.add(server)
        except Exception:
            raise self.invalidItemException() from None

        raise self.invalidRequestException() from None

    def deleteItem(self, parent: 'models.RegisteredServerGroup', item: str) -> None:
        try:
            parent.servers.remove(models.RegisteredServer.objects.get(uuid=processUuid(item)))
        except Exception:
            raise self.invalidItemException() from None

    # Custom methods
    def maintenance(self, parent: 'models.RegisteredServerGroup') -> typing.Any:
        """
        Custom method that swaps maintenance mode state for a provider
        :param item:
        """
        item = models.RegisteredServer.objects.get(uuid=processUuid(self._params['id']))
        self.ensureAccess(item, permtypes.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return 'ok'


class ServersGroups(ModelHandler):
    model = models.RegisteredServerGroup
    model_filter = {
        'type__in': [
            types.servers.ServerType.SERVER,
            types.servers.ServerType.UNMANAGED,
        ]
    }
    path = 'servers'
    name = 'groups'

    save_fields = ['name', 'comments', 'type', 'tags']  # Subtype is appended on beforeSave
    table_title = _('Servers Groups')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'comments': {'title': _('Comments')}},
        {'kind': {'title': _('Type')}},
        {'type': {'title': 'xx', 'visible': False}},
        {'subtype': {'title': _('Subtype')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def getTypes(self, *args, **kwargs) -> typing.Generator[typing.Dict[str, typing.Any], None, None]:
        for i in servers.ServerSubType.manager().enum():
            v = rest.TypeInfo(
                name=i.description, type=f'{i.type.name}@{i.subtype}', description='', icon=''
            ).asDict(group=gettext('Managed') if i.managed else gettext('Unmanaged'))
            yield v

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        return self.addField(
            self.addDefaultFields(
                [],
                ['name', 'comments', 'tags'],
            ),
            [
                {
                    'name': 'type',
                    'value': type_,
                    'type': gui.InputField.Types.HIDDEN,
                }
            ],
        )

    def beforeSave(self, fields: typing.Dict[str, typing.Any]) -> None:
        # Update type and subtype to correct values
        type, subtype = fields['type'].split('@')
        fields['type'] = types.servers.ServerType[type.upper()].value
        fields['subtype'] = subtype
        return super().beforeSave(fields)

    def item_as_dict(self, item: 'models.RegisteredServerGroup') -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'type': f'{types.servers.ServerType(item.type).name}@{item.subtype}',
            'subtype': item.subtype.capitalize(),
            'kind': types.servers.ServerType(item.type).name.capitalize(),
            'tags': [tag.tag for tag in item.tags.all()],
            'servers_count': item.servers.count(),
            'permission': permissions.getEffectivePermission(self._user, item),
        }

    def delete(self) -> str:
        """
        Processes a DELETE request
        """
        if len(self._args) != 1:
            raise RequestError('Delete need one and only one argument')

        self.ensureAccess(
            self.model(), permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            obj = models.RegisteredServerGroup.objects.get(uuid=processUuid(self._args[0]))
            if obj.type == types.servers.ServerType.UNMANAGED:
                 # Unmanaged has to remove ALSO the servers
                for server in obj.servers.all():
                    server.delete()
            obj.delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return OK
