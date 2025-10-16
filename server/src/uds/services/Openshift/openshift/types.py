import dataclasses
import enum
import typing
import logging

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
