# -*- coding: utf-8 -*-
#
# Copyright (c) 2019-2021 Virtual Cable S.L.U.
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
import os
import json
import base64
import hashlib
import tempfile
import contextlib
import logging
import typing
from uds.core import types, consts

from uds.core.util.security import secureRequestsSession
from uds.core.util import decorators

if typing.TYPE_CHECKING:
    from uds import models
    import requests

logger = logging.getLogger(__name__)


class ServerApiRequester:
    server: 'models.Server'
    hash: str

    def __init__(self, server: 'models.Server') -> None:
        self.hash = hashlib.sha256((server.token).encode()).hexdigest()
        self.server = server

    @contextlib.contextmanager
    def setupSession(
        self, *, minVersion: typing.Optional[str] = None
    ) -> typing.Generator['requests.Session', None, None]:
        """
        Sets up the request for the server
        """
        minVersion = minVersion or consts.MIN_SERVER_VERSION
        # If server has a cert, save it to a file
        verify: typing.Union[str, bool] = False
        try:
            if self.server.certificate:
                # Generate temp file, and delete it after
                with tempfile.NamedTemporaryFile('w', delete=False) as f:
                    f.write(self.server.certificate)  # Save cert
                    verify = f.name
            session = secureRequestsSession(verify=verify)
            # Setup headers
            session.headers.update(
                {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': consts.USER_AGENT,
                    'X-UDS-VERSION': consts.VERSION,
                    'X-AUTH-HASH': self.hash,
                }
            )
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

    def getCommsUrl(self, method: str, minVersion: typing.Optional[str]) -> typing.Optional[str]:
        """
        Returns the url for a method
        """
        if self.server.type == types.servers.ServerType.UNMANAGED or (
            self.server.version < (minVersion or consts.MIN_SERVER_VERSION)
        ):
            return None

        return self.server.getCommsUrl(path=method)

    def get(self, method: str, *, minVersion: typing.Optional[str] = None) -> typing.Any:
        url = self.getCommsUrl(method, minVersion)
        if not url:
            return None

        try:
            with self.setupSession(minVersion=minVersion) as session:
                response = session.get(url)
                if not response.ok:
                    logger.error(
                        'Error requesting %s from server %s: %s', method, self.server.hostname, response.text
                    )
                    return None

                return response.json()
        except Exception:  # If any error, return None
            return None

    def post(self, method: str, data: typing.Any, *, minVersion: typing.Optional[str] = None) -> typing.Any:
        url = self.getCommsUrl(method, minVersion)
        if not url:
            return None

        try:
            with self.setupSession(minVersion=minVersion) as session:
                response = session.post(url, json=data)
                if not response.ok:
                    logger.error(
                        'Error requesting %s from server %s: %s', method, self.server.hostname, response.text
                    )
                    return None

                return response.json()
        except Exception:  # If any error, return None
            return None

    def notifyAssign(
        self, userService: 'models.UserService', service_type: 'types.services.ServiceType', count: int
    ) -> None:
        """
        Notifies assign of user service to server
        """
        self.post(
            'assign',
            types.connections.AssignInfoType(
                udsuser=userService.user.name + '@' + userService.user.manager.name if userService.user else '',
                udsuser_uuid=userService.user.uuid if userService.user else '',
                userservice_uuid=userService.uuid,
                userservice_type=service_type,
                assignations=count,
            ),
        )

    def notifyPreconnect(
        self, userService: 'models.UserService', info: 'types.connections.ConnectionInfoType'
    ) -> None:
        """
        Notifies preconnect to server, if this allows it
        """
        src = userService.getConnectionSource()

        self.post(
            'preConnect',
            types.connections.PreconnectInfoType(
                user=info.username,
                protocol=info.protocol,
                ip=src.ip,
                hostname=src.hostname,
                udsuser=userService.user.name + '@' + userService.user.manager.name if userService.user else '',
                udsuser_uuid=userService.user.uuid if userService.user else '',
                userservice_uuid=userService.uuid,
                userservice_type=info.service_type,
            ).asDict(),
        )

    def notifyRelease(self, userService: 'models.UserService') -> None:
        """
        Notifies removal of user service to server
        """
        self.post('removeService', {'userservice': userService.uuid})

    @decorators.cached('reqserver', cacheTimeout=60)
    def getStats(self) -> typing.Optional['types.servers.ServerStatsType']:
        """
        Returns the stats of a server
        """
        data = self.get('stats')
        if data is None:
            return None

        return types.servers.ServerStatsType.fromDict(data)
