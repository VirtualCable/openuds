# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import enum
import typing

class VmState(enum.Enum):  # pylint: disable=too-few-public-methods
    INIT = 0
    PENDING = 1
    HOLD = 2
    ACTIVE = 3
    STOPPED = 4
    SUSPENDED = 5
    DONE = 6
    FAILED = 7
    POWEROFF = 8
    UNDEPLOYED = 9

    UNKNOWN = 99

    @staticmethod
    def fromState(state: str) -> 'VmState':
        try:
            return VmState(int(state))
        except Exception:
            return VmState.UNKNOWN


class ImageState(enum.Enum):  # pylint: disable=too-few-public-methods
    INIT = 0
    READY = 1
    USED = 2
    DISABLED = 3
    LOCKED = 4
    ERROR = 5
    CLONE = 6
    DELETE = 7
    USED_PERS = 8
    LOCKED_USED = 9
    LOCKED_USED_PERS = 10

    UNKNOWN = 99

    @staticmethod
    def fromState(state: str) -> 'ImageState':
        try:
            return ImageState(int(state))
        except Exception:
            return ImageState.UNKNOWN


class StorageType(typing.NamedTuple):
    id: str
    name: str
    total: int  # In Megabytes
    free: int   # In Megabytes
    xml: typing.Optional[str]


class TemplateType(typing.NamedTuple):
    id: str
    name: str
    memory: int
    xml: typing.Optional[str]


class ImageType(typing.NamedTuple):
    id: str
    name: str
    size: int   # In Megabytes
    persistent: bool
    running_vms: int
    state: ImageState
    xml: typing.Optional[str]


class VirtualMachineType(typing.NamedTuple):
    id: str
    name: str
    memory: int
    state: VmState
    xml: typing.Optional[str]
