# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import enum
import secrets

from django.db import models

from uds.core import types
from uds.core.util.os_detector import KnownOS

from uds.core.util.request import ExtendedHttpRequest
from uds.core.util.log import LogLevel

from uds.core.consts import MAX_DNS_NAME_LENGTH, MAX_IPV6_LENGTH, MAC_UNKNOWN, SERVER_DEFAULT_LISTEN_PORT

from .uuid_model import UUIDModel
from .tag import TaggingMixin


if typing.TYPE_CHECKING:
    from uds.models.transport import Transport


class RegisteredServerGroup(UUIDModel, TaggingMixin):
    """
    Registered Server Groups

    This table stores the information about registered server groups, that are used to group
    registered servers and allow access to them by groups.

    One Regestered server can belong to 0 or 1 groups. (once assigned to a group, it cannot be assigned to another one)
    """

    name = models.CharField(max_length=64, unique=True)
    comments = models.CharField(max_length=255, default='')

    # A RegisteredServer Group can have a host and port that listent to
    # (For example for tunnel servers)
    # These are not the servers ports itself, and it depends on the kind of server
    # For example, for tunnel server groups, has an internet address and port that will be used
    # But for APP Servers, host and port are ununsed
    kind = models.IntegerField(default=types.servers.ServerType.LEGACY, db_index=True)
    sub_kind = models.CharField(
        max_length=32, default='', db_index=True
    )  # Subkind of server, if any (I.E. LinuxDocker, RDS, etc..)

    host = models.CharField(max_length=MAX_DNS_NAME_LENGTH, default='')
    port = models.IntegerField(default=0)

    # 'Fake' declarations for type checking
    transports: 'models.manager.RelatedManager[Transport]'
    servers: 'models.manager.RelatedManager[RegisteredServer]'

    class Meta:
        # Unique for host and port, so we can have only one group for each host:port
        app_label = 'uds'
        constraints = [models.UniqueConstraint(fields=['host', 'port'], name='unique_host_port_group')]

    @property
    def pretty_host(self) -> str:
        if self.port == 0:
            return self.host
        return f'{self.host}:{self.port}'

    def https_url(self, path: str) -> str:
        if not path.startswith('/'):
            path = '/' + path
        return f'https://{self.host}:{self.port}{path}'

    def __str__(self):
        return self.name


