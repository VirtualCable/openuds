import collections.abc
import dataclasses
import enum
import typing
import logging

from . import exceptions


# The structure seems to be:
#  Groups:
#    - Clouds

logger = logging.getLogger(__name__)


class VMStatus(enum.StrEnum):
    """
    Represents the state of a Openshift vm.
    """

    # OpenShift VM phases and statuses
    # See:
    # and

    # Phases
    PENDING = 'Pending'
    SCHEDULING = 'Scheduling'
    SCHEDULED = 'Scheduled'
    RUNNING = 'Running'
    SUCCEEDED = 'Succeeded'
    FAILED = 'Failed'
    UNKNOWN = 'Unknown'

    # Statuses (printableStatus)
    STARTING = 'Starting'
    STOPPED = 'Stopped'
    STOPPING = 'Stopping'
    MIGRATING = 'Migrating'
    PAUSED = 'Paused'
    SUSPENDED = 'Suspended'
    RESTORING = 'Restoring'
    CLONING = 'Cloning'
    ERROR = 'Error'
    CRASH_LOOP_BACK_OFF = 'CrashLoopBackOff'
    WAITING_FOR_VMI = 'WaitingForVMI'
    WAITING_FOR_VOLUME_BIND = 'WaitingForVolumeBind'
    WAITING_FOR_NETWORK = 'WaitingForNetwork'
    WAITING_FOR_LAUNCHER_POD = 'WaitingForLauncherPod'
    WAITING_FOR_IMAGE = 'WaitingForImage'
    WAITING_FOR_DATA_VOLUME = 'WaitingForDataVolume'
    WAITING_FOR_USER_DATA = 'WaitingForUserData'
    WAITING_FOR_CLOUD_INIT = 'WaitingForCloudInit'
    WAITING_FOR_GUEST_AGENT = 'WaitingForGuestAgent'
    DELETING = 'Deleting'
    TERMINATING = 'Terminating'
    # Custom/legacy
    NOT_USABLE = 'notUsable'
    DENIED = 'Denied'
    WARNING = 'Warning'

    # Not usable, own state
    # We do not support multinode instances, and will not support them because it's a nonsense for UDS
    # but we will find for sure. We also do not support emtpy instances, so we will not use them

    def is_cloneable(self) -> bool:
        """
        Check if the instance is in a state that allows cloning.
        """
        return self in {
            VMStatus.RUNNING,
            VMStatus.STOPPED,
            VMStatus.SUSPENDED,
        }

    def is_cloning(self) -> bool:
        """
        Check if the instance is currently being cloned.
        """
        return self == VMStatus.CLONING

    def is_running(self) -> bool:
        """
        Check if the instance is running.
        """
        return self == VMStatus.RUNNING

    def is_provisioning(self) -> bool:
        """
        Check if the instance is currently being provisioned.
        """
        # OpenShift does not have a 'PROVISIONING' status; adjust as needed
        return self in {
            VMStatus.PENDING,
            VMStatus.SCHEDULING,
            VMStatus.SCHEDULED,
            VMStatus.STARTING,
            VMStatus.WAITING_FOR_VMI,
            VMStatus.WAITING_FOR_VOLUME_BIND,
            VMStatus.WAITING_FOR_NETWORK,
            VMStatus.WAITING_FOR_LAUNCHER_POD,
            VMStatus.WAITING_FOR_IMAGE,
            VMStatus.WAITING_FOR_DATA_VOLUME,
            VMStatus.WAITING_FOR_USER_DATA,
            VMStatus.WAITING_FOR_CLOUD_INIT,
            VMStatus.WAITING_FOR_GUEST_AGENT,
            VMStatus.RESTORING,
            VMStatus.CLONING,
            VMStatus.MIGRATING,
        }

    def is_stopped(self) -> bool:
        """
        Check if the instance is stopped.
        """
        return self == VMStatus.STOPPED

    def is_off(self) -> bool:
        """
        Check if the instance is off (stopped or suspended).
        """
        return self in {VMStatus.STOPPED, VMStatus.SUSPENDED}

    def is_error(self) -> bool:
        """
        Check if the instance is in an error state.
        """
        return self in {
            VMStatus.FAILED,
            VMStatus.DENIED,
        }

    def is_usable(self) -> bool:
        """
        Check if the instance is usable.
        """
        return self not in (VMStatus.NOT_USABLE, VMStatus.UNKNOWN)

    @staticmethod
    def from_string(state: str) -> 'VMStatus':
        """
        Convert a string to a OpenshiftState.
        """
        try:
            return VMStatus(state)
        except ValueError:
            logger.warning(f'Unknown instance state: {state}, defaulting to UNKNOWN')
            return VMStatus.UNKNOWN


