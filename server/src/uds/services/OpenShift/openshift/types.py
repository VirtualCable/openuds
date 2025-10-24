import collections.abc
import dataclasses
import enum
import typing
import logging

from typing import TypedDict, Any

from . import exceptions


# The structure seems to be:
#  Groups:
#    - Clouds

logger = logging.getLogger(__name__)


class InstanceStatus(enum.StrEnum):
    """
    Represents the state of a Openshift instance.
    """

    CANCELLED = 'cancelled'
    CLONING = 'cloning'
    DENIED = 'denied'
    FAILED = 'failed'
    PENDING_DELETE_APPROVAL = 'pendingDeleteApproval'
    PENDING_RECONFIGURE_APPROVAL = 'pendingReconfigureApproval'
    PENDING_REMOVAL = 'pendingRemoval'
    PROVISIONING = 'provisioning'
    REMOVING = 'removing'
    RESIZING = 'resizing'
    RESTARTING = 'restarting'
    RESTORING = 'restoring'
    RUNNING = 'Running'
    STOPPED = 'Stopped'
    SUSPENDED = 'Suspended'
    SUSPENDING = 'Suspending'
    UNKNOWN = 'unknown'
    WARNING = 'warning'
    PENDING = 'Pending'
    SCHEDULING = 'Scheduling'
    SCHEDULED = 'Scheduled'

    # Not usable, own state
    # We do not support multinode instances, and will not support them because it's a nonsense for UDS
    # but we will find for sure. We also do not support emtpy instances, so we will not use them
    NOT_USABLE = 'notUsable'

    def is_cloneable(self) -> bool:
        """
        Check if the instance is in a state that allows cloning.
        """
        return self in {
            InstanceStatus.RUNNING,
            InstanceStatus.STOPPED,
            InstanceStatus.SUSPENDED,
        }

    def is_cloning(self) -> bool:
        """
        Check if the instance is currently being cloned.
        """
        return self == InstanceStatus.CLONING

    def is_running(self) -> bool:
        """
        Check if the instance is running.
        """
        return self == InstanceStatus.RUNNING
    
    def is_provisioning(self) -> bool:
        """
        Check if the instance is currently being provisioned.
        """
        return self == InstanceStatus.PROVISIONING

    def is_stopped(self) -> bool:
        """
        Check if the instance is stopped.
        """
        return self == InstanceStatus.STOPPED
    
    def is_off(self) -> bool:
        """
        Check if the instance is off (stopped or suspended).
        """
        return self in {InstanceStatus.STOPPED, InstanceStatus.SUSPENDED}

    def is_error(self) -> bool:
        """
        Check if the instance is in an error state.
        """
        return self in {
            InstanceStatus.FAILED,
            InstanceStatus.DENIED,
        }

    def is_usable(self) -> bool:
        """
        Check if the instance is usable.
        """
        return self not in (InstanceStatus.NOT_USABLE, InstanceStatus.UNKNOWN)

    @staticmethod
    def from_string(state: str) -> 'InstanceStatus':
        """
        Convert a string to a OpenshiftState.
        """
        try:
            return InstanceStatus(state)
        except ValueError:
            logger.warning(f'Unknown instance state: {state}, defaulting to UNKNOWN')
            return InstanceStatus.UNKNOWN


@dataclasses.dataclass
class BasicInfo:
    """
    Represents a simple ID-Value pair.
    """

    id: int
    name: str
    code: str = ''

    @staticmethod
    def from_dict(
        data: dict[str, typing.Any],
        *,
        id_key: str = 'id',
        name_key: str = 'name',
        code_key: str = 'code',
    ) -> 'BasicInfo':
        """
        Create an IdValuePair from a dictionary.
        """
        return BasicInfo(id=data[id_key], name=data[name_key], code=data.get(code_key, ''))


@dataclasses.dataclass
class InterfaceInfo:
    """
    Represents a Openshift interface.
    """

    id: int
    mac_address: str
    ip_address: str


