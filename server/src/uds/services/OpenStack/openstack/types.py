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

from uds.core.services.generics import exceptions

class AuthMethod(enum.StrEnum):
    # Only theese two methods are supported by our OpenStack implementation
    PASSWORD = 'password'
    APPLICATION_CREDENTIAL = 'application_credential'

    @staticmethod
    def from_str(s: str) -> 'AuthMethod':
        try:
            return AuthMethod(s.lower())
        except ValueError:
            return AuthMethod.PASSWORD    

class ServerStatus(enum.StrEnum):
    ACTIVE = 'ACTIVE'  # The server is active.
    BUILD = 'BUILD'  # The server has not finished the original build process.
    DELETED = 'DELETED'  # The server is permanently deleted.
    ERROR = 'ERROR'  # The server is in error.
    HARD_REBOOT = 'HARD_REBOOT'  # The server is hard rebooting. This is equivalent to pulling the power plug on a physical server, plugging it back in, and rebooting it.
    MIGRATING = 'MIGRATING'  # The server is being migrated to a new host.
    PASSWORD = 'PASSWORD'  # The password is being reset on the server.
    PAUSED = 'PAUSED'  # In a paused state, the state of the server is stored in RAM. A paused server continues to run in frozen state.
    REBOOT = (
        'REBOOT'  # The server is in a soft reboot state. A reboot command was passed to the operating system.
    )
    REBUILD = 'REBUILD'  # The server is currently being rebuilt from an image.
    RESCUE = 'RESCUE'  # The server is in rescue mode. A rescue image is running with the original server image attached.
    RESIZE = 'RESIZE'  # Server is performing the differential copy of data that changed during its initial copy. Server is down for this stage.
    REVERT_RESIZE = 'REVERT_RESIZE'  # The resize or migration of a server failed for some reason. The destination server is being cleaned up and the original source server is restarting.
    SHELVED = 'SHELVED'  # The server is in shelved state. Depending on the shelve offload time, the server will be automatically shelved offloaded.
    SHELVED_OFFLOADED = 'SHELVED_OFFLOADED'  # The shelved server is offloaded (removed from the compute host) and it needs unshelved action to be used again.
    SHUTOFF = 'SHUTOFF'  # The server is powered off and the disk image still persists.
    SOFT_DELETED = (
        'SOFT_DELETED'  # The server is marked as deleted but the disk images are still available to restore.
    )
    SUSPENDED = 'SUSPENDED'  # The server is suspended, either by request or necessity. When you suspend a server, its state is stored on disk, all memory is written to disk, and the server is stopped. Suspending a server is similar to placing a device in hibernation and its occupied resource will not be freed but rather kept for when the server is resumed. If a server is infrequently used and the occupied resource needs to be freed to create other servers, it should be shelved.
    UNKNOWN = 'UNKNOWN'  # The state of the server is unknown. Contact your cloud provider.
    VERIFY_RESIZE = 'VERIFY_RESIZE'  # System is awaiting confirmation that the server is operational after a move or resize.

    @staticmethod
    def from_str(s: str) -> 'ServerStatus':
        try:
            return ServerStatus(s.upper())
        except ValueError:
            return ServerStatus.UNKNOWN

    # Helpers to check statuses
    def is_lost(self) -> bool:
        return self in [ServerStatus.DELETED, ServerStatus.ERROR, ServerStatus.UNKNOWN, ServerStatus.SOFT_DELETED]

    def is_paused(self) -> bool:
        return self in [ServerStatus.PAUSED, ServerStatus.SUSPENDED]

    def is_running(self) -> bool:
        return self in [ServerStatus.ACTIVE, ServerStatus.RESCUE, ServerStatus.RESIZE, ServerStatus.VERIFY_RESIZE]

    def is_stopped(self) -> bool:
        return self in [ServerStatus.SHUTOFF, ServerStatus.SHELVED, ServerStatus.SHELVED_OFFLOADED, ServerStatus.SOFT_DELETED]


class PowerState(enum.IntEnum):
    NOSTATE = 0
    RUNNING = 1
    PAUSED = 3
    SHUTDOWN = 4
    CRASHED = 6
    SUSPENDED = 7

    @staticmethod
    def from_int(i: int) -> 'PowerState':
        try:
            return PowerState(i)
        except ValueError:
            return PowerState.NOSTATE

    def is_paused(self) -> bool:
        return self == PowerState.PAUSED

    def is_running(self) -> bool:
        return self == PowerState.RUNNING

    def is_stopped(self) -> bool:
        return self in [PowerState.SHUTDOWN, PowerState.CRASHED, PowerState.SUSPENDED]


