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
import logging

from django.utils.translation import gettext as _

from uds.core import consts
from uds.core.util import ensure, singleton

IP_SUBTYPE: typing.Final[str] = 'ip'

logger = logging.getLogger(__name__)


class ServerType(enum.IntEnum):
    TUNNEL = 1
    ACTOR = 2
    SERVER = 3

    UNMANAGED = 100

    def as_str(self) -> str:
        return self.name.lower()

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
    ServerType.UNMANAGED, IP_SUBTYPE, 'Unmanaged IP Server', consts.images.DEFAULT_IMAGE_BASE64, False
)


@dataclasses.dataclass(frozen=True)
class ServerDiskInfo:
    mountpoint: str
    used: int
    total: int

    @staticmethod
    def from_dict(data: dict[str, typing.Any]) -> 'ServerDiskInfo':
        return ServerDiskInfo(data['mountpoint'], data['used'], data['total'])

    def as_dict(self) -> dict[str, typing.Any]:
        return {
            'mountpoint': self.mountpoint,
            'used': self.used,
            'total': self.total,
        }


@dataclasses.dataclass
class ServerStats:
    memused: int = 0  # In bytes
    memtotal: int = 0  # In bytes
    cpuused: float = 0  # 0-1 (cpu usage)
    uptime: int = 0  # In seconds
    disks: list[ServerDiskInfo] = dataclasses.field(
        default_factory=list[ServerDiskInfo]
    )  # List of tuples (mountpoint, used, total)
    connections: int = 0  # Number of connections
    current_users: int = 0  # Number of current users
    stamp: float = 0  # Timestamp of this stats

    @property
    def is_valid(self) -> bool:
        """If the stamp is lesss than consts.cache.DEFAULT_CACHE_TIMEOUT, it is considered valid

        Returns:
            bool: True if valid, False otherwise

        Note:
            In normal situations, the stats of a server will be uptated ever minute or so, so this will be valid
            most time. If the server is down, it will be valid for 3 minutes, so it will be used as a "last known" stats
        """
        from uds.core.util.model import sql_stamp  # To avoid circular import

        return self.stamp > sql_stamp() - consts.cache.DEFAULT_CACHE_TIMEOUT

    def load(self, min_memory: int = 0) -> float:
        # Loads are calculated as:
        # 30% cpu usage
        # 60% memory usage
        # 10% current users, with a max of 1000 users
        # Loads are normalized to 0-1
        # Lower weight is better

        if self.memtotal - self.memused < min_memory:
            return 1000000000  # At the end of the list

        w = (
            0.3 * self.cpuused
            + 0.6 * (self.memused / (self.memtotal or 1))
            + 0.1 * (min(1.0, self.current_users / 100.0))
        )

        return min(max(0.0, w), 1.0)

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

        new_memused = self.memused * new_users // current_users
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
    def from_dict(data: collections.abc.Mapping[str, typing.Any], **kwargs: typing.Any) -> 'ServerStats':
        from uds.core.util.model import sql_stamp  # Avoid circular import

        dct = {k: v for k, v in data.items()}  # Make a copy
        dct.update(kwargs)  # and update with kwargs
        disks: list[ServerDiskInfo] = []
        for disk in dct.get('disks', []):
            disks.append(ServerDiskInfo.from_dict(disk))
        return ServerStats(
            memused=dct.get('memused', 1),
            memtotal=dct.get('memtotal') or 1,  # Avoid division by zero
            cpuused=dct.get('cpuused', 0),
            uptime=dct.get('uptime', 0),
            disks=disks,
            connections=dct.get('connections', 0),
            current_users=dct.get('current_users', 0),
            stamp=sql_stamp(),
        )

    def as_dict(self) -> dict[str, typing.Any]:
        return {
            'memused': self.memused,
            'memtotal': self.memtotal,
            'cpuused': self.cpuused,
            'uptime': self.uptime,
            'disks': [d.as_dict() for d in self.disks],
            'connections': self.connections,
            'current_users': self.current_users,
            'stamp': self.stamp,
        }

    @staticmethod
    def null() -> 'ServerStats':
        return ServerStats()

    def __str__(self) -> str:
        # Human readable
        return f'memory: {self.memused//(1024*1024)}/{self.memtotal//(1024*1024)} cpu: {self.cpuused*100} users: {self.current_users}, load: {self.load()}, valid: {self.is_valid}'


# ServerCounter must be serializable by json, so
# we keep it as a NamedTuple instead of a dataclass
class ServerCounter(typing.NamedTuple):
    server_uuid: str
    counter: int

    @staticmethod
    def from_iterable(
        data: typing.Optional[collections.abc.Iterable[typing.Any]],
    ) -> typing.Optional['ServerCounter']:
        if data is None:
            return None

        return ServerCounter(*ensure.as_iterable(data))

    @staticmethod
    def null() -> 'ServerCounter':
        return ServerCounter('', 0)
