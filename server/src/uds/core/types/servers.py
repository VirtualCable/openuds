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
import dataclasses
import enum
import typing
import collections.abc

from django.utils.translation import gettext as _

from uds.core import consts
from uds.core.util import singleton


class ServerType(enum.IntEnum):
    TUNNEL = 1
    ACTOR = 2
    SERVER = 3

    UNMANAGED = 100

    def as_str(self) -> str:
        return self.name.lower()  # type: ignore

    def path(self) -> str:
        return {
            ServerType.TUNNEL: 'tunnel',
            ServerType.ACTOR: 'actor',
            ServerType.SERVER: 'server',
            ServerType.UNMANAGED: '',  # Unmanaged has no path, does not listen to anything
        }[self]

    @staticmethod
    def enumerate() -> list[tuple[int, str]]:
        return [
            (ServerType.TUNNEL, _('Tunnel')),
            (ServerType.ACTOR, _('Actor')),
            (ServerType.SERVER, _('Server')),
            (ServerType.UNMANAGED, _('Unmanaged')),
        ]


class ServerSubtype(metaclass=singleton.Singleton):
    class Info(typing.NamedTuple):
        type: ServerType
        subtype: str
        description: str
        managed: bool
        icon: str

    registered: dict[tuple[ServerType, str], Info]

    def __init__(self) -> None:
        self.registered = {}

    @staticmethod
    def manager() -> 'ServerSubtype':
        return ServerSubtype()

    def register(self, type: ServerType, subtype: str, description: str, icon: str, managed: bool) -> None:
        """Registers a new subtype for a server type

        Args:
            type (ServerType): Server type
            subtype (str): Subtype name
            description (str): Subtype description
            icon (str): Subtype icon (base64 encoded)
            managed (bool): If subtype is managed or not
        """
        self.registered[(type, subtype)] = ServerSubtype.Info(
            type=type, subtype=subtype, description=description, managed=managed, icon=icon
        )

    def enum(self) -> collections.abc.Iterable[Info]:
        return self.registered.values()

    def get(self, type: ServerType, subtype: str) -> typing.Optional[Info]:
        return self.registered.get((type, subtype))


# Registering default subtypes (basically, ip unmanaged is the "global" one), any other will be registered by the providers
# I.e. "linuxapp" will be registered by the Linux Applications Provider
# The main usage of this subtypes is to allow to group servers by type, and to allow to filter by type
ServerSubtype.manager().register(
    ServerType.UNMANAGED, 'ip', 'Unmanaged IP Server', consts.images.DEFAULT_IMAGE_BASE64, False
)


@dataclasses.dataclass
class ServerStats:
    memused: int = 0  # In bytes
    memtotal: int = 0  # In bytes
    cpuused: float = 0  # 0-1 (cpu usage)
    uptime: int = 0  # In seconds
    disks: list[tuple[str, int, int]] = dataclasses.field(
        default_factory=list
    )  # List of tuples (mountpoint, used, total)
    connections: int = 0  # Number of connections
    current_users: int = 0  # Number of current users
    stamp: float = 0  # Timestamp of this stats

    @property
    def cpufree_ratio(self) -> float:
        return (1 - self.cpuused) / (self.current_users + 1)

    @property
    def memfree_ratio(self) -> float:
        return (self.memtotal - self.memused) / (self.memtotal or 1) / (self.current_users + 1)

    @property
    def is_valid(self) -> bool:
        """If the stamp is lesss than consts.DEFAULT_CACHE_TIMEOUT, it is considered valid

        Returns:
            bool: True if valid, False otherwise

        Note:
            In normal situations, the stats of a server will be uptated ever minute or so, so this will be valid
            most time. If the server is down, it will be valid for 3 minutes, so it will be used as a "last known" stats
        """
        from uds.core.util.model import getSqlStamp  # To avoid circular import

        return self.stamp > getSqlStamp() - consts.system.DEFAULT_CACHE_TIMEOUT

    def weight(self, minMemory: int = 0) -> float:
        # Weights are calculated as:
        # 0.5 * cpu_usage + 0.5 * (1 - mem_free / mem_total) / (current_users + 1)
        # +1 is because this weights the connection of current users + new user
        # Dividing by number of users + 1 gives us a "ratio" of available resources per user when a new user is added
        # Also note that +512 forces that if mem_free is less than 512 MB, this server will be put at the end of the list
        if self.memtotal - self.memused < minMemory:
            return 1000000000  # At the end of the list

        # Lower is better
        return 1 / ((self.cpufree_ratio * 1.3 + self.memfree_ratio) or 1)

    def adjust(self, users_increment: int) -> 'ServerStats':
        """
        Fix the current stats as if new users are assigned or removed

        Does not updates the stamp, this is just a "simulation" of the stats with new users
        Real data will be eventually updated by the server itself, but this allows
        to have a more accurate weight of the server
        """
        if not self.is_valid or users_increment == 0:
            return self

        current_users = max(1, self.current_users)
        new_users = max(1, current_users + users_increment)

        new_memused = self.memused * new_users / current_users
        # Ensure memused is in range 0-memtotal
        new_memused = min(max(0, new_memused), self.memtotal - 1)

        new_cpuused = self.cpuused * new_users / current_users
        # Ensure cpuused is in range 0-1
        new_cpuused = min(max(0, new_cpuused), 1)

        return dataclasses.replace(
            self,
            current_users=new_users,
            memused=new_memused,
            cpuused=new_cpuused,
        )

    @staticmethod
    def fromDict(data: collections.abc.Mapping[str, typing.Any], **kwargs: typing.Any) -> 'ServerStats':
        from uds.core.util.model import getSqlStamp  # Avoid circular import

        dct = {k: v for k, v in data.items()}  # Make a copy
        dct.update(kwargs)  # and update with kwargs
        disks: list[tuple[str, int, int]] = []
        for disk in dct.get('disks', []):
            disks.append((disk['mountpoint'], disk['used'], disk['total']))
        return ServerStats(
            memused=dct.get('memused', 1),
            memtotal=dct.get('memtotal') or 1,  # Avoid division by zero
            cpuused=dct.get('cpuused', 0),
            uptime=dct.get('uptime', 0),
            disks=disks,
            connections=dct.get('connections', 0),
            current_users=dct.get('current_users', 0),
            stamp=dct.get('stamp', getSqlStamp()),
        )

    def asDict(self) -> dict[str, typing.Any]:
        data = self._asdict()
        # Replace disk as dicts
        data['disks'] = [{'mountpoint': d[0], 'used': d[1], 'total': d[2]} for d in self.disks]
        return data

    @staticmethod
    def empty() -> 'ServerStats':
        return ServerStats()

    def __str__(self) -> str:
        # Human readable
        return f'memory: {self.memused//(1024*1024)}/{self.memtotal//(1024*1024)} cpu: {self.cpuused*100} users: {self.current_users}, weight: {self.weight()}, valid: {self.is_valid}'


class ServerCounter(typing.NamedTuple):
    server_uuid: str
    counter: int

    @staticmethod
    def fromIterable(data: typing.Optional[collections.abc.Iterable]) -> typing.Optional['ServerCounter']:
        if data is None:
            return None
        return ServerCounter(*data)

    @staticmethod
    def empty() -> 'ServerCounter':
        return ServerCounter('', 0)
