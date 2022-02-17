# -*- coding: utf-8 -*-

#
# Copyright (c) 2019-2021 Virtual Cable S.L.U.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""

import urllib3
import urllib3.exceptions
import urllib.parse
import typing
import logging

import requests

from . import types

from uds.core.util.decorators import allowCache, ensureConected

# DEFAULT_PORT = 8006

CACHE_DURATION = 120  # Keep cache 2 minutes by default
CACHE_INFO_DURATION = 30

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


class ProxmoxNotFound(ProxmoxError):
    pass


class ProxmoxNodeUnavailableError(ProxmoxConnectionError):
    pass


# caching helper
def cachingKeyHelper(obj: 'ProxmoxClient') -> str:
    return obj._host


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
        cache: typing.Optional['Cache'] = None,
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

        # Disable warnings from urllib for
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def headers(self):
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'CSRFPreventionToken': self._csrf,
        }

    @staticmethod
    def checkError(response: requests.Response) -> typing.Any:
        if not response.ok:
            errMsg = 'Status code {}'.format(response.status_code)
            if response.status_code == 595:
                raise ProxmoxNodeUnavailableError()

            if response.status_code == 403:
                raise ProxmoxAuthError()

            if response.status_code == 400:
                try:
                    errMsg = 'Errors on request: {}'.format(response.json()['errors'])
                except Exception:  # No joson or no errors
                    pass

            raise ProxmoxError(errMsg)

        return response.json()

    def _getPath(self, path: str) -> str:
        return self._url + path

    def _get(self, path: str) -> typing.Any:
        try:
            result = requests.get(
                self._getPath(path),
                headers=self.headers,
                cookies={'PVEAuthCookie': self._ticket},
                verify=self._validateCert,
                timeout=self._timeout,
            )

            logger.debug(
                'GET result to %s: %s -- %s', path, result.status_code, result.content
            )
        except requests.ConnectionError as e:
            raise ProxmoxConnectionError(e)

        return ProxmoxClient.checkError(result)

    def _post(
        self,
        path: str,
        data: typing.Optional[typing.Iterable[typing.Tuple[str, str]]] = None,
    ) -> typing.Any:
        try:
            result = requests.post(
                self._getPath(path),
                data=data,
                headers=self.headers,
                cookies={'PVEAuthCookie': self._ticket},
                verify=self._validateCert,
                timeout=self._timeout,
            )

            logger.debug(
                'POST result to %s: %s -- %s', path, result.status_code, result.content
            )
        except requests.ConnectionError as e:
            raise ProxmoxConnectionError(e)

        return ProxmoxClient.checkError(result)

    def _delete(
        self,
        path: str,
        data: typing.Optional[typing.Iterable[typing.Tuple[str, str]]] = None,
    ) -> typing.Any:
        try:
            result = requests.delete(
                self._getPath(path),
                data=data,
                headers=self.headers,
                cookies={'PVEAuthCookie': self._ticket},
                verify=self._validateCert,
                timeout=self._timeout,
            )

            logger.debug(
                'DELETE result to %s: %s -- %s -- %s',
                path,
                result.status_code,
                result.content,
                result.headers,
            )
        except requests.ConnectionError as e:
            raise ProxmoxConnectionError(e)

        return ProxmoxClient.checkError(result)

    def connect(self, force=False) -> None:
        if self._ticket:
            return  # Already connected

        # we could cache this for a while, we know that at least for 30 minutes
        if self.cache and not force:
            dc = self.cache.get(self._host + 'conn')
            if dc:  # Stored on cache
                self._ticket, self._csrf = dc
                return

        try:
            result = requests.post(
                url=self._getPath('access/ticket'),
                data=self._credentials,
                headers=self.headers,
                verify=self._validateCert,
                timeout=self._timeout,
            )
            if not result.ok:
                raise ProxmoxAuthError()
            data = result.json()['data']
            self._ticket = data['ticket']
            self._csrf = data['CSRFPreventionToken']

            if self.cache:
                self.cache.put(
                    self._host + 'conn', (self._ticket, self._csrf), validity=1800
                )  # 30 minutes
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
    def isVMIdAvailable(self, vmId: int) -> bool:
        try:
            self._get(f'cluster/nextid?vmid={vmId}')
        except Exception:  # Not available
            return False
        return True

    @ensureConected
    @allowCache(
        'nodeNets',
        CACHE_DURATION,
        cachingArgs=1,
        cachingKWArgs=['node'],
        cachingKeyFnc=cachingKeyHelper,
    )
    def getNodeNetworks(self, node: str, **kwargs):
        return self._get('nodes/{}/network'.format(node))['data']

    @ensureConected
    def getBestNodeForVm(self, minMemory: int = 0) -> typing.Optional[types.NodeStats]:
        best = types.NodeStats.empty()
        node: types.NodeStats
        weightFnc = lambda x: (x.mem / x.maxmem) + (x.cpu / x.maxcpu) * 1.3

        # Offline nodes are not "the best"
        for node in filter(lambda x: x.status == 'online', self.getNodesStats()):
            if minMemory and node.mem < minMemory + 512000000:  # 512 MB reserved
                continue  # Skips nodes with not enouhg memory

            if weightFnc(node) < weightFnc(best):
                best = node

            # logger.debug('Node values for best: %s %f %f', node.name, node.mem / node.maxmem * 100, node.cpu)

        return best if best.status == 'online' else None

    @ensureConected
    def cloneVm(
        self,
        vmId: int,
        newVmId: int,
        name: str,
        description: typing.Optional[str],
        linkedClone: bool,
        toNode: typing.Optional[str] = None,
        toStorage: typing.Optional[str] = None,
        toPool: typing.Optional[str] = None,
    ) -> types.VmCreationResult:
        vmInfo = self.getVmInfo(vmId)

        fromNode = vmInfo.node

        if not toNode:
            logger.debug('Selecting best node')
            # If storage is not shared, must be done on same as origin
            if toStorage and self.getStorage(toStorage, vmInfo.node).shared:
                node = self.getBestNodeForVm(minMemory=-1)
                if node is None:
                    raise ProxmoxError(
                        'No switable node available for new vm {} on Proxmox'.format(
                            name
                        )
                    )
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

        if toPool:
            params.append(('pool', toPool))

        if linkedClone is False:
            params.append(
                ('format', 'qcow2')
            )  # Ensure clone for templates is on qcow2 format

        logger.debug('PARAMS: %s', params)

        return types.VmCreationResult(
            node=toNode,
            vmid=newVmId,
            upid=types.UPID.fromDict(
                self._post('nodes/{}/qemu/{}/clone'.format(fromNode, vmId), data=params)
            ),
        )

    @ensureConected
    @allowCache('hagrps', CACHE_DURATION, cachingKeyFnc=cachingKeyHelper)
    def listHAGroups(self) -> typing.List[str]:
        return [g['group'] for g in self._get('cluster/ha/groups')['data']]

    @ensureConected
    def enableVmHA(
        self, vmId: int, started: bool = False, group: typing.Optional[str] = None
    ) -> None:
        self._post(
            'cluster/ha/resources',
            data=[
                ('sid', 'vm:{}'.format(vmId)),
                ('comment', 'UDS HA VM'),
                ('state', 'started' if started else 'stopped'),
                ('max_restart', '4'),
                ('max_relocate', '4'),
            ]
            + ([('group', group)] if group else []),
        )

    @ensureConected
    def disableVmHA(self, vmId: int) -> None:
        try:
            self._delete('cluster/ha/resources/vm%3A{}'.format(vmId))
        except Exception:
            logger.exception('removeFromHA')

    @ensureConected
    def setProtection(
        self, vmId: int, node: typing.Optional[str] = None, protection: bool = False
    ) -> None:
        params: typing.List[typing.Tuple[str, str]] = [
            ('protection', str(int(protection))),
        ]
        node = node or self.getVmInfo(vmId).node
        self._post('nodes/{}/qemu/{}/config'.format(node, vmId), data=params)

    @ensureConected
    def deleteVm(
        self, vmId: int, node: typing.Optional[str] = None, purge: bool = True
    ) -> types.UPID:
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._delete('nodes/{}/qemu/{}?purge=1'.format(node, vmId))
        )

    @ensureConected
    def getTask(self, node: str, upid: str) -> types.TaskStatus:
        return types.TaskStatus.fromJson(
            self._get('nodes/{}/tasks/{}/status'.format(node, urllib.parse.quote(upid)))
        )

    @ensureConected
    @allowCache(
        'vms',
        CACHE_DURATION,
        cachingArgs=1,
        cachingKWArgs='node',
        cachingKeyFnc=cachingKeyHelper,
    )
    def listVms(
        self, node: typing.Union[None, str, typing.Iterable[str]] = None
    ) -> typing.List[types.VMInfo]:
        nodeList: typing.Iterable[str]
        if node is None:
            nodeList = [n.name for n in self.getClusterInfo().nodes if n.online]
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
    @allowCache(
        'vmip',
        CACHE_INFO_DURATION,
        cachingArgs=[1, 2],
        cachingKWArgs=['vmId', 'poolId'],
        cachingKeyFnc=cachingKeyHelper,
    )
    def getVMPoolInfo(self, vmId: int, poolId: str, **kwargs) -> types.VMInfo:
        # try to locate machine in pool
        node = None
        if poolId:
            try:
                for i in self._get(f'pools/{poolId}')['data']['members']:
                    try:
                        if i['vmid'] == vmId:
                            node = i['node']
                            break
                    except Exception:
                        pass
            except Exception:  # Error requesting pool, fallback to getVmInfo
                pass

        return self.getVmInfo(vmId, node, **kwargs)

    @ensureConected
    @allowCache(
        'vmin',
        CACHE_INFO_DURATION,
        cachingArgs=[1, 2],
        cachingKWArgs=['vmId', 'node'],
        cachingKeyFnc=cachingKeyHelper,
    )
    def getVmInfo(
        self, vmId: int, node: typing.Optional[str] = None, **kwargs
    ) -> types.VMInfo:
        nodes = (
            [types.Node(node, False, False, 0, '', '', '')]
            if node
            else self.getClusterInfo().nodes
        )
        anyNodeIsDown = False
        for n in nodes:
            try:
                vm = self._get('nodes/{}/qemu/{}/status/current'.format(n.name, vmId))[
                    'data'
                ]
                vm['node'] = n.name
                return types.VMInfo.fromDict(vm)
            except ProxmoxConnectionError:
                anyNodeIsDown = True
            except ProxmoxAuthError:
                raise
            except ProxmoxError:
                pass  # Any other error, ignore this node (not found in that node)

        if anyNodeIsDown:
            raise ProxmoxNodeUnavailableError()

        raise ProxmoxNotFound()

    @ensureConected
    # @allowCache('vmc', CACHE_DURATION, cachingArgs=[1, 2], cachingKWArgs=['vmId', 'node'], cachingKeyFnc=cachingKeyHelper)
    def getVmConfiguration(
        self, vmId: int, node: typing.Optional[str] = None, **kwargs
    ):
        node = node or self.getVmInfo(vmId).node
        return types.VMConfiguration.fromDict(
            self._get('nodes/{}/qemu/{}/config'.format(node, vmId))['data']
        )

    @ensureConected
    def startVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._post('nodes/{}/qemu/{}/status/start'.format(node, vmId))
        )

    @ensureConected
    def stopVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._post('nodes/{}/qemu/{}/status/stop'.format(node, vmId))
        )

    @ensureConected
    def resetVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._post('nodes/{}/qemu/{}/status/reset'.format(node, vmId))
        )

    @ensureConected
    def suspendVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._post('nodes/{}/qemu/{}/status/suspend'.format(node, vmId))
        )

    @ensureConected
    def shutdownVm(self, vmId: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.getVmInfo(vmId).node
        return types.UPID.fromDict(
            self._post('nodes/{}/qemu/{}/status/shutdown'.format(node, vmId))
        )

    @ensureConected
    def convertToTemplate(self, vmId: int, node: typing.Optional[str] = None) -> None:
        node = node or self.getVmInfo(vmId).node
        self._post('nodes/{}/qemu/{}/template'.format(node, vmId))
        # Ensure cache is reset for this VM (as it is now a template)
        self.getVmInfo(vmId, force=True)

    # proxmox has a "resume", but start works for suspended vm so we use it
    resumeVm = startVm

    @ensureConected
    @allowCache(
        'storage',
        CACHE_DURATION,
        cachingArgs=[1, 2],
        cachingKWArgs=['storage', 'node'],
        cachingKeyFnc=cachingKeyHelper,
    )
    def getStorage(self, storage: str, node: str, **kwargs) -> types.StorageInfo:
        return types.StorageInfo.fromDict(
            self._get(
                'nodes/{}/storage/{}/status'.format(node, urllib.parse.quote(storage))
            )['data']
        )

    @ensureConected
    @allowCache(
        'storages',
        CACHE_DURATION,
        cachingArgs=[1, 2],
        cachingKWArgs=['node', 'content'],
        cachingKeyFnc=cachingKeyHelper,
    )
    def listStorages(
        self,
        node: typing.Union[None, str, typing.Iterable[str]] = None,
        content: typing.Optional[str] = None,
        **kwargs,
    ) -> typing.List[types.StorageInfo]:
        """We use a list for storage instead of an iterator, so we can cache it..."""
        nodeList: typing.Iterable[str]
        if node is None:
            nodeList = [n.name for n in self.getClusterInfo().nodes if n.online]
        elif isinstance(node, str):
            nodeList = [node]
        else:
            nodeList = node
        params = (
            '' if not content else '?content={}'.format(urllib.parse.quote(content))
        )
        result: typing.List[types.StorageInfo] = []

        for nodeName in nodeList:
            for storage in self._get('nodes/{}/storage{}'.format(nodeName, params))[
                'data'
            ]:
                storage['node'] = nodeName
                storage['content'] = storage['content'].split(',')
                result.append(types.StorageInfo.fromDict(storage))

        return result

    @ensureConected
    @allowCache('nodeStats', CACHE_INFO_DURATION, cachingKeyFnc=cachingKeyHelper)
    def getNodesStats(self, **kwargs) -> typing.List[types.NodeStats]:
        return [
            types.NodeStats.fromDict(nodeStat)
            for nodeStat in self._get('cluster/resources?type=node')['data']
        ]

    @ensureConected
    @allowCache('pools', CACHE_DURATION // 6, cachingKeyFnc=cachingKeyHelper)
    def listPools(self) -> typing.List[types.PoolInfo]:
        return [
            types.PoolInfo.fromDict(nodeStat) for nodeStat in self._get('pools')['data']
        ]
