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
import datetime
import secrets
import typing
import collections.abc

from django.db import models
from django.db.models import Q

from uds.core import consts, types
from uds.core.consts import MAC_UNKNOWN
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.util import net, properties, resolver
from uds.core.util.model import sql_stamp, sql_now

from .tag import TaggingMixin
from .uuid_model import UUIDModel

if typing.TYPE_CHECKING:
    from uds.models.transport import Transport
    from uds.models.user_service import UserService


class ServerGroup(UUIDModel, TaggingMixin, properties.PropertiesMixin):
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
    # Note that servers type are always considered same as group type
    type = models.IntegerField(default=types.servers.ServerType.UNMANAGED, db_index=True)
    # Subtype of server, if any (I.E. LinuxDocker, RDS, etc..). so we can filter/group them
    subtype = models.CharField(max_length=32, default='', db_index=True)

    # On some cases, the group will have a host and port that will be used to connect to the servers
    # I.e. UDS Tunnels can be a lot of them, but have a load balancer that redirects to them
    host = models.CharField(max_length=consts.system.MAX_DNS_NAME_LENGTH, default='')
    port = models.IntegerField(default=0)

    # 'Fake' declarations for type checking
    transports: 'models.manager.RelatedManager[Transport]'
    servers: 'models.manager.RelatedManager[Server]'

    # For properties
    def get_owner_id_and_type(self) -> tuple[str, str]:
        return self.uuid, 'servergroup'

    class Meta:  # pyright: ignore
        # Unique for host and port, so we can have only one group for each host:port
        app_label = 'uds'

    @property
    def pretty_host(self) -> str:
        if self.port == 0:
            return self.host
        return f'{self.host}:{self.port}'

    @property
    def server_type(self) -> types.servers.ServerType:
        """Returns the server type of this server"""
        try:
            return types.servers.ServerType(self.type)
        except ValueError:
            return types.servers.ServerType.UNMANAGED

    @server_type.setter
    def server_type(self, value: types.servers.ServerType) -> None:
        """Sets the server type of this server"""
        self.type = value

    def is_managed(self) -> bool:
        """Returns if this server group is managed or not"""
        return self.server_type != types.servers.ServerType.UNMANAGED

    def https_url(self, path: str) -> str:
        if not path.startswith('/'):
            path = '/' + path
        return f'https://{self.host}:{self.port}{path}'

    def __str__(self) -> str:
        return self.name

    def search(self, ip_or_host_or_mac: str) -> typing.Optional['Server']:
        """Locates a server by ip or hostname

        It uses reverse dns lookup if ip_or_host is an ip and not found on database
        to try to locate the server by hostname

        Args:
            ip_or_host: Ip or hostname to search for

        Returns:
            The server found, or None if not found
        """
        found = self.servers.filter(
            Q(ip=ip_or_host_or_mac) | Q(hostname=ip_or_host_or_mac) | Q(mac=ip_or_host_or_mac)
        )
        if found:
            return found[0]
        # If not found, try to resolve ip_or_host and search again
        try:
            ip = resolver.resolve(ip_or_host_or_mac)[0]
            found_2 = Server.objects.filter(Q(ip=ip) | Q(hostname=ip))
            if found_2:
                return found_2[0]
        except Exception:
            pass
        return None



def _create_token() -> str:
    return secrets.token_urlsafe(36)


