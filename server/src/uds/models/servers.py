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
    from uds.models.user import User


class ServerGroup(UUIDModel, TaggingMixin):
    """
    Registered Server Groups

    This table stores the information about registered server groups, that are used to group
    registered servers and allow access to them by groups.

    One Regestered server can belong to 0 or 1 groups. (once assigned to a group, it cannot be assigned to another one)
    """

    name = models.CharField(max_length=64, unique=True)
    comments = models.CharField(max_length=255, default='')

    # A Server Group can have a host and port that listent to
    # (For example for tunnel servers)
    # These are not the servers ports itself, and it depends on the type of server
    # For example, for tunnel server groups, has an internet address and port that will be used
    # But for APP Servers, host and port are ununsed
    type = models.IntegerField(default=types.servers.ServerType.UNMANAGED, db_index=True)
    # Subtype of server, if any (I.E. LinuxDocker, RDS, etc..). so we can filter/group them
    subtype = models.CharField(max_length=32, default='', db_index=True)

    # On some cases, the group will have a host and port that will be used to connect to the servers
    # I.e. UDS Tunnels can be a lot of them, but have a load balancer that redirects to them
    host = models.CharField(max_length=MAX_DNS_NAME_LENGTH, default='')
    port = models.IntegerField(default=0)

    # 'Fake' declarations for type checking
    transports: 'models.manager.RelatedManager[Transport]'
    servers: 'models.manager.RelatedManager[Server]'

    def all_valid_servers(self) -> 'models.manager.RelatedManager[Server]':
        """Returns all servers that can belong to this group"""
        return self.servers.filter(maintenance_mode=False, type=self.type, subtype=self.subtype)

    class Meta:
        # Unique for host and port, so we can have only one group for each host:port
        app_label = 'uds'

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


def create_token() -> str:
    return secrets.token_urlsafe(36)


class Server(UUIDModel, TaggingMixin):
    """
    UDS Registered Servers

    This table stores the information about registered servers for tunnel servers (on v3.6) or
    more recently, for other type of servers that may be need to be registered (as app servers)

    type is used to
    allow or deny access to the API for this server.
    """

    # Username that registered the server
    username = models.CharField(max_length=128)
    # Ip from where the server was registered, can be IPv4 or IPv6
    ip_from = models.CharField(max_length=MAX_IPV6_LENGTH)
    # Ip of the server, can be IPv4 or IPv6 (used to communicate with it)
    ip = models.CharField(max_length=MAX_IPV6_LENGTH)

    # Hostname. It use depends on the implementation of the service, providers. etc..
    # But the normal operations is that hostname has precedence over ip
    # * Resolve hostname to ip
    # * If fails, use ip
    hostname = models.CharField(max_length=MAX_DNS_NAME_LENGTH)
    # Port where server listens for connections (if it listens)
    listen_port = models.IntegerField(default=SERVER_DEFAULT_LISTEN_PORT)

    # Token identifies de Registered Server (for API use, it's like the "secret" on other systems)
    token = models.CharField(max_length=48, db_index=True, unique=True, default=create_token)
    # Simple info field of when the registered server was created or revalidated
    stamp = models.DateTimeField()

    # Type of server. Defaults to tunnel, so we can migrate from previous versions
    # Note that a server can register itself several times, so we can have several entries
    # for the same server, but with different types.
    # (So, for example, an APP_SERVER can be also a TUNNEL_SERVER, because will use both APP API and TUNNEL API)
    type = models.IntegerField(default=types.servers.ServerType.TUNNEL.value, db_index=True)
    # Subtype of server, if any (I.E. LinuxDocker, RDS, etc..) so we can group it for
    # selections
    subtype = models.CharField(max_length=32, default='', db_index=True)
    # Version of the UDS API of the server. Starst at 4.0.0
    # If version is empty, means that it has no API
    version = models.CharField(max_length=32, default='')

    # If server is in "maintenance mode". Not used on tunnels (Because they are "redirected" by an external load balancer)
    # But used on other servers, so we can disable them for maintenance
    maintenance_mode = models.BooleanField(default=False, db_index=True)

    # If server is locked, since when is it locked.
    # This is used, for example, to allow one time use servers until the lock is released
    # (i.e. if a server is 1-1 machine, and we want to allow only one connection to it)
    locked_until = models.DateTimeField(null=True, blank=True, default=None, db_index=True)

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

    # Group (of registered servers) this server belongs to
    groups = models.ManyToManyField(
        ServerGroup,
        related_name='servers',
    )
    
    # For type checking
    users: 'models.manager.RelatedManager[ServerUser]'

    class Meta:  # pylint: disable=too-few-public-methods
        app_label = 'uds'

    @staticmethod
    def create_token() -> str:
        return create_token()  # Return global function

    @staticmethod
    def validateToken(
        token: str,
        serverType: typing.Union[typing.Iterable[types.servers.ServerType], types.servers.ServerType],
        request: typing.Optional[ExtendedHttpRequest] = None,
    ) -> bool:
        # Ensure token is valid
        try:
            if isinstance(serverType, types.servers.ServerType):
                tt = Server.objects.get(token=token, type=serverType.value)
            else:
                tt = Server.objects.get(token=token, type__in=[st.value for st in serverType])
            # We could check the request ip here
            if request and request.ip != tt.ip:
                raise Exception('Invalid ip')
            return True
        except Server.DoesNotExist:
            pass
        except Server.MultipleObjectsReturned:
            raise Exception('Multiple objects returned for token')
        return False

    @property
    def server_type(self) -> types.servers.ServerType:
        """Returns the server type of this server"""
        return types.servers.ServerType(self.type)

    @server_type.setter
    def server_type(self, value: types.servers.ServerType) -> None:
        """Sets the server type of this server"""
        self.type = value

    @property
    def host(self) -> str:
        """Returns the host of this server"""
        return self.hostname or self.ip

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
        return f'<RegisterdServer {self.token} of type {self.server_type.name} created on {self.stamp} by {self.username} from {self.ip}/{self.hostname}>'


class ServerUser(UUIDModel):
    server: 'models.ForeignKey[Server]' = models.ForeignKey(
        Server, related_name='users', on_delete=models.CASCADE
    )
    user: 'models.ForeignKey[User]' = models.ForeignKey(
        'uds.User', related_name='servers', on_delete=models.CASCADE
    )
    data = models.JSONField(null=True, blank=True, default=None)

    class Meta:  # pylint: disable=too-few-public-methods
        app_label = 'uds'

        constraints = [
            models.UniqueConstraint(
                fields=['server', 'user'], name='u_su_server_user'
            )
        ]

    def __str__(self) -> str:
        return f'<ServerUser {self.server} - {self.user}>'
