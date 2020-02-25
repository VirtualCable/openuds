import datetime
import re
import typing

networkRe = re.compile(r'([a-zA-Z0-9]+)=([^,]+)(,bridge=([^,]*),firewall=(.*))?')

# Conversor from dictionary to NamedTuple
conversors: typing.MutableMapping[typing.Type, typing.Callable] = {
    str: lambda x: str(x),
    bool: lambda x: bool(x),
    int: lambda x: int(x or '0'),
    float: lambda x: float(x or '0'),
    datetime.datetime: lambda x: datetime.datetime.fromtimestamp(int(x)),
}

def convertFromDict(type: typing.Type[typing.Any], dictionary: typing.MutableMapping[str, typing.Any]) -> typing.Any:
    return type(**{ k:conversors.get(type.__annotations__.get(k, str), lambda x: x)(dictionary.get(k, None)) for k in type._fields})


class Cluster(typing.NamedTuple):
    name: str
    version: str
    id: str
    nodes: int
    quorate: int

    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'Cluster':
        return convertFromDict(Cluster, dictionary)

class Node(typing.NamedTuple):
    name: str
    online: bool
    local: bool
    nodeid: int
    ip: str
    level: str
    id: str

    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'Node':
        return convertFromDict(Node, dictionary)

class NodeStats(typing.NamedTuple):
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
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'NodeStats':
        dictionary['name'] = dictionary['node']
        return convertFromDict(NodeStats, dictionary)

    @staticmethod
    def empty():
        return NodeStats(name='', status='offline', uptime=0, disk=0, maxdisk=0, level='', id='', mem=1, maxmem=1, cpu=1, maxcpu=1)

class ClusterStatus(typing.NamedTuple):
    cluster: typing.Optional[Cluster]
    nodes: typing.List[Node]

    @staticmethod
    def fromJson(dictionary: typing.MutableMapping[str, typing.Any]) -> 'ClusterStatus':
        nodes: typing.List[Node] = []
        cluster: typing.Optional[Cluster] = None

        for i in dictionary['data']:
            if i['type'] == 'cluster':
                cluster = Cluster.fromDict(i)
            else:
                nodes.append(Node.fromDict(i))

        return ClusterStatus(cluster=cluster, nodes=nodes)

class UPID(typing.NamedTuple):
    node: str
    pid: int
    pstart: int
    starttime: datetime.datetime
    type: str
    vmid: int
    user: str
    upid: str

    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'UPID':
        upid=dictionary['data']
        d = upid.split(':')
        return UPID(
            node=d[1],
            pid=int(d[2], 16),
            pstart=int(d[3], 16),
            starttime=datetime.datetime.fromtimestamp(int(d[4], 16)),
            type=d[5],
            vmid=int(d[6]),
            user=d[7],
            upid=upid
        )

class TaskStatus(typing.NamedTuple):
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
    def fromJson(dictionary: typing.MutableMapping[str, typing.Any]) -> 'TaskStatus':
        return convertFromDict(TaskStatus, dictionary['data'])

    def isRunning(self) -> bool:
        return self.status == 'running'

    def isFinished(self) -> bool:
        return self.status == 'stopped'

    def isCompleted(self) -> bool:
        return self.isFinished() and self.exitstatus == 'OK'

    def isErrored(self) -> bool:
        return self.isFinished() and not self.isCompleted()

class NetworkConfiguration(typing.NamedTuple):
    type: str
    mac: str
    bridge: str
    firewall: bool

    @staticmethod
    def fromString(value: str) -> 'NetworkConfiguration':
        v = networkRe.match(value)
        type = mac = bridge = firewall = ''
        if v:
            type, mac = v.group(1), v.group(2)
            bridge = v.group(4) or ''
            firewall = v.group(5)

        return NetworkConfiguration(type=type, mac=mac, bridge=bridge, firewall=bool(int(firewall)))


class VMInfo(typing.NamedTuple):
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

    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'VMInfo':
        return convertFromDict(VMInfo, dictionary)

class VMConfiguration(typing.NamedTuple):
    name: str
    vga: str
    sockets: int
    cores: int
    vmgenid: str
    digest: str
    networks: typing.List[NetworkConfiguration]

    template: bool

    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'VMConfiguration':
        nets: typing.List[NetworkConfiguration] = []
        for k in dictionary.keys():
            if k[:3] == 'net':
                nets.append(NetworkConfiguration.fromString(dictionary[k]))

        dictionary['networks'] = nets
        return convertFromDict(VMConfiguration, dictionary)

class VmCreationResult(typing.NamedTuple):
    node: str
    vmid: int
    upid: UPID

class StorageInfo(typing.NamedTuple):
    node: str
    storage: str
    content: typing.Tuple[str, ...]
    type: str

    shared: bool
    active: bool
    used: int
    avail: int
    total: int
    used_fraction: float


    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'StorageInfo':
        return convertFromDict(StorageInfo, dictionary)

class PoolInfo(typing.NamedTuple):
    poolid: str
    comments: str

    @staticmethod
    def fromDict(dictionary: typing.MutableMapping[str, typing.Any]) -> 'PoolInfo':

        return convertFromDict(PoolInfo, dictionary)
