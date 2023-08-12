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
import enum
import typing

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


class ServerSubType(metaclass=singleton.Singleton):
    class Info(typing.NamedTuple):
        type: ServerType
        subtype: str
        description: str
        managed: bool

    registered: typing.Dict[typing.Tuple[ServerType, str], Info]

    def __init__(self) -> None:
        self.registered = {}

    @staticmethod
    def manager() -> 'ServerSubType':
        return ServerSubType()

    def register(self, type: ServerType, subtype: str, description: str, managed: bool) -> None:
        self.registered[(type, subtype)] = ServerSubType.Info(
            type=type, subtype=subtype, description=description, managed=managed
        )

    def enum(self) -> typing.Iterable[Info]:
        return self.registered.values()

    def get(self, type: ServerType, subtype: str) -> typing.Optional[Info]:
        return self.registered.get((type, subtype))


# Registering default subtypes (basically, ip unmanaged is the "global" one), any other will be registered by the providers
# I.e. "linuxapp" will be registered by the Linux Applications Provider
# The main usage of this subtypes is to allow to group servers by type, and to allow to filter by type
ServerSubType.manager().register(ServerType.UNMANAGED, 'ip', 'Unmanaged IP Server', False)


class ServerStatsType(typing.NamedTuple):
    mem: int  # In bytes
    maxmem: int  # In bytes
    cpu: float  # 0-1
    uptime: int  # In seconds
    disk: int  # In bytes
    maxdisk: int  # In bytes
    connections: int  # Number of connections
    current_users: int  # Number of current users

    @staticmethod
    def fromDict(dct: typing.Dict[str, typing.Any]) -> 'ServerStatsType':
        return ServerStatsType(
            mem=dct.get('mem', 0),
            maxmem=dct.get('maxmem', 0),
            cpu=dct.get('cpu', 0),
            uptime=dct.get('uptime', 0),
            disk=dct.get('disk', 0),
            maxdisk=dct.get('maxdisk', 0),
            connections=dct.get('connections', 0),
            current_users=dct.get('current_users', 0),
        )

    def weight(self, minMemory: int = 0) -> float:
        # Weights are calculated as:
        # 0.5 * cpu_usage + 0.5 * (1 - mem_free / mem_total)
        if self.mem < minMemory + 512000000:  # 512 MB reserved
            return 10000000000   # Try to skip nodes with not enouhg memory, putting them at the end of the list
        return (self.mem / self.maxmem) + (self.cpu) * 1.3
