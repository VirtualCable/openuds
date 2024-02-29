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
import dataclasses

from django.utils.translation import gettext as _


class LoadBalancingPolicy(enum.IntEnum):
    ROUND_ROBIN = 0
    PRIORITY = 1
    GREATER_PERCENT_FREE = 2

    def as_str(self) -> str:
        return self.name.lower()

    @staticmethod
    def enumerate() -> list[tuple[int, str]]:
        return [
            (LoadBalancingPolicy.ROUND_ROBIN, _('Evenly distributed')),
            (LoadBalancingPolicy.PRIORITY, _('Priority')),
            (LoadBalancingPolicy.GREATER_PERCENT_FREE, _('Greater % available')),
        ]


class TransportSelectionPolicy(enum.IntEnum):
    AUTO = 0
    COMMON = 1
    LABEL = 2

    def as_str(self) -> str:
        return self.name.lower()

    @staticmethod
    def enumerate() -> list[tuple[int, str]]:
        return [
            (TransportSelectionPolicy.AUTO, _('Automatic selection')),
            (TransportSelectionPolicy.COMMON, _('Use only common transports')),
            (TransportSelectionPolicy.LABEL, _('Group Transports by label')),
        ]


class HighAvailabilityPolicy(enum.IntEnum):
    DISABLED = 0
    ENABLED = 1

    def as_str(self) -> str:
        return str(self)

    @staticmethod
    def enumerate() -> list[tuple[int, str]]:
        return [
            (HighAvailabilityPolicy.DISABLED, _('Disabled')),
            (HighAvailabilityPolicy.ENABLED, _('Enabled')),
        ]


@dataclasses.dataclass(frozen=True)
class UsageInfo:
    used: int
    total: int

    @property
    def percent(self) -> int:
        return (self.used * 100 // self.total) if self.total > 0 else 0


class UsageInfoVars:
    use_percent: str
    use_count: str
    left_count: str
    max_srvs: str

    def __init__(self, pool_usage_info: typing.Optional[UsageInfo] = None):
        if pool_usage_info is None:
            pool_usage_info = UsageInfo(0, 0)

        self.use_percent = str(pool_usage_info.percent) + '%' if pool_usage_info.total > 0 else ''
        self.use_count = str(pool_usage_info.used) if pool_usage_info.total > 0 else ''
        self.left_count = str(pool_usage_info.total - pool_usage_info.used) if pool_usage_info.total > 0 else ''
        self.max_srvs = str(pool_usage_info.total) if pool_usage_info.total > 0 else ''

    def replace(self, x: str) -> str:
        return (
            x.replace('{use}', self.use_percent)
            .replace('{total}', self.max_srvs)
            .replace('{usec}', self.use_count)
            .replace('{left}', self.left_count)
        )

    @staticmethod
    def has_macros(x: str) -> bool:
        return any(y in x for y in ('{use}', '{total}', '{usec}', '{left}'))