class Server(UUIDModel, TaggingMixin, properties.PropertiesMixin):
    """
    UDS Registered Servers

    This table stores the information about registered servers for tunnel servers (on v3.6) or
    more recently, for other type of servers that may be need to be registered (as app servers)

    type is used to
    allow or deny access to the API for this server.
    """

    # Username that registered the server
    register_username = models.CharField(max_length=128)
    # Ip from where the server was registered, can be IPv4 or IPv6
    register_ip = models.CharField(max_length=consts.system.MAX_IPV6_LENGTH)
    # Ip of the server, can be IPv4 or IPv6 (used to communicate with it)
    ip = models.CharField(max_length=consts.system.MAX_IPV6_LENGTH)

    # Hostname. It use depends on the implementation of the service, providers. etc..
    # But the normal operations is that hostname has precedence over ip
    # * Resolve hostname to ip
    # * If fails, use ip
    # Note that although hostname is not unique, if you try to register a server with a hostname
    # that has more than one record, it will fail
    hostname = models.CharField(max_length=consts.system.MAX_DNS_NAME_LENGTH)
    # Port where server listens for connections (if it listens)
    listen_port = models.IntegerField(default=consts.net.SERVER_DEFAULT_LISTEN_PORT)

    # Token identifies de Registered Server (for API use, it's like the "secret" on other systems)
    token = models.CharField(max_length=48, db_index=True, unique=True, default=_create_token)
    # Simple info field of when the registered server was created or revalidated
    stamp = models.DateTimeField()

    # Type of server. Defaults to tunnel, so we can migrate from previous versions
    # Note that a server can register itself several times, so we can have several entries
    # for the same server, but with different types.
    # (So, for example, an APP_SERVER can be also a TUNNEL_SERVER, because will use both APP API and TUNNEL API)
    # We store the type, because we need to filter in order to add to a type of server group.
    # All servers inside a server group must be of the same type. (Not checked on database, but on code when creating a server group)
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

    # If server is locked, until when is it locked.
    # This is used, for example, to allow one time use servers until the lock is released
    # (i.e. if a server is 1-1 machine, and we want to allow only one connection to it)
    locked_until = models.DateTimeField(null=True, blank=True, default=None, db_index=True)

    # os type of server (linux, windows, etc..)
    os_type = models.CharField(max_length=32, default=types.os.KnownOS.UNKNOWN.os_name())
    # mac address of registered server, if any. Important for VDI actor servers mainly, informative for others
    mac = models.CharField(max_length=32, default=MAC_UNKNOWN, db_index=True)
    # certificate of server, if any. VDI Actors will have it's certificate on a property of the userService
    # In fact CA of the certificate, but self signed will be created most times, so it will be the certificate itself
    certificate = models.TextField(default='', blank=True)

    # Log level, so we can filter messages for this server
    log_level = models.IntegerField(default=types.log.LogLevel.ERROR.value)

    # Extra data, for server type custom data use (i.e. actor keeps command related data here)
    data: typing.Any = models.JSONField(null=True, blank=True, default=None)

    # Group (of registered servers) this server belongs to
    # Note that only Tunnel servers can belong to more than one servergroup
    groups: 'models.ManyToManyField[ServerGroup, Server]' = models.ManyToManyField(
        ServerGroup,
        related_name='servers',
    )

    class Meta:  # pyright: ignore
        app_label = 'uds'

    # For properties
    def get_owner_id_and_type(self) -> tuple[str, str]:
        return self.uuid, 'server'

    @property
    def server_type(self) -> types.servers.ServerType:
        """Returns the server type of this server"""
        try:
            return types.servers.ServerType(self.type)
        except ValueError:
            return types.servers.ServerType.UNMANAGED

    @server_type.setter
    def server_type(self, value: types.servers.ServerType) -> None:
        """Sets the server type of this server"""
        self.type = value

    @property
    def host(self) -> str:
        """Returns the host of this server

        Host returns first the IP if it exists, and if not, the hostname (resolved)
        """
        if net.is_valid_ip(self.ip):
            return self.ip
        # If hostname exists, try to resolve it
        if self.hostname:
            ips = resolver.resolve(self.hostname)
            if ips:
                return ips[0]
        return ''

    @property
    def ip_version(self) -> int:
        """Returns the ip version of this server"""
        return 6 if ':' in self.ip else 4

    @property
    def stats(self) -> typing.Optional[types.servers.ServerStats]:
        """Returns the current stats of this server, or None if not available"""
        stats_dict = self.properties.get('stats', None)
        if stats_dict:
            return types.servers.ServerStats.from_dict(stats_dict)
        return None

    @stats.setter
    def stats(self, value: typing.Optional[types.servers.ServerStats]) -> None:
        """Sets the current stats of this server"""
        if value is None:
            del self.properties['stats']
        else:
            # Set stamp to current time and save it, overwriting existing stamp if any
            stats_dict = value.as_dict()
            stats_dict['stamp'] = sql_stamp()
            self.properties['stats'] = stats_dict

    def lock(self, duration: typing.Optional[datetime.timedelta]) -> None:
        """Locks this server for a duration"""
        if duration is None:
            self.locked_until = None
        else:
            self.locked_until = sql_now() + duration
        self.save(update_fields=['locked_until'])

    def interpolate_new_assignation(self) -> None:
        """Interpolates, with current stats, the addition of a new user"""
        stats = self.stats
        if stats and stats.is_valid:  # If rae invalid, do not waste time recalculating
            # Avoid replacing current "stamp" value, this is just a "simulation"
            self.properties['stats'] = stats.adjust(users_increment=1).as_dict()

    def interpolate_new_release(self) -> None:
        """Interpolates, with current stats, the release of a user"""
        stats = self.stats
        if stats and stats.is_valid:
            # Avoid replacing current "stamp" value, this is just a "simulation"
            self.properties['stats'] = stats.adjust(users_increment=-1).as_dict()

    def is_restrained(self) -> bool:
        """Returns if this server is restrained or not

        For this, we get the property (if available) "available" (datetime) and compare it with current time
        If it is not available, we return False, otherwise True
        """
        restrained_until = datetime.datetime.fromtimestamp(self.properties.get('available', consts.NEVER_UNIX))
        return restrained_until > sql_now()

    def set_restrained_until(self, value: typing.Optional[datetime.datetime] = None) -> None:
        """Sets the availability of this server
        If value is None, it will be available right now
        """
        if value is None:
            del self.properties['available']
        else:
            self.properties['available'] = value.timestamp()  # Encode as timestamp

    @property
    def last_ping(self) -> datetime.datetime:
        """Returns the last ping of this server"""
        last: float = self.properties.get('last_ping', consts.NEVER_UNIX)
        return datetime.datetime.fromtimestamp(last)

    @last_ping.setter
    def last_ping(self, value: datetime.datetime) -> None:
        """Sets the last ping of this server"""
        self.properties['last_ping'] = value.timestamp()

    @staticmethod
    def create_token() -> str:
        return _create_token()  # Return global function

    @staticmethod
    def validate_token(
        token: str,
        *,
        server_type: typing.Union[collections.abc.Iterable[types.servers.ServerType], types.servers.ServerType],
        request: typing.Optional[ExtendedHttpRequest] = None,
    ) -> bool:
        """Ensures that a token is valid for a server type

        Args:
            token: Token to validate
            server_type: Server type to validate token for
            request: Optional request to check ip against token ip

        Returns:
            True if token is valid for server type, False otherwise

        Note:
            This allows to keep Tunnels, Servers, Actors.. etc on same table, and validate tokens for each kind
        """
        # Ensure token is valid for a kind
        try:
            if isinstance(server_type, types.servers.ServerType):
                tt = Server.objects.get(token=token, type=server_type.value)
            else:
                tt = Server.objects.get(token=token, type__in=[st.value for st in server_type])
            # We could check the request ip here
            if request and request.ip != tt.ip:
                raise Exception('Invalid ip')
            return True
        except Server.DoesNotExist:
            pass
        except Server.MultipleObjectsReturned:
            raise Exception('Multiple objects returned for token')
        return False

    def set_actor_version(self, userservice: 'UserService') -> None:
        """Sets the actor version of this server to the userservice"""
        userservice.actor_version = f'Server {self.version or "unknown"}'

    def get_comms_endpoint(self, *, path: typing.Optional[str] = None) -> typing.Optional[str]:
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

        path = path.lstrip('/')  # Remove leading slashes
        pre, post = ('[', ']') if self.ip_version == 6 else ('', '')
        # The url is composed of https://[ip]:[port]/[server_type]/v1/[path]
        # v1 is currently the only version, but we can add more in the future
        return f'https://{pre}{self.ip}{post}:{self.listen_port}/{self.server_type.path()}/v1/{path}'

    def __str__(self) -> str:
        return f'<RegisterdServer {self.token} of type {self.server_type.name} created on {self.stamp} by {self.register_username} from {self.ip}/{self.hostname}>'


properties.PropertiesMixin.setup_signals(Server)
properties.PropertiesMixin.setup_signals(ServerGroup)