@dataclasses.dataclass
class InstanceInfo:
    """
    Represents a Openshift instance.

    Notes:
        * Instance can only be cloned if it's not already cloning and is in a state that allows cloning
        * The network mac address is avaliable on the provisioning state, so we can use it to identify the instance
        * The clone operation does not return the id of the instance, but the name is unique, so we can use it to find the instance later
    """

    id: int
    name: str
    display_name: str
    instance_type: BasicInfo = dataclasses.field(default_factory=lambda: BasicInfo(id=0, name=''))
    # Using a default factory to ensure tenant is always initialized
    tenant: BasicInfo = dataclasses.field(default_factory=lambda: BasicInfo(id=0, name=''))
    # Using a default factory to ensure interfaces is always initialized
    interfaces: typing.List[InterfaceInfo] = dataclasses.field(default_factory=list[InterfaceInfo])
    status: InstanceStatus = InstanceStatus.UNKNOWN

    @staticmethod
    def null() -> 'InstanceInfo':
        """
        Create a null instance.
        """
        return InstanceInfo(
            id=0,
            name='',
            display_name='',
            tenant=BasicInfo(id=0, name=''),
            interfaces=[],
            status=InstanceStatus.NOT_USABLE,
        )

    def is_usable(self) -> bool:
        """
        Check if the instance is usable.
        """
        return self.status.is_usable() and self.instance_type.code in ('kvm', 'mvm')

    def validate(self) -> 'InstanceInfo':
        """
        Validate the instance, ensuring it is usable.
        Raises an exception if not usable.
        """
        if not self.is_usable():
            raise exceptions.OpenshiftError(f'Instance {self.name} is not usable (status: {self.status})')

        return self

    @staticmethod
    def from_dict(data: dict[str, typing.Any]) -> 'InstanceInfo':
        """
        Create an Instance from a dictionary.
        """
        # Lets see if interfaces are present, it on
        # containerDetails[X].server.interfaces[]
        try:
            status = InstanceStatus.from_string(data.get('status', 'UNKNOWN'))
            interfaces: list[InterfaceInfo] = []
            if len(data.get('containers', [])) != 1 or len(data.get('servers', [])) != 1:
                status = InstanceStatus.NOT_USABLE

            if 'containerDetails' in data and isinstance(data['containerDetails'], list):
                for container in typing.cast(list[dict[str, typing.Any]], data['containerDetails']):
                    if 'server' in container and 'interfaces' in container['server']:
                        interfaces = [
                            InterfaceInfo(
                                id=iface['id'],
                                mac_address=iface['macAddress'],
                                ip_address=iface['ipAddress'],
                            )
                            for iface in container['server']['interfaces']
                        ]
                        break

            return InstanceInfo(
                id=data['id'],
                name=data.get('name', ''),
                display_name=data.get('displayName', ''),
                instance_type=BasicInfo.from_dict(data.get('instanceType', {}), id_key='id', name_key='name'),
                tenant=BasicInfo.from_dict(data.get('tenant', {}), id_key='id', name_key='name'),
                interfaces=interfaces,
                status=status,
            )
        except Exception as e:  # Any exception during parsing will generate a "null"
            logger.error(f'Error creating Instance from dict: {e}')
            return InstanceInfo.null()


#* --- OpenShift resource TypedDicts ---

@dataclasses.dataclass
class VMInterfaceInfo:
    name: str
    mac_address: str
    ip_address: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMInterfaceInfo':
        try:
            return VMInterfaceInfo(
                name=dictionary.get('interfaceName', ''),
                mac_address=dictionary.get('mac', ''),
                ip_address=dictionary.get('ipAddress', ''),
            )
        except Exception as e:
            logger.error(f'Error creating VMInterfaceInfo from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VMInterfaceInfo data') from e

@dataclasses.dataclass
class VMVolumeTemplate:
    name: str
    storage: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMVolumeTemplate':
        try:
            meta = dictionary.get('metadata', {})
            spec = dictionary.get('spec', {})
            storage = spec.get('storage', {})
            resources = storage.get('resources', {})
            requests = resources.get('requests', {})
            return VMVolumeTemplate(
                name=meta.get('name', ''),
                storage=requests.get('storage', '')
            )
        except Exception as e:
            logger.error(f'Error creating VMVolumeTemplate from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VMVolumeTemplate data') from e

@dataclasses.dataclass
class VMDeviceDisk:
    name: str
    boot_order: int

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMDeviceDisk':
        try:
            return VMDeviceDisk(
                name=dictionary.get('name', ''),
                boot_order=dictionary.get('bootOrder', 0),
            )
        except Exception as e:
            logger.error(f'Error creating VMDeviceDisk from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VMDeviceDisk data') from e

@dataclasses.dataclass
class VMVolume:
    name: str
    data_volume: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMVolume':
        try:
            dv = dictionary.get('dataVolume', {})
            return VMVolume(
                name=dictionary.get('name', ''),
                data_volume=dv.get('name', ''),
            )
        except Exception as e:
            logger.error(f'Error creating VMVolume from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VMVolume data') from e