class RegisteredServer(UUIDModel, TaggingMixin):
    """
    UDS Registered Servers

    This table stores the information about registered servers for tunnel servers (on v3.6) or
    more recently, for other kind of servers that may be need to be registered (as app servers)

    kind field is a flag that indicates the kind of server that is registered. This is used to
    allow or deny access to the API for this server.
    Currently there are two kinds of servers:
    - Tunnel servers: This is the original use of this table, and is used to allow tunnel servers (1)
    - Other servers: This is used to register server that needs to access some API methods, but
        that are not tunnel servers (2)

    If server is Other, but not Tunnel, it will be allowed to access API, but will not be able to
    create tunnels.
    """

    username = models.CharField(max_length=128)
    ip_from = models.CharField(max_length=MAX_IPV6_LENGTH)
    ip = models.CharField(max_length=MAX_IPV6_LENGTH)

    hostname = models.CharField(max_length=MAX_DNS_NAME_LENGTH)
    listen_port = models.IntegerField(
        default=SERVER_DEFAULT_LISTEN_PORT
    )  # Port where server listens for connections (if it listens)

    token = models.CharField(max_length=48, db_index=True, unique=True)
    stamp = models.DateTimeField()  # Date creation or validation of this entry

    # Type of server. Defaults to tunnel, so we can migrate from previous versions
    # Note that a server can register itself several times, so we can have several entries
    # for the same server, but with different types.
    # (So, for example, an APP_SERVER can be also a TUNNEL_SERVER, because will use both APP API and TUNNEL API)
    kind = models.IntegerField(default=types.servers.ServerType.TUNNEL.value, db_index=True)
    sub_kind = models.CharField(
        max_length=32, default='', db_index=True
    )  # Subkind of server, if any (I.E. LinuxDocker, RDS, etc..)
    version = models.CharField(
        max_length=32, default='4.0.0'
    )  # Version of the UDS API of the server. Starst at 4.0.0

    # If server is in "maintenance mode". Not used on tunnels (Because they are "redirected" by an external load balancer)
    # But used on other servers, so we can disable them for maintenance
    maintenance_mode = models.BooleanField(default=False, db_index=True)

    # os type of server (linux, windows, etc..)
    os_type = models.CharField(max_length=32, default=KnownOS.UNKNOWN.os_name())
    # mac address of registered server, if any. Important for VDI actor servers mainly, informative for others
    mac = models.CharField(max_length=32, default=MAC_UNKNOWN, db_index=True)
    # certificate of server, if any. VDI Actors will have it's certificate on a property of the userService
    certificate = models.TextField(default='', blank=True)

    # Log level, so we can filter messages for this server
    log_level = models.IntegerField(default=LogLevel.ERROR.value)

    # Extra data, for server type custom data use (i.e. actor keeps command related data here)
    data = models.JSONField(null=True, blank=True, default=None)

    # Group this server belongs to
    groups = models.ManyToManyField(
        RegisteredServerGroup,
        related_name='servers',
    )

    class Meta:  # pylint: disable=too-few-public-methods
        app_label = 'uds'

    @staticmethod
    def create_token() -> str:
        return secrets.token_urlsafe(36)

    @staticmethod
    def validateToken(
        token: str,
        serverType: typing.Union[typing.Iterable[types.servers.ServerType], types.servers.ServerType],
        request: typing.Optional[ExtendedHttpRequest] = None,
    ) -> bool:
        # Ensure token is valid
        try:
            if isinstance(serverType, types.servers.ServerType):
                tt = RegisteredServer.objects.get(token=token, kind=serverType.value)
            else:
                tt = RegisteredServer.objects.get(token=token, kind__in=[st.value for st in serverType])
            # We could check the request ip here
            if request and request.ip != tt.ip:
                raise Exception('Invalid ip')
            return True
        except RegisteredServer.DoesNotExist:
            pass
        except RegisteredServer.MultipleObjectsReturned:
            raise Exception('Multiple objects returned for token')
        return False

    @property
    def server_type(self) -> types.servers.ServerType:
        """Returns the server type of this server"""
        return types.servers.ServerType(self.kind)

    @server_type.setter
    def server_type(self, value: types.servers.ServerType) -> None:
        """Sets the server type of this server"""
        self.kind = value.value

    @property
    def ip_version(self) -> int:
        """Returns the ip version of this server"""
        return 6 if ':' in self.ip else 4

    def getCommsUrl(self, *, path: typing.Optional[str] = None) -> typing.Optional[str]:
        """
        Returns the url for a path to this server

        Args:
            path: Path to add to url

        Returns:
            The url for the path

        Note:
            USerService Actors has it own "comms" method
            This is so because every VDI actor has a different tocken, not registered here
            (This only registers "Master" actor, the descendants obtains a token from it)
            App Servers, future implementations of Tunnel and Other servers will use this method
            to obtain the url for the path.
            Currently, only App Servers uses this method. Tunnel servers does not expose any url.
            The "token" will be sent by server api on header, and it is a sha256 of the server token
            (so we don't sent it directly to client) on X-AUTH-HASH
        """
        path = path or ''

        if not path.startswith('/'):
            path = '/' + path

        path = f'/{self.server_type.path()}{path}'

        if self.ip_version == 4:
            return f'https://{self.ip}:{self.listen_port}{path}'
        return f'https://[{self.ip}]:{self.listen_port}{path}'

    def __str__(self):
        return f'<RegisterdServer {self.token} created on {self.stamp} by {self.username} from {self.ip}/{self.hostname}>'
