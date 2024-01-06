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


class EventType(enum.IntEnum):
    # Login - logout
    LOGIN = 0
    LOGOUT = 1
    # Service access
    ACCESS = 2
    # Cache performance
    CACHE_HIT = 3
    CACHE_MISS = 4
    # Platforms detected
    PLATFORM = 5
    # Tunnel
    TUNNEL_OPEN = 6
    TUNNEL_CLOSE = 7
    # Os Manager
    OSMANAGER_INIT = 8
    OSMANAGER_READY = 9
    OSMANAGER_RELEASE = 10

    # Unknown event type
    UNKNOWN = 9999

    @staticmethod
    def from_int(value: int) -> 'EventType':
        try:
            return EventType(value)
        except ValueError:
            return EventType.UNKNOWN

    @property
    def event_name(self) -> str:
        return self.name.capitalize().replace('_', ' ')


class EventOwner(enum.IntEnum):
    PROVIDER = 0
    SERVICE = 1
    SERVICEPOOL = 2
    AUTHENTICATOR = 3
    OSMANAGER = 4

    @staticmethod
    def from_int(value: int) -> 'EventOwner':
        try:
            return EventOwner(value)
        except ValueError:
            return EventOwner.PROVIDER

    @property
    def owner_name(self) -> str:
        return self.name.capitalize()


# Counters
class CounterType(enum.IntEnum):
    """
    Counter types
    """

    LOAD = 0
    STORAGE = 1
    ASSIGNED = 2
    INUSE = 3
    AUTH_USERS = 4
    AUTH_USERS_WITH_SERVICES = 5
    AUTH_SERVICES = 6
    CACHED = 7

    # Unkown counter type
    UNKNOWN = 9999

    @staticmethod
    def from_int(value: int) -> 'CounterType':
        try:
            return CounterType(value)
        except ValueError:
            return CounterType.UNKNOWN

    @property
    def counter_name(self) -> str:
        return self.name.capitalize().replace('_', ' ')


class CounterOwner(enum.IntEnum):
    """
    Counter owner types
    """

    PROVIDER = 0
    SERVICE = 1
    SERVICEPOOL = 2
    AUTHENTICATOR = 3

    @staticmethod
    def from_int(value: int) -> 'CounterOwner':
        try:
            return CounterOwner(value)
        except ValueError:
            return CounterOwner.PROVIDER

    @property
    def owner_name(self) -> str:
        return self.name.capitalize()
