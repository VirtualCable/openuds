import json
import urllib3
import urllib.parse
import typing
import logging

import requests

from . import types

from uds.core.util.decorators import allowCache, ensureConected

# DEFAULT_PORT = 8006

CACHE_DURATION = 120  # Keep cache 2 minutes by default

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.cache import Cache


logger = logging.getLogger(__name__)


class ProxmoxError(Exception):
    pass


class ProxmoxConnectionError(ProxmoxError):
    pass


class ProxmoxAuthError(ProxmoxError):
    pass


class PromxmoxNotFound(ProxmoxError):
    pass

# caching helper
def cachingKeyHelper(obj: 'ProxmoxClient') -> str:
    return obj._host  # pylint: disable=protected-access

class ProxmoxClient:
    _host: str
    _port: int
    _credentials: typing.Tuple[typing.Tuple[str, str], typing.Tuple[str, str]]
    _url: str
    _validateCert: bool
    _timeout: int

    _ticket: str
    _csrf: str

    cache: typing.Optional['Cache']

    def __init__(
            self,
            host: str,
            port: int,
            username: str,
            password: str,
            timeout: int = 5,
            validateCertificate: bool = False,
            cache: typing.Optional['Cache'] = None
        ) -> None:
        self._host = host
        self._port = port
        self._credentials = (('username', username), ('password', password))
        self._validateCert = validateCertificate
        self._timeout = timeout
        self._url = 'https://{}:{}/api2/json/'.format(self._host, self._port)

        self.cache = cache

        self._ticket = ''
        self._csrf = ''

        # Disable warnings from urllib
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def headers(self):
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'CSRFPreventionToken': self._csrf
        }

    def _getPath(self, path: str) -> str:
        return self._url + path

    def _get(self, path: str) -> typing.Any:
        result = requests.get(
            self._getPath(path),
            headers=self.headers,
            cookies={'PVEAuthCookie': self._ticket},
            verify=self._validateCert,
            timeout=self._timeout
        )

        logger.debug('GET result to %s: %s -- %s', path, result.status_code, result.content)

        if not result.ok:
            raise ProxmoxAuthError()

        return result.json()

    def _post(self, path: str, data: typing.Optional[typing.Iterable[typing.Tuple[str, str]]] = None) -> typing.Any:
        result = requests.post(
            self._getPath(path),
            data=data,
            headers=self.headers,
            cookies={'PVEAuthCookie': self._ticket},
            verify=self._validateCert,
            timeout=self._timeout
        )

        logger.debug('POST result to %s: %s -- %s', path, result.status_code, result.content)

        if not result.ok:
            raise ProxmoxError(result.content)

        return result.json()

    def _delete(self, path: str, data: typing.Optional[typing.Iterable[typing.Tuple[str, str]]] = None) -> typing.Any:
        result = requests.delete(
            self._getPath(path),
            data=data,
            headers=self.headers,
            cookies={'PVEAuthCookie': self._ticket},
            verify=self._validateCert,
            timeout=self._timeout
        )

        logger.debug('POST result to %s: %s -- %s', path, result.status_code, result.content)

        if not result.ok:
            raise ProxmoxError(result.content)

        return result.json()

    def connect(self) -> None:
        if self._ticket:
            return
        try:
            result = requests.post(
                url=self._getPath('access/ticket'),
                data=self._credentials,
                headers=self.headers,
                verify=self._validateCert,
                timeout=self._timeout
            )
            if not result.ok:
                raise ProxmoxAuthError()
            data = result.json()['data']
            self._ticket = data['ticket']
            self._csrf = data['CSRFPreventionToken']
        except requests.RequestException as e:
            raise ProxmoxConnectionError from e

    def test(self) -> bool:
        try:
            self.connect()
        except Exception as e:
            # logger.error('Error testing proxmox: %s', e)
            return False
        return True

    @ensureConected
    @allowCache('cluster', CACHE_DURATION, cachingKeyFnc=cachingKeyHelper)
    def getClusterInfo(self, **kwargs) -> types.ClusterStatus:
        return types.ClusterStatus.fromJson(self._get('cluster/status'))

    @ensureConected
    def getNextVMId(self) -> int:
        return int(self._get('cluster/nextid')['data'])

    @ensureConected
    @allowCache('nodeNets', CACHE_DURATION, cachingArgs=1, cachingKWArgs=['node'], cachingKeyFnc=cachingKeyHelper)
    def getNodeNetworks(self, node: str, **kwargs):
        return self._get('nodes/{}/network'.format(node))['data']

    @ensureConected
    def getBestNodeForVm(self, minMemory: int = 0) -> typing.Optional[types.NodeStats]:
        best = types.NodeStats.empty()
        node: types.NodeStats
        weightFnc = lambda x: (x.mem /x .maxmem) + x.cpu

        for node in self.getNodesStats():
            if node.status != 'online':
                continue
            if minMemory and node.mem < minMemory + 512000000:  # 512 MB reserved
                continue  # Skips nodes with not enouhg memory
            
            if weightFnc(node) < weightFnc(best):
                best = node

            print(node.name, node.mem / node.maxmem * 100, node.cpu)

        return best if best.status == 'online' else None

    @ensureConected
    def cloneVm(
        self,
        vmId: int,
        name: str,
        description: typing.Optional[str],
        linkedClone: bool,
        toNode: typing.Optional[str] = None,
        toStorage: typing.Optional[str] = None,
        memory: int = 0
    ) -> types.VmCreationResult:
        newVmId = self.getNextVMId()
        vmInfo = self.getVmInfo(vmId)

        fromNode = vmInfo.node

        if not toNode:
            # If storage is not shared, must be done on same as origin
            if toStorage and self.getStorage(toStorage, vmInfo.node).shared:
                node = self.getBestNodeForVm(minMemory=-1)
                if node is None:
                    raise ProxmoxError('No switable node available for new vm {} on Proxmox'.format(name))
                toNode = node.name
            else:
                toNode = fromNode

        # From normal vm, disable "linked cloning"
        if linkedClone and not vmInfo.template:
            linkedClone = False

        params: typing.List[typing.Tuple[str, str]] = [
            ('newid', str(newVmId)),
            ('name', name),
            ('target', toNode),
            ('full', str(int(not linkedClone))),
        ]

        if description:
            params.append(('description', description))

        if toStorage and linkedClone is False:
            params.append(('storage', toStorage))

        logger.debug('PARAMS: %s', params)

        return types.VmCreationResult(
            node=toNode,
            vmid=newVmId,
            upid=types.UPID.fromDict(
                self._post(
                    'nodes/{}/qemu/{}/clone'.format(fromNode, vmId),
                    data=params
                )
            )
        )

    @ensureConected
    def deleteVm(self, vmId: int, node: typing.Optional[str] = None, purge: bool = True) -> types.UPID:
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._delete(
                'nodes/{}/qemu/{}'.format(node, vmId)
            )
        )

    @ensureConected
    def getTask(self, node: str, upid: str) -> types.TaskStatus:
        return types.TaskStatus.fromJson(self._get('nodes/{}/tasks/{}/status'.format(node, urllib.parse.quote(upid))))

    @ensureConected
    @allowCache('vms', CACHE_DURATION, cachingArgs=1, cachingKWArgs='node', cachingKeyFnc=cachingKeyHelper)
    def listVms(self, node: typing.Union[None, str, typing.Iterable[str]] = None) -> typing.List[types.VMInfo]:
        nodeList: typing.Iterable[str]
        if node is None:
            nodeList = [n.name for n in self.getClusterInfo().nodes]
        elif isinstance(node, str):
            nodeList = [node]
        else:
            nodeList = node

        result = []
        for nodeName in nodeList:
            for vm in self._get('nodes/{}/qemu'.format(nodeName))['data']:
                vm['node'] = nodeName
                result.append(types.VMInfo.fromDict(vm))

        return sorted(result, key=lambda x: '{}{}'.format(x.node, x.name))

    @ensureConected
    @allowCache('vmi', CACHE_DURATION, cachingArgs=[1, 2], cachingKWArgs=['vmId', 'node'], cachingKeyFnc=cachingKeyHelper)
    def getVmInfo(self, vmId: int, node: typing.Optional[str] = None, **kwargs) -> types.VMInfo:
        # TODO: try first form cache?
        nodes = [types.Node(node, False, False, 0, '', '', '')] if node else self.getClusterInfo().nodes
        for n in nodes:
            try:
                vm = self._get('nodes/{}/qemu/{}/status/current'.format(n.name, vmId))['data']
                vm['node'] = n.name
                return types.VMInfo.fromDict(vm)
            except ProxmoxError:
                pass  # Not found, try next
        raise PromxmoxNotFound()

       
    @ensureConected
    @allowCache('vmc', CACHE_DURATION, cachingArgs=[1, 2], cachingKWArgs=['vmId', 'node'], cachingKeyFnc=cachingKeyHelper)
    def getVmConfiguration(self, vmId: int, node: typing.Optional[str] = None, **kwargs):
        node = node or self.getVmInfo(vmId).node
        return types.VMConfiguration.fromDict(self._get('nodes/{}/qemu/{}/config'.format(node, vmId))['data'])

    @ensureConected
    def startVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(self._post('nodes/{}/qemu/{}/status/start'.format(node, vmId)))

    @ensureConected
    def stopVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(self._post('nodes/{}/qemu/{}/status/stop'.format(node, vmId)))

    @ensureConected
    def suspendVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(self._post('nodes/{}/qemu/{}/status/suspend'.format(node, vmId)))

    @ensureConected
    def convertToTemplate(self, vmId: int, node: typing.Optional[str] = None) -> None:
        node = node or self.getVmInfo(vmId).node
        self._post('nodes/{}/qemu/{}/template'.format(node, vmId))

    # proxmox has a "resume", but start works for suspended vm so we use it
    resumeVm = startVm

    @ensureConected
    @allowCache('storage', CACHE_DURATION, cachingArgs=[1, 2], cachingKWArgs=['storage', 'node'], cachingKeyFnc=cachingKeyHelper)
    def getStorage(self, storage: str, node: str, **kwargs) -> types.StorageInfo:
        return types.StorageInfo.fromDict(self._get('nodes/{}/storage/{}/status'.format(node, urllib.parse.quote(storage)))['data'])

    @ensureConected
    @allowCache('storages', CACHE_DURATION, cachingArgs=[1, 2], cachingKWArgs=['node', 'content'], cachingKeyFnc=cachingKeyHelper)
    def listStorage(self, node: typing.Union[None, str, typing.Iterable[str]] = None, content: typing.Optional[str] = None, **kwargs)  -> typing.List[types.StorageInfo]:
        """We use a list for storage instead of an iterator, so we can cache it...
        """
        nodeList: typing.Iterable[str]
        if node is None:
            nodeList = [n.name for n in self.getClusterInfo().nodes if n.online]
        elif isinstance(node, str):
            nodeList = [node]
        else:
            nodeList = node
        params = '' if not content else '?content={}'.format(urllib.parse.quote(content))
        result: typing.List[types.StorageInfo] = []

        for nodeName in nodeList:
            for storage in self._get('nodes/{}/storage{}'.format(nodeName, params))['data']:
                storage['node'] = nodeName
                storage['content'] = storage['content'].split(',')
                result.append(types.StorageInfo.fromDict(storage))

        return result

    @ensureConected
    @allowCache('nodeStats', CACHE_DURATION, cachingKeyFnc=cachingKeyHelper)
    def getNodesStats(self, **kwargs) -> typing.List[types.NodeStats]:
        return [types.NodeStats.fromDict(nodeStat) for nodeStat in self._get('cluster/resources?type=node')['data']]
