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
    RUNNING = 'running'
    STOPPED = 'stopped'
    SUSPENDED = 'suspended'
    SUSPENDING = 'suspending'
    UNKNOWN = 'unknown'
    WARNING = 'warning'

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
class VMMetadata:
    name: str
    namespace: str
    uid: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMMetadata':
        return VMMetadata(
            name=dictionary.get('name', ''),
            namespace=dictionary.get('namespace', ''),
            uid=dictionary.get('uid', ''),
        )

@dataclasses.dataclass
class VMVolumeTemplate:
    name: str
    storage: str
    storage_class: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMVolumeTemplate':
        meta = dictionary.get('metadata', {})
        spec = dictionary.get('spec', {})
        storage = spec.get('storage', {})
        resources = storage.get('resources', {})
        requests = resources.get('requests', {})
        return VMVolumeTemplate(
            name=meta.get('name', ''),
            storage=requests.get('storage', ''),
            storage_class=storage.get('storageClassName', ''),
        )

@dataclasses.dataclass
class VMInterface:
    name: str
    model: str
    mac_address: str
    state: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMInterface':
        return VMInterface(
            name=dictionary.get('name', ''),
            model=dictionary.get('model', ''),
            mac_address=dictionary.get('macAddress', ''),
            state=dictionary.get('state', ''),
        )

@dataclasses.dataclass
class VMDeviceDisk:
    name: str
    boot_order: int

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMDeviceDisk':
        return VMDeviceDisk(
            name=dictionary.get('name', ''),
            boot_order=dictionary.get('bootOrder', 0),
        )

@dataclasses.dataclass
class VMVolume:
    name: str
    data_volume: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMVolume':
        dv = dictionary.get('dataVolume', {})
        return VMVolume(
            name=dictionary.get('name', ''),
            data_volume=dv.get('name', ''),
        )

@dataclasses.dataclass
class VMDomain:
    architecture: str
    disks: list[VMDeviceDisk]
    interfaces: list[VMInterface]
    volumes: list[VMVolume]
    subdomain: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMDomain':
        return VMDomain(
            architecture=dictionary.get('architecture', ''),
            disks=[VMDeviceDisk.from_dict(disk) for disk in dictionary.get('domain', {}).get('devices', {}).get('disks', [])],
            interfaces=[VMInterface.from_dict(iface) for iface in dictionary.get('domain', {}).get('devices', {}).get('interfaces', [])],
            volumes=[VMVolume.from_dict(vol) for vol in dictionary.get('volumes', [])],
            subdomain=dictionary.get('subdomain', ''),
        )

@dataclasses.dataclass
class VMStatus:
    printable_status: str
    run_strategy: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMStatus':
        return VMStatus(
            printable_status=dictionary.get('printableStatus', ''),
            run_strategy=dictionary.get('runStrategy', ''),
        )

@dataclasses.dataclass
class VMDefinition:
    metadata: VMMetadata
    run_strategy: str
    status: VMStatus
    volume_template: VMVolumeTemplate
    domain: VMDomain

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMDefinition':
        spec = dictionary.get('spec', {})
        template = spec.get('template', {}).get('spec', {})
        return VMDefinition(
            metadata=VMMetadata.from_dict(dictionary.get('metadata', {})),
            run_strategy=spec.get('runStrategy', ''),
            status=VMStatus.from_dict(dictionary.get('status', {})),
            volume_template=VMVolumeTemplate.from_dict(spec.get('dataVolumeTemplates', [{}])[0]),
            domain=VMDomain.from_dict(template),
        )

    
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