class AccessType(enum.StrEnum):
    PUBLIC = 'public'
    PRIVATE = 'private'
    INTERNAL = 'url'

    @staticmethod
    def from_str(s: str) -> 'AccessType':
        try:
            return AccessType(s.lower())
        except ValueError:
            return AccessType.PUBLIC


class SnapshotStatus(enum.StrEnum):
    CREATING = 'creating'  # The snapshot is being created.
    AVAILABLE = 'available'  # The snapshot is ready to use.
    BACKING_UP = 'backing-up'  # The snapshot is being backed up.
    DELETING = 'deleting'  # The snapshot is being deleted.
    ERROR = 'error'  # A snapshot creation error has occurred.
    DELETED = 'deleted'  # The snapshot is deleted.
    UNMANAGING = 'unmanaging'  # The snapshot is being unmanaged.
    RESTORING = 'restoring'  # The snapshot is being restored to a volume.
    ERROR_DELETING = 'error_deleting'  # A snapshot deletion error has occurred.

    UNKNOWN = 'unknown'  # The state of the snapshot is unknown. Internal, not from openstack

    @staticmethod
    def from_str(s: str) -> 'SnapshotStatus':
        try:
            return SnapshotStatus(s.lower())
        except ValueError:
            return SnapshotStatus.UNKNOWN


class NetworkStatus(enum.StrEnum):
    ACTIVE = 'ACTIVE'  # The network is active.
    DOWN = 'DOWN'  # The network is down.
    BUILD = 'BUILD'  # The network has not finished the original build process.
    ERROR = 'ERROR'  # The network is in error.

    @staticmethod
    def from_str(s: str) -> 'NetworkStatus':
        try:
            return NetworkStatus(s.upper())
        except ValueError:
            return NetworkStatus.ERROR


class PortStatus(enum.StrEnum):
    ACTIVE = 'ACTIVE'  # The port is active.
    DOWN = 'DOWN'  # The port is down.
    BUILD = 'BUILD'  # The port has not finished the original build process.
    ERROR = 'ERROR'  # The port is in error.

    @staticmethod
    def from_str(s: str) -> 'PortStatus':
        try:
            return PortStatus(s.upper())
        except ValueError:
            return PortStatus.ERROR


