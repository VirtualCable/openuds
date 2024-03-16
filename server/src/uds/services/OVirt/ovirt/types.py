import enum
import typing
import dataclasses


class VMStatus(enum.StrEnum):
    # Adapted from ovirtsdk4
    DOWN = 'down'
    IMAGE_LOCKED = 'image_locked'
    MIGRATING = 'migrating'
    NOT_RESPONDING = 'not_responding'
    PAUSED = 'paused'
    POWERING_DOWN = 'powering_down'
    POWERING_UP = 'powering_up'
    REBOOT_IN_PROGRESS = 'reboot_in_progress'
    RESTORING_STATE = 'restoring_state'
    SAVING_STATE = 'saving_state'
    SUSPENDED = 'suspended'
    UNASSIGNED = 'unassigned'
    UNKNOWN = 'unknown'
    UP = 'up'
    WAIT_FOR_LAUNCH = 'wait_for_launch'

    @staticmethod
    def from_str(status: str) -> 'VMStatus':
        try:
            return VMStatus(status)
        except ValueError:
            return VMStatus.UNKNOWN


class StorageStatus(enum.StrEnum):
    # Adapted from ovirtsdk4
    ACTIVATING = 'activating'
    ACTIVE = 'active'
    DETACHING = 'detaching'
    INACTIVE = 'inactive'
    LOCKED = 'locked'
    MAINTENANCE = 'maintenance'
    MIXED = 'mixed'
    PREPARING_FOR_MAINTENANCE = 'preparing_for_maintenance'
    UNATTACHED = 'unattached'
    UNKNOWN = 'unknown'

    @staticmethod
    def from_str(status: str) -> 'StorageStatus':
        try:
            return StorageStatus(status)
        except ValueError:
            return StorageStatus.UNKNOWN


class StorageType(enum.StrEnum):
    # Adapted from ovirtsdk4
    DATA = 'data'
    EXPORT = 'export'
    IMAGE = 'image'
    ISO = 'iso'
    MANAGED_BLOCK_STORAGE = 'managed_block_storage'
    VOLUME = 'volume'

    # Custom value to represent an unknown storage type
    UNKNOWN = 'unknown'

    @staticmethod
    def from_str(type: str) -> 'StorageType':
        try:
            return StorageType(type)
        except ValueError:
            return StorageType.UNKNOWN


class TemplateStatus(enum.StrEnum):
    # Adapted from ovirtsdk4
    ILLEGAL = 'illegal'
    LOCKED = 'locked'
    OK = 'ok'

    # Custom value to represent the template is missing
    # Used on get_template_info
    UNKNOWN = 'unknown'

    @staticmethod
    def from_str(status: str) -> 'TemplateStatus':
        try:
            return TemplateStatus(status)
        except ValueError:
            return TemplateStatus.ILLEGAL


@dataclasses.dataclass
class StorageInfo:
    id: str
    name: str
    type: StorageType
    available: int
    used: int
    status: StorageStatus

    @property
    def enabled(self) -> bool:
        return self.status not in (StorageStatus.INACTIVE, StorageStatus.MAINTENANCE)

    @staticmethod
    def from_data(storage: typing.Any) -> 'StorageInfo':
        return StorageInfo(
            id=storage.id,
            name=storage.name,
            type=StorageType.from_str(storage.type.value),
            available=storage.available,
            used=storage.used,
            status=StorageStatus.from_str(storage.status.value),
        )


@dataclasses.dataclass
class DatacenterInfo:
    name: str
    id: str
    local_storage: bool
    description: str
    storage: list[StorageInfo]

    @staticmethod
    def from_data(datacenter: typing.Any, storage: list[StorageInfo]) -> 'DatacenterInfo':
        return DatacenterInfo(
            name=datacenter.name,
            id=datacenter.id,
            local_storage=datacenter.local,
            description=datacenter.description,
            storage=storage,
        )


@dataclasses.dataclass
class ClusterInfo:
    name: str
    id: str
    datacenter_id: str

    @staticmethod
    def from_data(cluster: typing.Any) -> 'ClusterInfo':
        return ClusterInfo(
            name=cluster.name,
            id=cluster.id,
            datacenter_id=cluster.data_center.id if cluster.data_center else '',
        )


@dataclasses.dataclass
class VMInfo:
    name: str
    id: str
    cluster_id: str
    usb_enabled: bool
    # usb legacy is not supported anymore, so we only have "native"
    # and does not needs a separate field
    status: VMStatus

    @staticmethod
    def from_data(vm: typing.Any) -> 'VMInfo':
        try:
            usb_enabled = vm.usb.enabled
        except Exception:
            usb_enabled = False
        return VMInfo(
            name=vm.name,
            id=vm.id,
            cluster_id=vm.cluster.id,
            usb_enabled=usb_enabled,
            status=VMStatus.from_str(vm.status.value),
        )

    @staticmethod
    def missing() -> 'VMInfo':
        return VMInfo(name='', id='', cluster_id='', usb_enabled=False, status=VMStatus.UNKNOWN)


@dataclasses.dataclass
class TemplateInfo:
    id: str
    name: str
    description: str
    cluster_id: str
    status: TemplateStatus

    @staticmethod
    def from_data(template: typing.Any) -> 'TemplateInfo':
        return TemplateInfo(
            id=template.id,
            name=template.name,
            description=template.description,
            cluster_id=template.cluster.id,
            status=TemplateStatus.from_str(template.status.value),
        )

    @staticmethod
    def missing() -> 'TemplateInfo':
        return TemplateInfo(id='', name='', description='', cluster_id='', status=TemplateStatus.UNKNOWN)