@dataclasses.dataclass
class Interface:
    name: str
    mac_address: str
    ip_address: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'Interface':
        try:
            return Interface(
                name=dictionary.get('interfaceName', ''),
                mac_address=dictionary.get('mac', ''),
                ip_address=dictionary.get('ipAddress', ''),
            )
        except Exception as e:
            logger.error(f'Error creating Interface from dict: {e}')
            raise exceptions.OpenshiftError('Invalid Interface data') from e


@dataclasses.dataclass
class VolumeTemplate:
    name: str
    storage: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VolumeTemplate':
        try:
            meta = dictionary.get('metadata', {})
            spec = dictionary.get('spec', {})
            storage = spec.get('storage', {})
            resources = storage.get('resources', {})
            requests = resources.get('requests', {})
            return VolumeTemplate(name=meta.get('name', ''), storage=requests.get('storage', ''))
        except Exception as e:
            logger.error(f'Error creating VolumeTemplate from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VolumeTemplate data') from e


@dataclasses.dataclass
class DeviceDisk:
    name: str
    boot_order: int

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'DeviceDisk':
        try:
            return DeviceDisk(
                name=dictionary.get('name', ''),
                boot_order=dictionary.get('bootOrder', 0),
            )
        except Exception as e:
            logger.error(f'Error creating DeviceDisk from dict: {e}')
            raise exceptions.OpenshiftError('Invalid DeviceDisk data') from e


@dataclasses.dataclass
class Volume:
    name: str
    data_volume: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'Volume':
        try:
            dv = dictionary.get('dataVolume', {})
            return Volume(
                name=dictionary.get('name', ''),
                data_volume=dv.get('name', ''),
            )
        except Exception as e:
            logger.error(f'Error creating Volume from dict: {e}')
            raise exceptions.OpenshiftError('Invalid Volume data') from e


@dataclasses.dataclass
class VM:
    name: str
    namespace: str
    uid: str
    status: VMStatus
    volume_template: VolumeTemplate
    disks: list[DeviceDisk]
    volumes: list[Volume]

    def validate(self) -> 'VM':
        if not self.is_usable():
            raise exceptions.OpenshiftError(f'VM {self.name} is not usable (status: {self.status})')

        return self

    def is_usable(self) -> bool:
        return self.status.is_usable()

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VM':
        try:
            metadata = dictionary.get('metadata', {})
            status_data = dictionary.get('status', {})
            status_str = status_data.get('printableStatus', 'UNKNOWN')
            spec = dictionary.get('spec', {})
            template = spec.get('template', {}).get('spec', {})
            return VM(
                name=metadata.get('name', ''),
                namespace=metadata.get('namespace', ''),
                uid=metadata.get('uid', ''),
                status=VMStatus.from_string(status_str),
                volume_template=VolumeTemplate.from_dict(spec.get('dataVolumeTemplates', [{}])[0]),
                disks=[DeviceDisk.from_dict(disk) for disk in template.get('devices', {}).get('disks', [])],
                volumes=[Volume.from_dict(vol) for vol in template.get('volumes', [])],
            )
        except Exception as e:
            logger.error(f'Error creating Definition from dict: {e}')
            raise exceptions.OpenshiftError('Invalid Definition data') from e


@dataclasses.dataclass
class VMInstance:
    name: str
    namespace: str
    uid: str
    interfaces: list[Interface]
    status: VMStatus
    phase: VMStatus = VMStatus.UNKNOWN  # Use InstanceStatus for phase

    def validate(self) -> 'VMInstance':
        if not self.is_usable():
            raise exceptions.OpenshiftError(f'VMInstance {self.name} is not usable (status: {self.status})')

        return self

    def is_usable(self) -> bool:
        return self.status.is_usable()

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMInstance':
        try:
            metadata = dictionary.get('metadata', {})
            status_data = dictionary.get('status', {})
            phase_str = status_data.get('phase', '')
            status_str = phase_str or status_data.get('printableStatus', 'UNKNOWN')
            return VMInstance(
                name=metadata.get('name', ''),
                namespace=metadata.get('namespace', ''),
                uid=metadata.get('uid', ''),
                interfaces=[Interface.from_dict(iface) for iface in status_data.get('interfaces', [])],
                status=VMStatus.from_string(status_str),
                phase=VMStatus.from_string(phase_str) if phase_str else VMStatus.UNKNOWN,
            )
        except Exception as e:
            logger.error(f'Error creating VMInstance from dict: {e}')
            raise exceptions.OpenshiftError('Invalid VMInstance data') from e
