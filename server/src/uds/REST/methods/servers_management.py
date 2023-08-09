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

from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core import types
from uds.core.types import permissions
from uds.REST.exceptions import NotFound, RequestError
from uds.REST.model import OK, ModelHandler

logger = logging.getLogger(__name__)


# REST API for Server Tokens management (for admin interface)
class ServersTokens(ModelHandler):
    model = models.RegisteredServer
    model_exclude = {
        'kind__in': [
            types.servers.ServerType.ACTOR,
        ]
    }
    path = 'servers'
    name = 'tokens'

    table_title = _('Servers tokens')
    table_fields = [
        {'token': {'title': _('Token')}},
        {'stamp': {'title': _('Date'), 'type': 'datetime'}},
        {'username': {'title': _('Issued by')}},
        {'hostname': {'title': _('Origin')}},
        {'type': {'title': _('Type')}},
        {'os': {'title': _('OS')}},
        {'ip': {'title': _('IP')}},
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
            'type': types.servers.ServerType(
                item.kind
            ).as_str(),  # type is a reserved word, so we use "kind" instead on model
            'os': item.os_type,
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
            self.model.objects.get(token=self._args[0]).delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return OK

# REST API For servers (except tunnel servers nor actors)
class ServersGroups(ModelHandler):
    model = models.RegisteredServerGroup
    model_filter = {
        'kind__in': [
            types.servers.ServerType.SERVER,
            types.servers.ServerType.LEGACY,
        ]
    }
    path = 'servers'
    name = 'groups'

    table_title = _('Servers Groups')
    table_fields = [
        {'stamp': {'title': _('Date'), 'type': 'datetime'}},
        {'kind': {'title': _('Type')}},
        {'ip': {'title': _('IP')}},
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
            'type': types.servers.ServerType(
                item.kind
            ).as_str(),  # type is a reserved word, so we use "kind" instead on model
            'os': item.os_type,
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
            self.model.objects.get(token=self._args[0]).delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return OK


