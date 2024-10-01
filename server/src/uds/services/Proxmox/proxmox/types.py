import collections.abc
import dataclasses
import datetime
import enum
import re
import typing

from . import exceptions as prox_exceptions

NETWORK_RE: typing.Final[typing.Pattern[str]] = re.compile(r'([a-zA-Z0-9]+)=([^,]+)')  # May have vla id at end


class VMStatus(enum.StrEnum):
    RUNNING = 'running'
    STOPPED = 'stopped'

    UNKNOWN = 'unknown'

    def is_running(self) -> bool:
        return self == VMStatus.RUNNING

    @staticmethod
    def from_str(value: str) -> 'VMStatus':
        try:
            return VMStatus(value)
        except ValueError:
            return VMStatus.UNKNOWN


# Need to be "NamedTuple"s because we use _fields attribute
@dataclasses.dataclass
class Cluster:
    name: str
    version: str
    id: str
    nodes: int
    quorate: int

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'Cluster':
        return Cluster(
            name=dictionary.get('name', ''),
            version=dictionary.get('version', ''),
            id=dictionary.get('id', ''),
            nodes=dictionary.get('nodes', 0),
            quorate=dictionary.get('quorate', 0),
        )


@dataclasses.dataclass
class Node:
    name: str
    online: bool
    local: bool
    nodeid: int
    ip: str
    level: str
    id: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'Node':
        return Node(
            name=dictionary.get('name', ''),
            online=dictionary.get('online', False),
            local=dictionary.get('local', False),
            nodeid=dictionary.get('nodeid', 0),
            ip=dictionary.get('ip', ''),
            level=dictionary.get('level', ''),
            id=dictionary.get('id', ''),
        )

    @staticmethod
    def null() -> 'Node':
        return Node(
            name='',
            online=False,
            local=False,
            nodeid=0,
            ip='',
            level='',
            id='',
        )


@dataclasses.dataclass
class NodeStats:
    name: str
    status: str
    uptime: int
    disk: int
    maxdisk: int
    level: str
    id: str
    mem: int
    maxmem: int
    cpu: float
    maxcpu: int

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'NodeStats':
        return NodeStats(
            name=dictionary.get('node', ''),
            status=dictionary.get('status', ''),
            uptime=dictionary.get('uptime', 0),
            disk=dictionary.get('disk', 0),
            maxdisk=dictionary.get('maxdisk', 0),
            level=dictionary.get('level', ''),
            id=dictionary.get('id', ''),
            mem=dictionary.get('mem', 0),
            maxmem=dictionary.get('maxmem', 0),
            cpu=dictionary.get('cpu', 0),
            maxcpu=dictionary.get('maxcpu', 0),
        )

    @staticmethod
    def null() -> 'NodeStats':
        return NodeStats(
            name='',
            status='offline',
            uptime=0,
            disk=0,
            maxdisk=0,
            level='',
            id='',
            mem=1,
            maxmem=1,
            cpu=1,
            maxcpu=1,
        )


@dataclasses.dataclass
class ClusterInfo:
    cluster: typing.Optional[Cluster]
    nodes: list[Node]

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'ClusterInfo':
        nodes: list[Node] = []
        cluster: typing.Optional[Cluster] = None

        for i in dictionary['data']:
            if i['type'] == 'cluster':
                cluster = Cluster.from_dict(i)
            else:
                nodes.append(Node.from_dict(i))

        return ClusterInfo(cluster=cluster, nodes=nodes)


@dataclasses.dataclass
class ExecResult:
    node: str
    pid: int
    pstart: int
    starttime: datetime.datetime
    type: str
    vmid: int
    user: str
    upid: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'ExecResult':
        upid = dictionary['data']
        d = upid.split(':')
        return ExecResult(
            node=d[1],
            pid=int(d[2], 16),
            pstart=int(d[3], 16),
            starttime=datetime.datetime.fromtimestamp(int(d[4], 16)),
            type=d[5],
            vmid=int(d[6]),
            user=d[7],
            upid=upid,
        )


@dataclasses.dataclass
class TaskStatus:
    node: str
    pid: int
    pstart: int
    starttime: datetime.datetime
    type: str
    status: str
    exitstatus: str
    user: str
    upid: str
    id: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'TaskStatus':
        data = dictionary['data']
        return TaskStatus(
            node=data['node'],
            pid=data['pid'],
            pstart=data['pstart'],
            starttime=datetime.datetime.fromtimestamp(data['starttime']),
            type=data['type'],
            status=data['status'],
            exitstatus=data.get('exitstatus', ''),
            user=data['user'],
            upid=data['upid'],
            id=data['id'],
        )

    def is_running(self) -> bool:
        return self.status == 'running'

    def is_finished(self) -> bool:
        return self.status == 'stopped'

    def is_completed(self) -> bool:
        return self.is_finished() and self.exitstatus == 'OK'

    def is_errored(self) -> bool:
        return self.is_finished() and not self.is_completed()


