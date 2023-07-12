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
import secrets
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core.util.model import getSqlDatetimeAsUnix, getSqlDatetime
from uds.REST import Handler
from uds.REST.exceptions import RequestError, NotFound
from uds.REST.model import ModelHandler, OK
from uds.core.util import permissions

logger = logging.getLogger(__name__)


class ServerRegister(Handler):
    needs_admin = True
    path = 'servers'
    name = 'register'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        serverToken: models.RegisteredServers
        now = getSqlDatetimeAsUnix()
        try:
            # If already exists a token for this MAC, return it instead of creating a new one, and update the information...
            serverToken = models.RegisteredServers.objects.get(
                ip=self._params['ip'], hostname=self._params['hostname']
            )
            # Update parameters
            serverToken.username = self._user.pretty_name
            serverToken.ip_from = self._request.ip
            serverToken.stamp = getSqlDatetime()
            serverToken.kind = self._params['type']
            serverToken.save()
        except Exception:
            try:
                serverToken = models.RegisteredServers.objects.create(
                    username=self._user.pretty_name,
                    ip_from=self._request.ip,
                    ip=self._params['ip'],
                    hostname=self._params['hostname'],
                    token=secrets.token_urlsafe(36),
                    stamp=getSqlDatetime(),
                    kind=self._params['type'],
                )
            except Exception as e:
                return {'result': '', 'stamp': now, 'error': str(e)}
        return {'result': serverToken.token, 'stamp': now}


class ServersTokens(ModelHandler):
    model = models.RegisteredServers
    path = 'servers'
    name = 'tokens'

    table_title = _('Servers tokens')
    table_fields = [
        {'token': {'title': _('Token')}},
        {'stamp': {'title': _('Date'), 'type': 'datetime'}},
        {'username': {'title': _('Issued by')}},
        {'hostname': {'title': _('Origin')}},
        {'type': {'title': _('Type')}},
        {'ip': {'title': _('IP')}},
    ]

    def item_as_dict(self, item: models.RegisteredServers) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.token,
            'name': str(_('Token isued by {} from {}')).format(item.username, item.ip),
            'stamp': item.stamp,
            'username': item.username,
            'ip': item.ip,
            'hostname': item.hostname,
            'token': item.token,
            'type': models.RegisteredServers.ServerType(item.kind).as_str(),  # type is a reserved word, so we use "kind" instead on model
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
