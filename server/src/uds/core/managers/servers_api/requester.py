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
import os
import hashlib
import tempfile
import contextlib
import logging
import typing
import collections.abc
from uds.core import types, consts

from uds.core.util import security, cache
from uds.core.util.model import sql_now


if typing.TYPE_CHECKING:
    from uds import models
    import requests

logger = logging.getLogger(__name__)

AUTH_TOKEN = 'X-TOKEN-AUTH'


# Restrainer decorator
# If server is restrained, it will return False
# If server is not restrained, it will execute the function and return it's result
# If exception is raised, it will restrain the server and return False
def restrain_server(func: collections.abc.Callable[..., typing.Any]) -> collections.abc.Callable[..., typing.Any]:
    def inner(self: 'ServerApiRequester', *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if self.server.is_restrained():
            return False

        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            restrained_until = sql_now() + datetime.timedelta(seconds=consts.system.FAILURE_TIMEOUT)
            logger.exception('Error executing %s: %s. Server restrained until %s', func.__name__, e, restrained_until)
            self.server.set_restrained_until(
                restrained_until
            )  # Block server for a while
            return False

    return inner


class ServerApiRequester:
    server: 'models.Server'
    cache: 'cache.Cache'
    hash: str

    def __init__(self, server: 'models.Server') -> None:
        self.hash = hashlib.sha256((server.token).encode()).hexdigest()
        self.server = server
        self.cache = cache.Cache('serverapi:' + server.uuid)

    @contextlib.contextmanager
    def setup_session(
        self, *, minVersion: typing.Optional[str] = None
    ) -> typing.Generator['requests.Session', None, None]:
        """
        Sets up the request for the server
        """
        minVersion = minVersion or consts.system.MIN_SERVER_VERSION
        # If server has a cert, save it to a file
        verify: typing.Union[str, bool] = False
        try:
            if self.server.certificate:
                # Generate temp file, and delete it after
                with tempfile.NamedTemporaryFile('w', delete=False) as f:
                    f.write(self.server.certificate)  # Save cert
                    verify = f.name
            session = security.secure_requests_session(verify=verify)
            # Setup headers
            session.headers.update(
                {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': consts.system.USER_AGENT,
                    'X-UDS-VERSION': consts.system.VERSION,
                    AUTH_TOKEN: self.hash,
                }
            )
            # And timeout
        except Exception as e:
            logger.error('Error setting up request for server %s: %s', self.server.hostname, e)
            raise

        try:
            yield session
        finally:
            session.close()
            if isinstance(verify, str):
                try:
                    os.unlink(verify)
                except Exception:
                    logger.error('Error removing temp file %s', verify)

    def get_comms_endpoint(self, method: str, min_version: typing.Optional[str]) -> typing.Optional[str]:
        """
        Returns the url for a method on the server
        """
        if self.server.type == types.servers.ServerType.UNMANAGED or (
            self.server.version < (min_version or consts.system.MIN_SERVER_VERSION)
        ):
            return None

        return self.server.get_comms_endpoint(path=method)

    def get(self, method: str, *, minVersion: typing.Optional[str] = None) -> typing.Any:
        url = self.get_comms_endpoint(method, minVersion)
        if not url:
            return None

        with self.setup_session(minVersion=minVersion) as session:
            response = session.get(url, timeout=(consts.net.DEFAULT_CONNECT_TIMEOUT, consts.net.DEFAULT_REQUEST_TIMEOUT))
            if not response.ok:
                logger.error(
                    'Error requesting %s from server %s: %s', method, self.server.hostname, response.text
                )
                return None

            return response.json()

    def post(self, method: str, data: typing.Any, *, minVersion: typing.Optional[str] = None) -> typing.Any:
        url = self.get_comms_endpoint(method, minVersion)
        if not url:
            return None

        with self.setup_session(minVersion=minVersion) as session:
            response = session.post(url, json=data, timeout=(consts.net.DEFAULT_CONNECT_TIMEOUT, consts.net.DEFAULT_REQUEST_TIMEOUT))
            if not response.ok:
                logger.error(
                    'Error requesting %s from server %s: %s', method, self.server.hostname, response.text
                )
                return None

            return response.json()

    @restrain_server
    def notify_assign(
        self, userService: 'models.UserService', service_type: 'types.services.ServiceType', count: int
    ) -> bool:
        """
        Notifies assign of user service to server

        Args:
            userService: User service to notify
            service_type: Type of service to notify
            count: Number of "logins" to notify

        Returns:
            True if notification was sent, False otherwise
        """
        logger.debug('Notifying assign of service %s to server %s', userService.uuid, self.server.host)
        self.post(
            'assign',
            types.connections.AssignRequest(
                udsuser=userService.user.name + '@' + userService.user.manager.name if userService.user else '',
                udsuser_uuid=userService.user.uuid if userService.user else '',
                userservice_uuid=userService.uuid,
                service_type=service_type,
                assignations=count,
            ).as_dict(),
        )
        return True

    @restrain_server
    def notify_preconnect(
        self, userService: 'models.UserService', info: 'types.connections.ConnectionData'
    ) -> bool:
        """
        Notifies preconnect to server, if this allows it

        Args:
            userService: User service to notify
            info: Connection data to notify

        Returns:
            True if notification was sent, False otherwise
        """
        src = userService.get_connection_source()

        logger.debug(
            'Notifying preconnect of service %s to server %s: %s', userService.uuid, self.server.host, info
        )
        self.post(
            'preconnect',
            types.connections.PreconnectRequest(
                user=info.username,
                protocol=info.protocol,
                ip=src.ip,
                hostname=src.hostname,
                udsuser=userService.user.name + '@' + userService.user.manager.name if userService.user else '',
                udsuser_uuid=userService.user.uuid if userService.user else '',
                userservice_uuid=userService.uuid,
                service_type=info.service_type,
            ).as_dict(),
        )
        return True

    @restrain_server
    def notify_release(self, userService: 'models.UserService') -> bool:
        """
        Notifies removal of user service to server
        """
        logger.debug('Notifying release of service %s to server %s', userService.uuid, self.server.host)
        self.post('release', types.connections.ReleaseRequest(userservice_uuid=userService.uuid).as_dict())

        return True

    def get_stats(self) -> typing.Optional['types.servers.ServerStats']:
        """
        Returns the stats of a server
        """
        # If stored stats are still valid, return them
        stats = self.server.stats
        if stats and stats.is_valid:
            return stats

        logger.debug('Getting stats from server %s', self.server.host)
        try:
            data = self.get('stats')  # Unmanaged servers will return None
            if data is None:
                return None
        except Exception as e:
            logger.error('Error getting stats from server %s: %s', self.server.host, e)
            if stats:
                return stats  # Better return old stats than nothing
            return None

        # Will store stats on property, so no save is needed
        self.server.stats = types.servers.ServerStats.from_dict(data)
        return self.server.stats