@dataclasses.dataclass
class ServerInfo:

    @dataclasses.dataclass
    class AddresInfo:
        version: int
        ip: str
        mac: str
        type: str
        network_name: str = ''

        @staticmethod
        def from_dict(d: dict[str, typing.Any]) -> 'ServerInfo.AddresInfo':
            return ServerInfo.AddresInfo(
                version=d.get('version') or 4,
                ip=d.get('addr') or '',
                mac=(d.get('OS-EXT-IPS-MAC:mac_addr') or '').upper(),
                type=d.get('OS-EXT-IPS:type') or '',
            )

        @staticmethod
        def from_addresses(adresses: dict[str, list[dict[str, typing.Any]]]) -> list['ServerInfo.AddresInfo']:
            def _build() -> typing.Generator['ServerInfo.AddresInfo', None, None]:
                for net_name, inner_addresses in adresses.items():
                    for address in inner_addresses:
                        address_info = ServerInfo.AddresInfo.from_dict(address)
                        address_info.network_name = net_name
                        yield address_info

            return list(_build())

    id: str
    name: str
    href: str
    flavor: str
    status: ServerStatus
    power_state: PowerState
    addresses: list[AddresInfo]  # network_name: AddresInfo
    access_addr_ipv4: str
    access_addr_ipv6: str
    fault: typing.Optional[str]
    admin_pass: str
    
    def validated(self) -> 'ServerInfo':
        """
        Raises NotFoundError if server is lost
        
        Returns:
            self
        """
        if self.status.is_lost():
            raise exceptions.NotFoundError(f'Server {self.id} is lost')
        return self

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'ServerInfo':
        # Look for self link
        href: str = ''
        for link in d.get('links', []):
            try:
                if link.get('rel', '') == 'self':
                    href = typing.cast(str, link['href'])
                    break
            except Exception:
                pass  # Just ignore any error here
        # Try to get flavor, only on >= 2.47
        try:
            flavor = d.get('flavor', {}).get('id', '')
        except Exception:
            flavor = ''
        return ServerInfo(
            id=d['id'],
            name=d.get('name', d['id']),
            href=href,
            flavor=flavor,
            status=ServerStatus.from_str(d.get('status', ServerStatus.UNKNOWN.value)),
            power_state=PowerState.from_int(d.get('OS-EXT-STS:power_state', PowerState.NOSTATE)),
            addresses=ServerInfo.AddresInfo.from_addresses(d.get('addresses', {})),
            access_addr_ipv4=d.get('accessIPv4') or '',
            access_addr_ipv6=d.get('accessIPv6') or '',
            fault=d.get('fault', None),
            admin_pass=d.get('adminPass') or '',
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
    description: str
    size: int
    availability_zone: str
    bootable: bool
    encrypted: bool

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'VolumeInfo':
        return VolumeInfo(
            id=d['id'],
            name=d['name'] or '',
            description=d.get('description', ''),
            size=d.get('size', 0),
            availability_zone=d.get('availability_zone', ''),
            bootable=d.get('bootable', False),
            encrypted=d.get('encrypted', False),
        )


@dataclasses.dataclass
class VolumeSnapshotInfo:
    id: str
    volume_id: str
    name: str
    description: str
    status: SnapshotStatus
    size: int  # in gibibytes (GiB)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'VolumeSnapshotInfo':
        # Try to get created_at and updated_at, if not possible, just ignore it
        created_at = datetime.datetime.fromisoformat(d.get('created_at') or '1970-01-01T00:00:00')
        updated_at = datetime.datetime.fromisoformat(d.get('updated_at') or '1970-01-01T00:00:00')
        return VolumeSnapshotInfo(
            id=d['id'],
            volume_id=d['volume_id'],
            name=d['name'],
            description=d['description'] or '',
            status=SnapshotStatus.from_str(d['status']),
            size=d['size'],
            created_at=created_at,
            updated_at=updated_at,
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
    available: bool

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'AvailabilityZoneInfo':
        available = d.get('zoneState', {}).get('available', False)
        return AvailabilityZoneInfo(
            id=d['zoneName'],
            name=d['zoneName'],
            available=available,
        )


@dataclasses.dataclass
class FlavorInfo:
    id: str
    name: str
    vcpus: int
    ram: int
    disk: int
    swap: int
    is_public: bool
    disabled: bool

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'FlavorInfo':
        return FlavorInfo(
            id=d['id'],
            name=d['name'],
            vcpus=d['vcpus'],
            ram=d['ram'],
            disk=d['disk'],
            swap=d['swap'] or 0,
            is_public=d.get('os-flavor-access:is_public', True),
            disabled=d.get('OS-FLV-DISABLED:disabled', False),
        )


@dataclasses.dataclass
class NetworkInfo:
    id: str
    name: str
    status: NetworkStatus
    shared: bool
    subnets: list[str]
    availability_zones: list[str]

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'NetworkInfo':
        return NetworkInfo(
            id=d['id'],
            name=d['name'],
            status=NetworkStatus.from_str(d['status']),
            shared=d['shared'],
            subnets=d['subnets'],
            availability_zones=d.get('availability_zones', []),
        )


@dataclasses.dataclass
class SubnetInfo:
    id: str
    name: str
    cidr: str
    enable_dhcp: bool
    gateway_ip: str
    ip_version: int
    network_id: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'SubnetInfo':
        return SubnetInfo(
            id=d['id'],
            name=d['name'],
            cidr=d['cidr'],
            enable_dhcp=d['enable_dhcp'],
            gateway_ip=d['gateway_ip'],
            ip_version=d['ip_version'],
            network_id=d['network_id'],
        )


@dataclasses.dataclass
class PortInfo:

    @dataclasses.dataclass
    class FixedIpInfo:
        ip_address: str
        subnet_id: str

        @staticmethod
        def from_dict(d: dict[str, typing.Any]) -> 'PortInfo.FixedIpInfo':
            return PortInfo.FixedIpInfo(
                ip_address=d['ip_address'],
                subnet_id=d['subnet_id'],
            )

    id: str
    name: str
    status: str
    device_id: str
    device_owner: str
    mac_address: str
    fixed_ips: list['FixedIpInfo']

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'PortInfo':
        return PortInfo(
            id=d['id'],
            name=d['name'],
            status=d['status'],
            device_id=d['device_id'],
            device_owner=d['device_owner'],
            mac_address=d['mac_address'],
            fixed_ips=[PortInfo.FixedIpInfo.from_dict(ip) for ip in d['fixed_ips']],
        )


@dataclasses.dataclass
class SecurityGroupInfo:
    id: str
    name: str
    description: str

    @staticmethod
    def from_dict(d: dict[str, typing.Any]) -> 'SecurityGroupInfo':
        return SecurityGroupInfo(
            id=d['id'],
            name=d['name'],
            description=d['description'],
        )