@dataclasses.dataclass
class NetworkConfiguration:
    net: str
    type: str
    macaddr: str

    netdata: str  # Original data
    
    def is_null(self) -> bool:
        return self.net == ''

    def set_mac_address(self, macaddr: str) -> None:
        self.macaddr = macaddr
        # Replace mac address in netdata
        self.netdata = re.sub(r'^([^=]+)=([^,]+),', r'\1={},'.format(macaddr), self.netdata)

    @staticmethod
    def from_str(net: str, netdata: str) -> 'NetworkConfiguration':
        v = NETWORK_RE.match(netdata)
        type = mac = ''
        if v:
            type, mac = v.group(1), v.group(2)

        return NetworkConfiguration(net=net, type=type, macaddr=mac, netdata=netdata)

    @staticmethod
    def null() -> 'NetworkConfiguration':
        return NetworkConfiguration(net='', type='', macaddr='', netdata='')

@dataclasses.dataclass
class HAInfo:
    state: str
    group: str
    managed: bool

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'HAInfo':
        return HAInfo(
            state=dictionary.get('state', ''),
            group=dictionary.get('group', ''),
            managed=dictionary.get('managed', False),
        )

    @staticmethod
    def null() -> 'HAInfo':
        return HAInfo(
            state='',
            group='',
            managed=False,
        )


@dataclasses.dataclass
class VMInfo:
    id: int
    status: VMStatus
    node: str
    template: bool
    ha: HAInfo

    agent: typing.Optional[str]
    cpus: typing.Optional[int]
    lock: typing.Optional[str]  # if suspended, lock == "suspended" & qmpstatus == "stopped"
    disk: typing.Optional[int]
    maxdisk: typing.Optional[int]
    mem: typing.Optional[int]
    maxmem: typing.Optional[int]
    name: typing.Optional[str]
    pid: typing.Optional[int]
    qmpstatus: typing.Optional[str]  # stopped, running, paused (in memory)
    tags: typing.Optional[str]
    uptime: typing.Optional[int]
    netin: typing.Optional[int]
    netout: typing.Optional[int]
    diskread: typing.Optional[int]
    diskwrite: typing.Optional[int]
    vgpu_type: typing.Optional[str]

    def validate(self) -> 'VMInfo':
        if self.id < 0:
            raise prox_exceptions.ProxmoxNotFound('VM not found')
        return self

    def is_null(self) -> bool:
        return self.id == -1

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMInfo':
        vgpu_type = None
        # Look for vgpu type if present
        for k, v in dictionary.items():
            if k.startswith('hostpci'):
                for i in v.split(','):
                    if i.startswith('mdev='):
                        vgpu_type = i[5:]
                        break  # found it, stop looking

            if vgpu_type is not None:
                break  # Already found it, stop looking

        return VMInfo(
            status=VMStatus.from_str(dictionary['status']),
            id=int(dictionary.get('vmid', 0)),
            node=dictionary.get('node', ''),
            template=dictionary.get('template', False),
            ha=HAInfo.from_dict(dictionary.get('ha', {})),
            agent=dictionary.get('agent', None),
            cpus=dictionary.get('cpus', None),
            lock=dictionary.get('lock', None),
            disk=dictionary.get('disk', None),
            maxdisk=dictionary.get('maxdisk', None),
            mem=dictionary.get('mem', None),
            maxmem=dictionary.get('maxmem', None),
            name=dictionary.get('name', None),
            pid=dictionary.get('pid', None),
            qmpstatus=dictionary.get('qmpstatus', None),
            tags=dictionary.get('tags', None),
            uptime=dictionary.get('uptime', None),
            netin=dictionary.get('netin', None),
            netout=dictionary.get('netout', None),
            diskread=dictionary.get('diskread', None),
            diskwrite=dictionary.get('diskwrite', None),
            vgpu_type=vgpu_type,
        )

    @staticmethod
    def null() -> 'VMInfo':
        return VMInfo(
            status=VMStatus.UNKNOWN,
            id=-1,
            node='',
            template=False,
            ha=HAInfo.null(),
            agent=None,
            cpus=None,
            lock=None,
            disk=None,
            maxdisk=None,
            mem=None,
            maxmem=None,
            name=None,
            pid=None,
            qmpstatus=None,
            tags=None,
            uptime=None,
            netin=None,
            netout=None,
            diskread=None,
            diskwrite=None,
            vgpu_type=None,
        )


