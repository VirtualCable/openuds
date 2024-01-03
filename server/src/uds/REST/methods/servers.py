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
import collections.abc

from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core import consts, exceptions, types
from uds.core.util import decorators, validators, log, model
from uds.REST import Handler, exceptions as rest_exceptions
from uds.REST.utils import rest_result

logger = logging.getLogger(__name__)


# REST API for Server Token Clients interaction
# Register is split in two because tunnel registration also uses this
class ServerRegisterBase(Handler):
    def post(self) -> collections.abc.MutableMapping[str, typing.Any]:
        serverToken: models.Server
        now = model.sql_datetime()
        ip = self._params.get('ip', self.request.ip)
        if ':' in ip:
            # If zone is present, remove it
            ip = ip.split('%')[0]
        port = self._params.get('port', consts.system.SERVER_DEFAULT_LISTEN_PORT)

        mac = self._params.get('mac', consts.MAC_UNKNOWN)
        data = self._params.get('data', None)
        subtype = self._params.get('subtype', '')
        os = self._params.get('os', types.os.KnownOS.UNKNOWN.os_name()).lower()
        certificate = self._params.get('certificate', '')
        version = self._params.get('version', '')

        type = self._params['type']  # MUST be present
        hostname = self._params['hostname']  # MUST be present
        # Validate parameters
        try:
            try:
                t = types.servers.ServerType(type)
            except ValueError:
                raise ValueError(_('Invalid type. Type must be an integer.'))
            if len(subtype) > 16:
                raise ValueError(_('Invalid subtype. Max length is 16.'))
            if len(os) > 16:
                raise ValueError(_('Invalid os. Max length is 16.'))
            if data and len(data) > 2048:
                raise ValueError(_('Invalid data. Max length is 2048.'))
            if port < 1 or port > 65535:
                raise ValueError(_('Invalid port. Must be between 1 and 65535'))
            validators.validateIpv4OrIpv6(ip)  # Will raise "validation error"
            validators.validateFqdn(hostname)
            validators.validateMac(mac)
            validators.validateJson(data)
            validators.validateServerCertificate(certificate)
        except Exception as e:
            raise rest_exceptions.RequestError(str(e)) from e

        try:
            # If already exists a token for this, return it instead of creating a new one, and update the information...
            # Note that if the same IP (validated by a login) requests a new token, the old one will be sent instead of creating a new one
            # Note that we use IP (with type) to identify the server, so if any of them changes, a new token will be created
            # MAC is just informative, and data is used to store any other information that may be needed
            serverTokens = models.Server.objects.filter(hostname=hostname, type=type)
            if serverTokens.count() > 1:
                return rest_result('error', error='More than one server with same hostname and type')
            if serverTokens.count() == 0:
                raise models.Server.DoesNotExist()  # Force creation of a new one
            serverToken = serverTokens[0]
            # Update parameters
            # serverToken.hostname = self._params['hostname'] 
            serverToken.username = self._user.pretty_name
            serverToken.certificate = certificate
            # Ensure we do not store zone if IPv6 and present
            serverToken.ip_from = self._request.ip.split('%')[0]
            serverToken.listen_port = port
            serverToken.ip = ip
            serverToken.stamp = now
            serverToken.mac = mac
            serverToken.subtype = subtype  # Optional
            serverToken.version = version
            serverToken.data = data
            serverToken.save()
        except Exception:
            try:
                serverToken = models.Server.objects.create(
                    username=self._user.pretty_name,
                    ip_from=self._request.ip.split('%')[0],  # Ensure we do not store zone if IPv6 and present
                    ip=ip,
                    listen_port=port,
                    hostname=self._params['hostname'],
                    certificate=certificate,
                    log_level=self._params.get('log_level', log.LogLevel.INFO.value),
                    stamp=now,
                    type=self._params['type'],
                    subtype=self._params.get('subtype', ''),  # Optional
                    os_type=typing.cast(str, (self._params.get('os') or types.os.KnownOS.UNKNOWN.os_name())).lower(),
                    mac=mac,
                    data=data,
                    version = version
                )
            except Exception as e:
                return rest_result('error', error=str(e))
        return rest_result(result=serverToken.token)


class ServerRegister(ServerRegisterBase):
    needs_staff = True
    path = 'servers'
    name = 'register'


# REST handlers for server actions
class ServerTest(Handler):
    authenticated = False  # Test is not authenticated, the auth is the token to test itself

    path = 'servers'
    name = 'test'

    @decorators.blocker()
    def post(self) -> collections.abc.MutableMapping[str, typing.Any]:
        # Test if a token is valid
        try:
            models.Server.objects.get(token=self._params['token'])
            return rest_result(True)
        except Exception as e:
            return rest_result('error', error=str(e))


class ServerEvent(Handler):
    """
    Manages a event notification from a server to UDS Broker

    The idea behind this is manage events like login and logout from a single point

    Currently possible notify actions are:
    * login
    * logout
    * log
    """

    authenticated = False  # Actor requests are not authenticated normally
    path = 'servers'
    name = 'event'

    def getUserService(self) -> models.UserService:
        '''
        Looks for an userService and, if not found, raises a BlockAccess request
        '''
        try:
            return models.UserService.objects.get(uuid=self._params['uuid'])
        except models.UserService.DoesNotExist:
            logger.error('User service not found (params: %s)', self._params)
            raise

    @decorators.blocker()
    def post(self) -> collections.abc.MutableMapping[str, typing.Any]:
        # Avoid circular import
        from uds.core.managers.servers import ServerManager

        try:
            server = models.Server.objects.get(token=self._params['token'])
        except models.Server.DoesNotExist:
            raise exceptions.BlockAccess() from None  # Block access if token is not valid
        except KeyError:
            raise rest_exceptions.RequestError('Token not present') from None  # Invalid request if token is not present
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
            return ServerManager.manager().processEvent(server, self._params)
        except Exception as e:
            logger.error('Error processing event %s: %s', self._params, e)
            return rest_result('error', error='Error processing event')
