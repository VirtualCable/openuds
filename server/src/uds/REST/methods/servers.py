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
from uds.core import consts, exceptions, types
from uds.core.types import permissions
from uds.core.util import blocker
from uds.core.util.log import LogLevel
from uds.core.util.model import getSqlDatetime, getSqlDatetimeAsUnix
from uds.core.util.os_detector import KnownOS
from uds.REST import Handler
from uds.REST.exceptions import NotFound, RequestError
from uds.REST.model import OK, ModelHandler
from uds.REST.utils import rest_result

logger = logging.getLogger(__name__)


class ServerRegister(Handler):
    needs_staff = True
    path = 'servers'
    name = 'register'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        serverToken: models.RegisteredServer
        now = getSqlDatetime()
        ip = self._params.get('ip', self.request.ip)
        if ':' in ip:
            # If zone is present, remove it
            ip = ip.split('%')[0]

        try:
            # If already exists a token for this, return it instead of creating a new one, and update the information...
            # Note that we use IP and HOSTNAME (with type) to identify the server, so if any of them changes, a new token will be created
            # MAC is just informative, and data is used to store any other information that may be needed
            serverToken = models.RegisteredServer.objects.get(
                ip=ip, kind=self._params['type']
            )
            # Update parameters
            serverToken.hostname = self._params['hostname']
            serverToken.username = self._user.pretty_name
            # Ensure we do not store zone if IPv6 and present
            serverToken.ip_from = self._request.ip.split('%')[0]
            serverToken.stamp = now
            serverToken.kind = self._params['type']
            serverToken.save()
        except Exception:
            try:
                serverToken = models.RegisteredServer.objects.create(
                    username=self._user.pretty_name,
                    ip_from=self._request.ip.split('%')[0],  # Ensure we do not store zone if IPv6 and present
                    ip=ip,
                    hostname=self._params['hostname'],
                    token=models.RegisteredServer.create_token(),
                    log_level=self._params.get('log_level', LogLevel.INFO.value),
                    stamp=now,
                    kind=self._params['type'],
                    sub_kind=self._params.get('sub_kind', ''), # Optional
                    os_type=typing.cast(str, self._params.get('os', KnownOS.UNKNOWN.os_name())).lower(),
                    mac=self._params.get('mac', consts.MAC_UNKNOWN),
                    data=self._params.get('data', None),
                )
            except Exception as e:
                return rest_result('error', error=str(e))
        return rest_result(result=serverToken.token)


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
            'id': item.token,
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

class ServerTest(Handler):
    authenticated = False  # Test is not authenticated, the auth is the token to test itself

    path = 'servers'
    name = 'test'

    @blocker.blocker()
    def post(self) -> typing.MutableMapping[str, typing.Any]:
        # Test if a token is valid
        try:
            models.RegisteredServer.objects.get(token=self._params['token'])
            return rest_result(True)
        except Exception as e:
            return rest_result('error', error=str(e))

# Server related classes/actions
class ServerAction(Handler):
    authenticated = False  # Actor requests are not authenticated normally
    path = 'servers/action'

    def action(self, server: models.RegisteredServer) -> typing.MutableMapping[str, typing.Any]:
        return rest_result('error', error='Base action invoked')
    
    @blocker.blocker()
    def post(self) -> typing.MutableMapping[str, typing.Any]:
        try:
            server = models.RegisteredServer.objects.get(token=self._params['token'])
        except models.RegisteredServer.DoesNotExist:
            raise exceptions.BlockAccess() from None   # Block access if token is not valid
        
        return self.action(server)

class ServerEvent(ServerAction):
    """
    Manages a event notification from a server to UDS Broker

    The idea behind this is manage events like login and logout from a single point

    Currently possible notify actions are:
    * login
    * logout
    * log
    """
    name = 'notify'

    def getUserService(self) -> models.UserService:
        '''
        Looks for an userService and, if not found, raises a BlockAccess request
        '''
        try:
            return models.UserService.objects.get(uuid=self._params['uuid'])
        except models.UserService.DoesNotExist:
            logger.error('User service not found (params: %s)', self._params)
            raise 

    def action(self, server: models.RegisteredServer) -> typing.MutableMapping[str, typing.Any]:
        # Notify a server that a new service has been assigned to it
        # Get action from parameters
        # Parameters:
        #  * event
        #  * uuid  (user service uuid)
        #  * data: data related to the received event
        #    * Login: { 'username': 'username'}
        #    * Logout: { 'username': 'username'}
        #    * Log: { 'level': 'level', 'message': 'message'}
        try:
            event = types.events.NotifiableEvents(self._params.get('event', None))
        except ValueError:
            return rest_result('error', error='No valid event specified')

        # Extract user service
        try:
            userService = self.getUserService()
        except Exception:
            return rest_result('error', error='User service not found')

        if event == types.events.NotifiableEvents.LOGIN:
            # TODO: notify
            pass
        elif event == types.events.NotifiableEvents.LOGOUT:
            # TODO: notify
            pass
        elif event == types.events.NotifiableEvents.LOG:
            # TODO: log
            pass

        return rest_result(True)