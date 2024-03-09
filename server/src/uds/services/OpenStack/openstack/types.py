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
import datetime
import typing
import dataclasses
import enum


class State(enum.StrEnum):
    ACTIVE = 'ACTIVE'
    BUILDING = 'BUILDING'
    DELETED = 'DELETED'
    ERROR = 'ERROR'
    HARD_REBOOT = 'HARD_REBOOT'
    MIGRATING = 'MIGRATING'
    PASSWORD = 'PASSWORD'
    PAUSED = 'PAUSED'
    REBOOT = 'REBOOT'
    REBUILD = 'REBUILD'
    RESCUED = 'RESCUED'
    RESIZED = 'RESIZED'
    REVERT_RESIZE = 'REVERT_RESIZE'
    SOFT_DELETED = 'SOFT_DELETED'
    STOPPED = 'STOPPED'
    SUSPENDED = 'SUSPENDED'
    UNKNOWN = 'UNKNOWN'
    VERIFY_RESIZE = 'VERIFY_RESIZE'
    SHUTOFF = 'SHUTOFF'


@dataclasses.dataclass
class VMInfo:
    id: str
    name: str
    href: str = ''

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'VMInfo':
        # Look for self link
        href: str = ''
        for link in d.get('links', []):
            try:
                if link.get('rel', '') == 'self':
                    href = typing.cast(str, link['href'])
                    break
            except Exception:
                pass  # Just ignore any error here
        return VMInfo(
            id=d['id'],
            name=d['name'],
            href=href,
        )


@dataclasses.dataclass
class ProjectInfo:
    id: str
    name: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'ProjectInfo':
        return ProjectInfo(
            id=d['id'],
            name=d['name'],
        )


@dataclasses.dataclass
class RegionInfo:
    id: str
    name: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'RegionInfo':
        # Try to guess name
        # Api definition does not includes name, nor locale, but some implementations includes it
        name: str = d['id']
        if 'name' in d:
            name = d['name']
        # Mayby it has a locales dict, if this is the case and it contains en-us (case insensitive), we will use it
        if 'locales' in d and isinstance(d['locales'], dict):
            if 'en-us' in d['locales'] and isinstance(d['locales']['en-us'], str):
                name = d['locales']['en-us']
        return RegionInfo(
            id=d['id'],
            name=name,
        )


@dataclasses.dataclass
class ImageInfo:
    id: str
    name: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'ImageInfo':
        return ImageInfo(
            id=d['id'],
            name=d.get('name', d['id']),
        )


@dataclasses.dataclass
class VolumeInfo:
    id: str
    name: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'VolumeInfo':
        return VolumeInfo(
            id=d['id'],
            name=d['name'] or '',
        )


@dataclasses.dataclass
class VolumeSnapshotInfo:
    id: str
    name: str
    description: str
    status: str
    size: int  # in gibibytes (GiB)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'VolumeSnapshotInfo':
        # Try to get created_at and updated_at, if not possible, just ignore it
        return VolumeSnapshotInfo(
            id=d['id'],
            name=d['name'],
            description=d['description'] or '',
            status=d['status'],
            size=d['size'],
            created_at=datetime.datetime.fromisoformat(d['created_at']),
            updated_at=datetime.datetime.fromisoformat(d['updated_at']),
        )


@dataclasses.dataclass
class VolumeTypeInfo:
    id: str
    name: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'VolumeTypeInfo':
        return VolumeTypeInfo(
            id=d['id'],
            name=d['name'],
        )

@dataclasses.dataclass
class AvailabilityZoneInfo:
    id: str
    name: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'AvailabilityZoneInfo':
        return AvailabilityZoneInfo(
            id=d['zoneName'],
            name=d['zoneName'],
        )