@dataclasses.dataclass
class VMDefinition:
    name: str
    namespace: str
    uid: str
    status: InstanceStatus
    volume_template: VMVolumeTemplate
    disks: list[VMDeviceDisk]
    volumes: list[VMVolume]

    def validate(self) -> 'VMDefinition':
        if not self.is_usable():
            raise exceptions.OpenshiftError(f'VM Instance {self.name} is not usable (status: {self.status})')

        return self

    def is_usable(self) -> bool:
        return self.status.is_usable()

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMDefinition':
        try:
            metadata = dictionary.get('metadata', {})
            status_data = dictionary.get('status', {})
            status_str = status_data.get('printableStatus', 'UNKNOWN')
            spec = dictionary.get('spec', {})
            template = spec.get('template', {}).get('spec', {})
            return VMDefinition(
                name=metadata.get('name', ''),
                namespace=metadata.get('namespace', ''),
                uid=metadata.get('uid', ''),
                status=InstanceStatus.from_string(status_str),
                volume_template=VMVolumeTemplate.from_dict(spec.get('dataVolumeTemplates', [{}])[0]),
                disks=[VMDeviceDisk.from_dict(disk) for disk in template.get('devices', {}).get('disks', [])],
                volumes=[VMVolume.from_dict(vol) for vol in template.get('volumes', [])],
            )
        except Exception as e:
            logger.error(f'Error creating VMDefinition from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VMDefinition data') from e
        
@dataclasses.dataclass
class VMInstanceInfo:
    name: str
    namespace: str
    uid: str
    interfaces: list[VMInterfaceInfo]
    status: InstanceStatus
    phase: InstanceStatus = InstanceStatus.UNKNOWN  # Use InstanceStatus for phase

    def validate(self) -> 'VMInstanceInfo':
        if not self.is_usable():
            raise exceptions.OpenshiftError(f'VM Instance {self.name} is not usable (status: {self.status})')

        return self

    def is_usable(self) -> bool:
        return self.status.is_usable()

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMInstanceInfo':
        try:
            metadata = dictionary.get('metadata', {})
            status_data = dictionary.get('status', {})
            phase_str = status_data.get('phase', '')
            status_str = phase_str or status_data.get('printableStatus', 'UNKNOWN')
            return VMInstanceInfo(
                name=metadata.get('name', ''),
                namespace=metadata.get('namespace', ''),
                uid=metadata.get('uid', ''),
                interfaces=[VMInterfaceInfo.from_dict(iface) for iface in status_data.get('interfaces', [])],
                status=InstanceStatus.from_string(status_str),
                phase=InstanceStatus.from_string(phase_str) if phase_str else InstanceStatus.UNKNOWN
            )
        except Exception as e:
            logger.error(f'Error creating VMInstanceInfo from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VM Instance data') from e

    
class ManagedFieldType(TypedDict, total=False):
    apiVersion: str
    fieldsType: str
    fieldsV1: dict[str, Any]
    manager: str
    operation: str
    time: str
    subresource: str

class MetadataType(TypedDict, total=False):
    name: str
    namespace: str
    uid: str
    resourceVersion: str
    creationTimestamp: str
    annotations: dict[str, Any]
    labels: dict[str, Any]
    managedFields: list[ManagedFieldType]
    finalizers: list[str]
    generation: int

class VMItemType(TypedDict, total=False):
    apiVersion: str
    kind: str
    metadata: MetadataType
    spec: dict[str, Any]
    status: dict[str, Any]

class VMListType(TypedDict, total=False):
    apiVersion: str
    kind: str
    items: list[VMItemType]
    metadata: dict[str, Any]

class NADSpecType(TypedDict, total=False):
    config: str

class NADItemType(TypedDict, total=False):
    apiVersion: str
    kind: str
    metadata: MetadataType
    spec: NADSpecType

class NADListType(TypedDict, total=False):
    apiVersion: str
    kind: str
    items: list[NADItemType]
    metadata: dict[str, Any]

class SCItemType(TypedDict, total=False):
    metadata: MetadataType
    provisioner: str
    parameters: dict[str, Any]
    reclaimPolicy: str
    volumeBindingMode: str

class SCListType(TypedDict, total=False):
    apiVersion: str
    kind: str
    items: list[SCItemType]
    metadata: dict[str, Any]
