import datetime
import re
import typing
import dataclasses
import collections.abc

NETWORK_RE: typing.Final[typing.Pattern] = re.compile(r'([a-zA-Z0-9]+)=([^,]+)')  # May have vla id at end

# Conversor from dictionary to NamedTuple
CONVERSORS: typing.Final[collections.abc.MutableMapping[typing.Type, collections.abc.Callable]] = {
    str: lambda x: str(x),
    bool: lambda x: bool(x),
    int: lambda x: int(x or '0'),
    float: lambda x: float(x or '0'),
    datetime.datetime: lambda x: datetime.datetime.fromtimestamp(int(x)),
}


def _from_dict(
    type: type[typing.Any],
    dictionary: collections.abc.MutableMapping[str, typing.Any],
    extra: typing.Optional[collections.abc.Mapping[str, typing.Any]] = None,
) -> typing.Any:
    extra = extra or {}
    return type(
        **{
            k: CONVERSORS.get(type.__annotations__.get(k, str), lambda x: x)(
                dictionary.get(k, extra.get(k, None))
            )
            for k in type._fields  # type: ignore
        }
    )


@dataclasses.dataclass(slots=True)
class Cluster:
    name: str
    version: str
    id: str
    nodes: int
    quorate: int

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'Cluster':
        return _from_dict(Cluster, dictionary)


@dataclasses.dataclass(slots=True)
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
        return _from_dict(Node, dictionary)


@dataclasses.dataclass(slots=True)
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
        dictionary['name'] = dictionary['node']
        return _from_dict(NodeStats, dictionary)

    @staticmethod
    def empty():
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


@dataclasses.dataclass(slots=True)
class ClusterStatus:
    cluster: typing.Optional[Cluster]
    nodes: list[Node]

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'ClusterStatus':
        nodes: list[Node] = []
        cluster: typing.Optional[Cluster] = None

        for i in dictionary['data']:
            if i['type'] == 'cluster':
                cluster = Cluster.from_dict(i)
            else:
                nodes.append(Node.from_dict(i))

        return ClusterStatus(cluster=cluster, nodes=nodes)


@dataclasses.dataclass(slots=True)
class UPID:
    node: str
    pid: int
    pstart: int
    starttime: datetime.datetime
    type: str
    vmid: int
    user: str
    upid: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'UPID':
        upid = dictionary['data']
        d = upid.split(':')
        return UPID(
            node=d[1],
            pid=int(d[2], 16),
            pstart=int(d[3], 16),
            starttime=datetime.datetime.fromtimestamp(int(d[4], 16)),
            type=d[5],
            vmid=int(d[6]),
            user=d[7],
            upid=upid,
        )


@dataclasses.dataclass(slots=True)
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
        return _from_dict(TaskStatus, dictionary['data'])

    def is_running(self) -> bool:
        return self.status == 'running'

    def is_finished(self) -> bool:
        return self.status == 'stopped'

    def is_completed(self) -> bool:
        return self.is_finished() and self.exitstatus == 'OK'

    def is_errored(self) -> bool:
        return self.is_finished() and not self.is_completed()


@dataclasses.dataclass(slots=True)
class NetworkConfiguration:
    net: str
    type: str
    mac: str

    @staticmethod
    def from_str(net: str, value: str) -> 'NetworkConfiguration':
        v = NETWORK_RE.match(value)
        type = mac = ''
        if v:
            type, mac = v.group(1), v.group(2)

        return NetworkConfiguration(net=net, type=type, mac=mac)


@dataclasses.dataclass(slots=True)
class VMInfo:
    status: str
    vmid: int
    node: str
    template: bool

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

        data = _from_dict(VMInfo, dictionary, {'vgpu_type': vgpu_type})

        return data


@dataclasses.dataclass(slots=True)
class VMConfiguration:
    name: str
    vga: str
    sockets: int
    cores: int
    vmgenid: str
    digest: str
    networks: list[NetworkConfiguration]

    template: bool

    @staticmethod
    def from_dict(src: collections.abc.MutableMapping[str, typing.Any]) -> 'VMConfiguration':
        nets: list[NetworkConfiguration] = []
        for k in src.keys():
            if k[:3] == 'net':
                nets.append(NetworkConfiguration.from_str(k, src[k]))

        src['networks'] = nets
        return _from_dict(VMConfiguration, src)


@dataclasses.dataclass(slots=True)
class VmCreationResult:
    node: str
    vmid: int
    upid: UPID


@dataclasses.dataclass(slots=True)
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
    used_fraction: float

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'StorageInfo':
        return _from_dict(StorageInfo, dictionary)


@dataclasses.dataclass(slots=True)
class PoolInfo:
    poolid: str
    comments: str

    @staticmethod
    def from_dict(dictionary: collections.abc.MutableMapping[str, typing.Any]) -> 'PoolInfo':
        return _from_dict(PoolInfo, dictionary)
