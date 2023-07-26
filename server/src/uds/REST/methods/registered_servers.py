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
from uds.core.util.os_detector import KnownOS
from uds.core.util.log import LogLevel
from uds.REST import Handler
from uds.REST.exceptions import RequestError, NotFound
from uds.REST.model import ModelHandler, OK
from uds.core.util import permissions

logger = logging.getLogger(__name__)


class ServerRegister(Handler):
    needs_staff = True
    path = 'servers'
    name = 'register'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        serverToken: models.RegisteredServers
        now = getSqlDatetimeAsUnix()
        ip_version = 4
        ip = self._params.get('ip', self.request.ip)
        if ':' in ip:
            ip_version = 6
            # If zone is present, remove it
            ip = ip.split('%')[0]

        try:
            # If already exists a token for this, return it instead of creating a new one, and update the information...
            # Note that we use IP and HOSTNAME (with type) to identify the server, so if any of them changes, a new token will be created
            # MAC is just informative, and data is used to store any other information that may be needed
            serverToken = models.RegisteredServers.objects.get(
                ip=ip, ip_version=ip_version, hostname=self._params['hostname'], kind=self._params['type']
            )
            # Update parameters
            serverToken.username = self._user.pretty_name
            # Ensure we do not store zone if IPv6 and present
            serverToken.ip_from = self._request.ip.split('%')[0]
            serverToken.stamp = getSqlDatetime()
            serverToken.kind = self._params['type']
            serverToken.save()
        except Exception:
            try:
                serverToken = models.RegisteredServers.objects.create(
                    username=self._user.pretty_name,
                    ip_from=self._request.ip.split('%')[0],  # Ensure we do not store zone if IPv6 and present
                    ip=ip,
                    ip_version=ip_version,
                    hostname=self._params['hostname'],
                    token=models.RegisteredServers.create_token(),
                    log_level=self._params.get('log_level', LogLevel.INFO.value),
                    stamp=getSqlDatetime(),
                    kind=self._params['type'],
                    os_type=typing.cast(str, self._params.get('os', KnownOS.UNKNOWN.os_name())).lower(),
                    mac=self._params.get('mac', models.RegisteredServers.MAC_UNKNOWN),
                    data=self._params.get('data', None),
                )
            except Exception as e:
                return {'result': '', 'stamp': now, 'error': str(e)}
        return {'result': serverToken.token, 'stamp': now}

class ServerTest(Handler):
    needs_staff = True
    path = 'servers'
    name = 'test'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        # Test if a token is valid
        try:
            serverToken = models.RegisteredServers.objects.get(token=self._params['token'])
            return {'result': serverToken.token, 'stamp': getSqlDatetimeAsUnix()}
        except Exception as e:
            return {'result': '', 'stamp': getSqlDatetimeAsUnix(), 'error': 'Token not found'}

class ServersTokens(ModelHandler):
    model = models.RegisteredServers
    model_filter = {
        'kind__in': [models.RegisteredServers.ServerType.TUNNEL_SERVER, models.RegisteredServers.ServerType.OTHER]
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

    def item_as_dict(self, item: models.RegisteredServers) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.token,
            'name': str(_('Token isued by {} from {}')).format(item.username, item.ip),
            'stamp': item.stamp,
            'username': item.username,
            'ip': item.ip,
            'hostname': item.hostname,
            'token': item.token,
            'type': models.RegisteredServers.ServerType(
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
