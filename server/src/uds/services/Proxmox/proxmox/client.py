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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import re
import time
import typing
import urllib.parse
import logging


from uds.core import types as core_types
from uds.core.util import security
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached

from . import types, consts, exceptions


import requests

logger = logging.getLogger(__name__)


# caching helper
def caching_key_helper(obj: 'ProxmoxClient') -> str:
    return obj._host  # pylint: disable=protected-access


class ProxmoxClient:
    _host: str
    _port: int
    _credentials: tuple[tuple[str, str], tuple[str, str]]
    _use_api_token: bool
    _url: str
    _verify_ssl: bool
    _timeout: int

    _ticket: str
    _csrf: str

    _session: typing.Optional[requests.Session] = None

    cache: typing.Optional['Cache']

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_api_token: bool = False,
        timeout: int = 5,
        verify_ssl: bool = False,
        cache: typing.Optional['Cache'] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._credentials = (('username', username), ('password', password))
        self._use_api_token = use_api_token
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._url = 'https://{}:{}/api2/json/'.format(self._host, self._port)

        self.cache = cache

        self._ticket = ''
        self._csrf = ''

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            return self.connect()
        return self._session

    def connect(self, force: bool = False) -> requests.Session:
        if self._ticket and self._session and not force:
            return self._session

        self._session = security.secure_requests_session(verify=self._verify_ssl)

        if self._use_api_token:
            token = f'{self._credentials[0][1]}={self._credentials[1][1]}'
            # Set _ticket to something, so we don't try to connect again
            self._ticket = 'API_TOKEN'  # Using API token, not a real ticket
            self._session.headers.update(
                {
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    # 'Content-Type': 'application/json',
                    'Authorization': f'PVEAPIToken={token}',
                }
            )
        else:
            self._session.headers.update(
                {
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )

            def _update_session(ticket: str, csrf: str) -> None:
                session = typing.cast('requests.Session', self._session)
                self._ticket = ticket
                self._csrf = csrf
                session.headers.update({'CSRFPreventionToken': self._csrf})
                session.cookies.update(  # pyright: ignore[reportUnknownMemberType]
                    {'PVEAuthCookie': self._ticket},
                )

            # we could cache this for a while, we know that at least for 30 minutes
            if self.cache and not force:
                dc = self.cache.get(self._host + 'conn')
                if dc:  # Stored on cache
                    _update_session(*dc)  # Set session data, dc has ticket, csrf

            try:
                result = self._session.post(
                    url=self.get_api_url('access/ticket'),
                    data=self._credentials,
                    timeout=self._timeout,
                )
                if not result.ok:
                    raise exceptions.ProxmoxAuthError(result.content.decode('utf8'))
                data = result.json()['data']
                ticket = data['ticket']
                csrf = data['CSRFPreventionToken']

                if self.cache:
                    self.cache.put(self._host + 'conn', (ticket, csrf), validity=1800)  # 30 minutes

                _update_session(ticket, csrf)
            except requests.RequestException as e:
                raise exceptions.ProxmoxConnectionError(str(e)) from e

        return self._session

    def ensure_correct(self, response: 'requests.Response', *, node: typing.Optional[str]) -> typing.Any:
        if not response.ok:
            logger.debug('Error on request %s: %s', response.status_code, response.content)
            error_message = 'Status code {}'.format(response.status_code)
            if response.status_code == 595:
                raise exceptions.ProxmoxNodeUnavailableError(response.content.decode('utf8'))

            if response.status_code == 403:
                raise exceptions.ProxmoxAuthError(response.content.decode('utf8'))

            if response.status_code == 400:
                try:
                    error_message = 'Errors on request: {}'.format(response.json()['errors'])
                except Exception:  # nosec: No joson or no errors, use default msg
                    pass

            if response.status_code // 100 == 5 and node:
                # Try to get from journal
                try:
                    journal = [x for x in filter(lambda x: 'failed' in x, self.journal(node, 4))]
                    logger.error('Proxmox error 500:')
                    for line in journal:
                        logger.error(' * %s', line)

                    error_message = f'Error {response.status_code} on request: {" ## ".join(journal)}'
                except Exception:
                    pass  # If we can't get journal, just use default message

            raise exceptions.ProxmoxError(error_message)

        return response.json()

    def get_api_url(self, path: str) -> str:
        return self._url + path

    def do_get(self, path: str, *, node: typing.Optional[str] = None) -> typing.Any:
        try:
            result = self.session.get(
                self.get_api_url(path),
                timeout=self._timeout,
            )

            logger.debug('GET result to %s: %s -- %s', path, result.status_code, result.content)
        except requests.ConnectionError as e:
            raise exceptions.ProxmoxConnectionError(str(e))

        return self.ensure_correct(result, node=node)

    def do_post(
        self,
        path: str,
        data: typing.Optional[collections.abc.Iterable[tuple[str, str]]] = None,
        *,
        node: typing.Optional[str] = None,
    ) -> typing.Any:
        try:
            result = self.session.post(
                self.get_api_url(path),
                data=data,  # type: ignore
                timeout=self._timeout,
            )

            logger.debug('POST result to %s: %s -- %s', path, result.status_code, result.content)
        except requests.ConnectionError as e:
            raise exceptions.ProxmoxConnectionError(str(e))

        return self.ensure_correct(result, node=node)

    def do_delete(
        self,
        path: str,
        data: typing.Optional[collections.abc.Iterable[tuple[str, str]]] = None,
        *,
        node: typing.Optional[str] = None,
    ) -> typing.Any:
        try:
            result = self.session.delete(
                self.get_api_url(path),
                data=data,  # type: ignore
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
            raise exceptions.ProxmoxConnectionError(str(e))

        return self.ensure_correct(result, node=node)

    def test(self) -> bool:
        try:
            self.connect()
            if self._use_api_token:
                # When using api token, we need to ask for something
                # Because the login has not been done, just the token has been set on headers
                self.get_cluster_info()
        except Exception:
            # logger.error('Error testing proxmox: %s', e)
            return False
        return True

    @cached('cluster', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_cluster_info(self, **kwargs: typing.Any) -> types.ClusterInfo:
        return types.ClusterInfo.from_dict(self.do_get('cluster/status'))

    @cached('cluster_res', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_cluster_resources(
        self, type: typing.Literal['vm', 'storage', 'node', 'sdn'], **kwargs: typing.Any
    ) -> list[dict[str, typing.Any]]:
        # i.e.: self.do_get('cluster/resources?type=vm')
        return self.do_get(f'cluster/resources?type={type}')['data']

    def get_next_vmid(self) -> int:
        return int(self.do_get('cluster/nextid')['data'])

    def is_vmid_available(self, vmid: int) -> bool:
        try:
            self.do_get(f'cluster/nextid?vmid={vmid}')
        except Exception:  # Not available
            return False
        return True

    @cached('nodeNets', consts.CACHE_DURATION, args=1, kwargs=['node'], key_helper=caching_key_helper)
    def get_node_networks(self, node: str, **kwargs: typing.Any) -> typing.Any:
        return self.do_get(f'nodes/{node}/network', node=node)['data']

    # pylint: disable=unused-argument
    @cached('nodeGpuDevices', consts.CACHE_DURATION_LONG, key_helper=caching_key_helper)
    def list_node_gpu_devices(self, node: str, **kwargs: typing.Any) -> list[str]:
        return [
            device['id']
            for device in self.do_get(f'nodes/{node}/hardware/pci', node=node)['data']
            if device.get('mdev')
        ]

    def list_node_vgpus(self, node: str, **kwargs: typing.Any) -> list[types.VGPUInfo]:
        return [
            types.VGPUInfo.from_dict(gpu)
            for device in self.list_node_gpu_devices(node)
            for gpu in self.do_get(f'nodes/{node}/hardware/pci/{device}/mdev', node=node)['data']
        ]

    def node_has_vgpus_available(
        self, node: str, vgpu_type: typing.Optional[str], **kwargs: typing.Any
    ) -> bool:
        return any(
            gpu.available and (vgpu_type is None or gpu.type == vgpu_type) for gpu in self.list_node_vgpus(node)
        )

    def get_best_node_for_vm(
        self,
        min_memory: int = 0,
        must_have_vgpus: typing.Optional[bool] = None,
        mdev_type: typing.Optional[str] = None,
    ) -> typing.Optional[types.NodeStats]:
        '''
        Returns the best node to create a VM on

        Args:
            minMemory (int, optional): Minimum memory required. Defaults to 0.
            mustHaveVGPUS (typing.Optional[bool], optional): If the node must have VGPUS. True, False or None (don't care). Defaults to None.
        '''
        best = types.NodeStats.null()
        node: types.NodeStats

        # Function to calculate the weight of a node
        def calc_weight(x: types.NodeStats) -> float:
            return (x.mem / x.maxmem) + (x.cpu / x.maxcpu) * 1.3

        # Offline nodes are not "the best"
        for node in filter(lambda x: x.status == 'online', self.get_node_stats()):
            if min_memory and node.mem < min_memory + 512000000:  # 512 MB reserved
                continue  # Skips nodes with not enouhg memory
            if must_have_vgpus is not None and must_have_vgpus != bool(self.list_node_gpu_devices(node.name)):
                continue  # Skips nodes without VGPUS if vGPUS are required
            if mdev_type and not self.node_has_vgpus_available(node.name, mdev_type):
                continue  # Skips nodes without free vGPUS of required type if a type is required

            # Get best node using our simple weight function (basically, the less used node, but with a little more weight on CPU)
            if calc_weight(node) < calc_weight(best):
                best = node

            # logger.debug('Node values for best: %s %f %f', node.name, node.mem / node.maxmem * 100, node.cpu)

        return best if best.status == 'online' else None

    def clone_vm(
        self,
        vmid: int,
        new_vmid: int,
        name: str,
        description: typing.Optional[str],
        as_linked_clone: bool,
        target_node: typing.Optional[str] = None,
        target_storage: typing.Optional[str] = None,
        target_pool: typing.Optional[str] = None,
        must_have_vgpus: typing.Optional[bool] = None,
    ) -> types.VmCreationResult:
        # Get info of the vm, also ensures that the vm exists
        vminfo = self.get_vm_info(vmid)

        # Ensure exists target storage
        if target_storage and not any(
            s.storage == target_storage for s in self.list_storages(node=target_node)
        ):
            raise exceptions.ProxmoxDoesNotExists(
                f'Storage "{target_storage}" does not exist on node "{target_node}"'
            )

        # Ensure exists target pool, (id is in fact the name of the pool)
        if target_pool and not any(p.id == target_pool for p in self.list_pools()): 
            raise exceptions.ProxmoxDoesNotExists(f'Pool "{target_pool}" does not exist')

        src_node = vminfo.node

        if not target_node:
            logger.debug('Selecting best node')
            # If storage is not shared, must be done on same as origin
            if target_storage and self.get_storage_info(storage=target_storage, node=vminfo.node).shared:
                node = self.get_best_node_for_vm(
                    min_memory=-1, must_have_vgpus=must_have_vgpus, mdev_type=vminfo.vgpu_type
                )
                if node is None:
                    raise exceptions.ProxmoxError(
                        f'No switable node available for new vm {name} on Proxmox (check memory and VGPUS, space...)'
                    )
                target_node = node.name
            else:
                target_node = src_node

        # Ensure exists target node
        if not any(n.name == target_node for n in self.get_cluster_info().nodes):
            raise exceptions.ProxmoxDoesNotExists(f'Node "{target_node}" does not exist')

        # Check if mustHaveVGPUS is compatible with the node
        if must_have_vgpus is not None and must_have_vgpus != bool(self.list_node_gpu_devices(target_node)):
            raise exceptions.ProxmoxNoGPUError(
                f'Node "{target_node}" does not have VGPUS and they are required'
            )

        if self.node_has_vgpus_available(target_node, vminfo.vgpu_type):
            raise exceptions.ProxmoxNoGPUError(
                f'Node "{target_node}" does not have free VGPUS of type {vminfo.vgpu_type} (requred by VM {vminfo.name})'
            )

        # From normal vm, disable "linked cloning"
        if as_linked_clone and not vminfo.template:
            as_linked_clone = False

        params: list[tuple[str, str]] = [
            ('newid', str(new_vmid)),
            ('name', name),
            ('target', target_node),
            ('full', str(int(not as_linked_clone))),
        ]

        if description:
            params.append(('description', description))

        if target_storage and as_linked_clone is False:
            params.append(('storage', target_storage))

        if target_pool:
            params.append(('pool', target_pool))

        if as_linked_clone is False:
            params.append(('format', 'qcow2'))  # Ensure clone for templates is on qcow2 format

        logger.debug('PARAMS: %s', params)

        return types.VmCreationResult(
            node=target_node,
            vmid=new_vmid,
            upid=types.UPID.from_dict(
                self.do_post(f'nodes/{src_node}/qemu/{vmid}/clone', data=params, node=src_node)
            ),
        )

    @cached('hagrps', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def list_ha_groups(self, **kwargs: typing.Any) -> list[str]:
        return [g['group'] for g in self.do_get('cluster/ha/groups')['data']]

    def enable_vm_ha(self, vmid: int, started: bool = False, group: typing.Optional[str] = None) -> None:
        """
        Enable high availability for a virtual machine.

        Args:
            vmid (int): The ID of the virtual machine.
            started (bool, optional): Whether the virtual machine should be started. Defaults to False.
            group (str, optional): The group to which the virtual machine belongs. Defaults to None.
        """
        self.do_post(
            'cluster/ha/resources',
            data=[
                ('sid', f'vm:{vmid}'),
                ('comment', 'UDS HA VM'),
                ('state', 'started' if started else 'stopped'),
                ('max_restart', '4'),
                ('max_relocate', '4'),
            ]
            + ([('group', group)] if group else []),  # Append ha group if present
        )

    def disable_vm_ha(self, vmid: int) -> None:
        try:
            self.do_delete(f'cluster/ha/resources/vm%3A{vmid}')
        except Exception:
            logger.exception('removeFromHA')

    def set_vm_protection(
        self, vmid: int, *, node: typing.Optional[str] = None, protection: bool = False
    ) -> None:
        params: list[tuple[str, str]] = [
            ('protection', str(int(protection))),
        ]
        node = node or self.get_vm_info(vmid).node
        self.do_post(f'nodes/{node}/qemu/{vmid}/config', data=params, node=node)

    def get_guest_ip_address(
        self, vmid: int, *, node: typing.Optional[str] = None, ip_version: typing.Literal['4', '6', ''] = ''
    ) -> str:
        """Returns the guest ip address of the specified machine"""
        try:
            node = node or self.get_vm_info(vmid).node
            ifaces_list: list[dict[str, typing.Any]] = self.do_get(
                f'nodes/{node}/qemu/{vmid}/agent/network-get-interfaces',
                node=node,
            )['data']['result']
            # look for first non-localhost interface with an ip address
            for iface in ifaces_list:
                if iface['name'] != 'lo' and 'ip-addresses' in iface:
                    for ip in iface['ip-addresses']:
                        if ip['ip-address'].startswith('127.'):
                            continue
                        if ip_version == '4' and ip.get('ip-address-type') != 'ipv4':
                            continue
                        elif ip_version == '6' and ip.get('ip-address-type') != 'ipv6':
                            continue
                        return ip['ip-address']
        except Exception as e:
            logger.info('Error getting guest ip address for machine %s: %s', vmid, e)
            raise exceptions.ProxmoxError(f'No ip address for vm {vmid}: {e}')

        raise exceptions.ProxmoxError('No ip address found for vm {}'.format(vmid))

    def delete_vm(self, vmid: int, node: typing.Optional[str] = None, purge: bool = True) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self.do_delete(f'nodes/{node}/qemu/{vmid}?purge=1', node=node))

    def list_snapshots(self, vmid: int, node: typing.Optional[str] = None) -> list[types.SnapshotInfo]:
        node = node or self.get_vm_info(vmid).node
        try:
            return [
                types.SnapshotInfo.from_dict(s)
                for s in self.do_get(f'nodes/{node}/qemu/{vmid}/snapshot', node=node)['data']
            ]
        except Exception:
            return []  # If we can't get snapshots, just return empty list

    def get_current_vm_snapshot(
        self, vmid: int, node: typing.Optional[str] = None
    ) -> typing.Optional[types.SnapshotInfo]:
        return (
            sorted(
                filter(lambda x: x.snaptime, self.list_snapshots(vmid, node)),
                key=lambda x: x.snaptime or 0,
                reverse=True,
            )
            + [None]
        )[0]

    @cached('snapshots', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def supports_snapshot(self, vmid: int, node: typing.Optional[str] = None) -> bool:
        # If machine uses tpm, snapshots are not supported
        return not self.get_vm_config(vmid, node).tpmstate0

    def create_snapshot(
        self,
        vmid: int,
        *,
        node: 'str|None' = None,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> types.UPID:
        if self.supports_snapshot(vmid, node) is False:
            raise exceptions.ProxmoxError('Machine does not support snapshots')

        node = node or self.get_vm_info(vmid).node
        # Compose a sanitized name, without spaces and with a timestamp
        name = name or f'UDS-{time.time()}'
        params: list[tuple[str, str]] = [
            ('snapname', name),
            ('description', description or f'UDS Snapshot created at {time.strftime("%c")}'),
        ]
        return types.UPID.from_dict(self.do_post(f'nodes/{node}/qemu/{vmid}/snapshot', data=params, node=node))

    def delete_snapshot(
        self,
        vmid: int,
        *,
        node: 'str|None' = None,
        name: typing.Optional[str] = None,
    ) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        if name is None:
            raise exceptions.ProxmoxError('Snapshot name is required')
        return types.UPID.from_dict(self.do_delete(f'nodes/{node}/qemu/{vmid}/snapshot/{name}', node=node))

    def restore_snapshot(
        self,
        vmid: int,
        *,
        node: 'str|None' = None,
        name: typing.Optional[str] = None,
    ) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        if name is None:
            raise exceptions.ProxmoxError('Snapshot name is required')
        return types.UPID.from_dict(
            self.do_post(f'nodes/{node}/qemu/{vmid}/snapshot/{name}/rollback', node=node)
        )

    def get_task_info(self, node: str, upid: str) -> types.TaskStatus:
        return types.TaskStatus.from_dict(
            self.do_get(f'nodes/{node}/tasks/{urllib.parse.quote(upid)}/status', node=node)
        )

    @cached('vms', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def list_vms(
        self, node: typing.Union[None, str, collections.abc.Iterable[str]] = None, **kwargs: typing.Any
    ) -> list[types.VMInfo]:
        node_list: collections.abc.Iterable[str]
        if node is None:
            node_list = [n.name for n in self.get_cluster_info().nodes if n.online]
        elif isinstance(node, str):
            node_list = [node]
        else:
            node_list = node

        # Get all vms from all nodes, better thant getting all vms from each node
        return sorted(
            [
                types.VMInfo.from_dict(vm_info)
                for vm_info in self.get_cluster_resources('vm')
                if vm_info['type'] == 'qemu' and vm_info['node'] in node_list
            ],
            key=lambda x: f'{x.node}{x.name}',
        )

        # result: list[types.VMInfo] = []
        # for node_name in node_list:
        #     for vm in self.do_get(f'nodes/{node_name}/qemu', node=node_name)['data']:
        #         vm['node'] = node_name
        #         result.append(types.VMInfo.from_dict(vm))

        # return sorted(result, key=lambda x: '{}{}'.format(x.node, x.name))

    def get_vm_pool_info(self, vmid: int, poolid: typing.Optional[str], **kwargs: typing.Any) -> types.VMInfo:
        # try to locate machine in pool
        node = None
        if poolid:
            # If for an specific pool, try to locate the node where the machine is
            try:
                for i in self.do_get(f'pools/{poolid}', node=node)['data']['members']:
                    try:
                        if i['vmid'] == vmid:
                            node = i['node']
                            break
                    except Exception:  # nosec: # If vmid is not present, just try next node
                        pass
            except Exception:  # nosec: # If pool is not present, just use default getVmInfo
                pass

        return self.get_vm_info(vmid, node, **kwargs)

    def get_vm_info(self, vmid: int, node: typing.Optional[str] = None, **kwargs: typing.Any) -> types.VMInfo:
        nodes = [types.Node(node, False, False, 0, '', '', '')] if node else self.get_cluster_info().nodes
        any_node_is_down = False
        for n in nodes:
            try:
                vm = self.do_get(f'nodes/{n.name}/qemu/{vmid}/status/current', node=node)['data']
                vm['node'] = n.name
                return types.VMInfo.from_dict(vm)
            except exceptions.ProxmoxConnectionError:
                any_node_is_down = True  # There is at least one node down when we are trying to get info
            except exceptions.ProxmoxAuthError:
                raise
            except exceptions.ProxmoxError:
                pass  # Any other error, ignore this node (not found in that node)

        if any_node_is_down:
            raise exceptions.ProxmoxNodeUnavailableError('All nodes are down or not available')

        raise exceptions.ProxmoxNotFound(f'VM {vmid} not found')

    def get_vm_config(self, vmid: int, node: typing.Optional[str] = None) -> types.VMConfiguration:
        node = node or self.get_vm_info(vmid).node
        return types.VMConfiguration.from_dict(
            self.do_get(f'nodes/{node}/qemu/{vmid}/config', node=node)['data']
        )

    def set_vm_net_mac(
        self,
        vmid: int,
        macaddr: str,
        netid: typing.Optional[str] = None,  # net0, net1, ...
        node: typing.Optional[str] = None,
    ) -> None:
        node = node or self.get_vm_info(vmid).node
    
        net: types.NetworkConfiguration = types.NetworkConfiguration.null()
        
        cfg = self.get_vm_config(vmid, node)
        
        if netid is None:
            net = cfg.networks[0]
        else:
            for i in cfg.networks:
                if i.net == netid:
                    net = i
                    break
                
        # net should be the reference to the network we want to update
        if net.is_null():
            raise exceptions.ProxmoxError(f'Network {netid} not found for VM {vmid}')

        logger.debug('Updating mac address for VM %s: %s=%s', vmid, netid, net.macaddr)

        self.do_post(
            f'nodes/{node}/qemu/{vmid}/config',
            data=[(netid, netdata)],
            node=node,
        )

    def start_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self.do_post(f'nodes/{node}/qemu/{vmid}/status/start', node=node))

    def stop_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self.do_post(f'nodes/{node}/qemu/{vmid}/status/stop', node=node))

    def reset_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self.do_post(f'nodes/{node}/qemu/{vmid}/status/reset', node=node))

    def suspend_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        # Note: Suspend, in fact, invoques sets the machine state to "paused"
        return self.shutdown_vm(vmid, node)
        # node = node or self.get_machine_info(vmid).node
        # return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/status/suspend', node=node))

    def shutdown_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self.do_post(f'nodes/{node}/qemu/{vmid}/status/shutdown', node=node))

    def convert_vm_to_template(self, vmid: int, node: typing.Optional[str] = None) -> None:
        node = node or self.get_vm_info(vmid).node
        self.do_post(f'nodes/{node}/qemu/{vmid}/template', node=node)
        # Ensure cache is reset for this VM (as it is now a template)
        self.get_vm_info(vmid, force=True)

    # proxmox has a "resume", but start works for suspended vm so we use it
    def resume_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        return self.start_vm(vmid, node)

    @cached('storage', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_storage_info(self, node: str, storage: str, **kwargs: typing.Any) -> types.StorageInfo:
        storage_info = types.StorageInfo.from_dict(
            self.do_get(f'nodes/{node}/storage/{urllib.parse.quote(storage)}/status', node=node)['data']
        )
        storage_info.node = node
        storage_info.storage = storage
        return storage_info

    @cached('storages', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def list_storages(
        self,
        *,
        node: typing.Union[None, str, collections.abc.Iterable[str]] = None,
        content: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> list[types.StorageInfo]:
        """We use a list for storage instead of an iterator, so we can cache it..."""
        node_list: set[str]
        match node:
            case None:
                node_list = {n.name for n in self.get_cluster_info().nodes if n.online}
            case str():
                node_list = {node}
            case collections.abc.Iterable():
                node_list = set(node)

        return sorted(
            [
                types.StorageInfo.from_dict(st_info)
                for st_info in self.get_cluster_resources('storage')
                if st_info['node'] in node_list and (content is None or content in st_info['content'])
            ],
            key=lambda x: f'{x.node}{x.storage}',
        )

        # result: list[types.StorageInfo] = []

        # for node_name in nodes:
        #     for storage in self.do_get(f'nodes/{node_name}/storage{params}', node=node_name)['data']:
        #         storage['node'] = node_name
        #         storage['content'] = storage['content'].split(',')
        #         result.append(types.StorageInfo.from_dict(storage))

        # return result

    @cached('nodeStats', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    def get_node_stats(self, **kwargs: typing.Any) -> list[types.NodeStats]:
        # vm | storage | node | sdn are valid types for cluster/resources
        return [
            types.NodeStats.from_dict(nodeStat)
            for nodeStat in self.do_get('cluster/resources?type=node')['data']
        ]

    @cached('pools', consts.CACHE_DURATION // 6, key_helper=caching_key_helper)
    def list_pools(self, **kwargs: typing.Any) -> list[types.PoolInfo]:
        return [types.PoolInfo.from_dict(poolInfo) for poolInfo in self.do_get('pools')['data']]

    @cached('pool', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_pool_info(
        self, pool_id: str, retrieve_vm_names: bool = False, **kwargs: typing.Any
    ) -> types.PoolInfo:
        pool_info = types.PoolInfo.from_dict(self.do_get(f'pools/{pool_id}')['data'])
        if retrieve_vm_names:
            for i in range(len(pool_info.members)):
                try:
                    pool_info.members[i].vmname = self.get_vm_info(pool_info.members[i].vmid).name or ''
                except Exception:
                    pool_info.members[i].vmname = f'VM-{pool_info.members[i].vmid}'
        return pool_info

    def get_console_connection(
        self, vmid: int, node: typing.Optional[str] = None
    ) -> typing.Optional[core_types.services.ConsoleConnectionInfo]:
        """
        Gets the connetion info for the specified machine
        """
        node = node or self.get_vm_info(vmid).node
        res: dict[str, typing.Any] = self.do_post(f'nodes/{node}/qemu/{vmid}/spiceproxy', node=node)['data']
        return core_types.services.ConsoleConnectionInfo(
            type=res['type'],
            proxy=res['proxy'],
            address=res['host'],
            port=res.get('port', None),
            secure_port=res['tls-port'],
            cert_subject=res['host-subject'],
            ticket=core_types.services.ConsoleConnectionTicket(value=res['password']),
            ca=res.get('ca', None),
        )
        # Sample data:
        # 'data': {'proxy': 'http://pvealone.dkmon.com:3128',
        # 'release-cursor': 'Ctrl+Alt+R',
        # 'host': 'pvespiceproxy:63489cf9:101:pvealone::c934cf7f7570012bbebab9e1167402b6471aae16',
        # 'delete-this-file': 1,
        # 'secure-attention': 'Ctrl+Alt+Ins',
        # 'title': 'VM 101 - VM-1',
        # 'password': '31a189dd71ce859867e28dd68ba166a701e77eed',
        # 'type': 'spice',
        # 'toggle-fullscreen': 'Shift+F11',
        # 'host-subject': 'OU=PVE Cluster Node,O=Proxmox Virtual Environment,CN=pvealone.dkmon.com',
        # 'tls-port': 61000,
        # 'ca': '-----BEGIN CERTIFICATE-----\\n......\\n-----END CERTIFICATE-----\\n'}}

    def journal(self, node: str, lastentries: int = 4, **kwargs: typing.Any) -> list[str]:
        try:
            return self.do_get(f'nodes/{node}/journal?lastentries={lastentries}')['data']
        except Exception:
            return []