@dataclasses.dataclass
class VMConfiguration:
    name: str
    vga: str
    sockets: int
    cores: int
    vmgenid: str
    digest: str
    networks: list[NetworkConfiguration]
    tpmstate0: typing.Optional[str]

    template: bool
    protection: bool

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VMConfiguration':
        nets: list[NetworkConfiguration] = []
        for k in dictionary.keys():
            if k[:3] == 'net':
                nets.append(NetworkConfiguration.from_str(k, dictionary[k]))

        return VMConfiguration(
            name=dictionary.get('name', ''),
            vga=dictionary.get('vga', ''),
            sockets=dictionary.get('sockets', 0),
            cores=dictionary.get('cores', 0),
            vmgenid=dictionary.get('vmgenid', ''),
            digest=dictionary.get('digest', ''),
            networks=nets,
            tpmstate0=dictionary.get('tpmstate0', ''),
            template=dictionary.get('template', False),
            protection=dictionary.get('protection', False),
        )


@dataclasses.dataclass
class VmCreationResult:
    vmid: int
    exec_result: ExecResult


@dataclasses.dataclass
class StorageInfo:
    node: str
    storage: str
    content: tuple[str, ...]
    type: str

    shared: bool
    active: bool
    used: int
    avail: int
    total: int

    def is_null(self) -> bool:
        return self.node == '' and self.storage == ''

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'StorageInfo':
        if 'maxdisk' in dictionary:  # From cluster/resources
            total = int(dictionary['maxdisk'])
            used = int(dictionary['disk'])
            avail = total - used
            ttype = dictionary.get('plugintype', '')
            active = dictionary.get('status', '') == 'available'
        else:  # From nodes/storage
            total = int(dictionary.get('total', 0))
            used = int(dictionary.get('used', 0))
            avail = int(dictionary.get('avail', 0))
            ttype = dictionary.get('type', '')
            active = bool(dictionary.get('active', False))
        return StorageInfo(
            node=dictionary.get('node', ''),
            storage=dictionary.get('storage', ''),
            content=tuple(dictionary.get('content', '').split(',')),
            type=ttype,
            shared=bool(dictionary.get('shared', False)),
            active=active,
            used=used,
            avail=avail,
            total=total,
        )

    @staticmethod
    def null() -> 'StorageInfo':
        return StorageInfo(
            node='',
            storage='',
            content=(),
            type='',
            shared=False,
            active=False,
            used=0,
            avail=0,
            total=0,
        )


@dataclasses.dataclass
class PoolMemberInfo:
    id: str
    node: str
    storage: str
    type: str
    vmid: int
    vmname: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'PoolMemberInfo':
        return PoolMemberInfo(
            id=dictionary.get('id', ''),
            node=dictionary.get('node', ''),
            storage=dictionary.get('storage', ''),
            type=dictionary.get('type', ''),
            vmid=dictionary.get('vmid', 0),
            vmname=dictionary.get('vmname', ''),
        )


@dataclasses.dataclass
class PoolInfo:
    id: str  # This is in fact the name, must be also unique
    comments: str
    members: list[PoolMemberInfo]

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'PoolInfo':
        if 'members' in dictionary:
            members: list[PoolMemberInfo] = [PoolMemberInfo.from_dict(i) for i in dictionary['members']]
        else:
            members = []

        return PoolInfo(
            id=dictionary.get('poolid', ''),
            comments=dictionary.get('comments', ''),
            members=members,
        )

    @staticmethod
    def null() -> 'PoolInfo':
        return PoolInfo(
            id='',
            comments='',
            members=[],
        )

    def is_null(self) -> bool:
        return self.id == ''


@dataclasses.dataclass
class SnapshotInfo:
    name: str
    description: str

    parent: typing.Optional[str]
    snaptime: typing.Optional[int]
    vmstate: typing.Optional[bool]

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'SnapshotInfo':
        return SnapshotInfo(
            name=dictionary.get('name', ''),
            description=dictionary.get('description', ''),
            parent=dictionary.get('parent', None),
            snaptime=dictionary.get('snaptime', None),
            vmstate=dictionary.get('vmstate', None),
        )


@dataclasses.dataclass
class VGPUInfo:
    name: str
    description: str
    device: str
    available: bool
    type: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'VGPUInfo':
        return VGPUInfo(
            name=dictionary.get('name', ''),
            description=dictionary.get('description', ''),
            device=dictionary.get('device', ''),
            available=dictionary.get('available', False),
            type=dictionary.get('type', ''),
        )
