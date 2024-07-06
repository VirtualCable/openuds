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
from uds.core.util.decorators import cached, ensure_connected

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
    _url: str
    _validate_cert: bool
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
        validate_certificate: bool = False,
        cache: typing.Optional['Cache'] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._credentials = (('username', username), ('password', password))
        self._validate_cert = validate_certificate
        self._timeout = timeout
        self._url = 'https://{}:{}/api2/json/'.format(self._host, self._port)

        self.cache = cache

        self._ticket = ''
        self._csrf = ''

    @property
    def headers(self) -> dict[str, str]:
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'CSRFPreventionToken': self._csrf,
        }

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

            if response.status_code == 500 and node:
                # Try to get from journal
                try:
                    journal = [x for x in filter(lambda x: 'failed' in x, self.journal(node, 4))]
                    logger.error('Proxmox error 500:')
                    for line in journal:
                        logger.error(' * %s', line)

                    error_message = f'Error 500 on request: {" ## ".join(journal)}'
                except Exception:
                    pass  # If we can't get journal, just use default message

            raise exceptions.ProxmoxError(error_message)

        return response.json()

    def _compose_url_for(self, path: str) -> str:
        return self._url + path

    def _get(self, path: str, *, node: typing.Optional[str] = None) -> typing.Any:
        try:
            result = security.secure_requests_session(verify=self._validate_cert).get(
                self._compose_url_for(path),
                headers=self.headers,
                cookies={'PVEAuthCookie': self._ticket},
                timeout=self._timeout,
            )

            logger.debug('GET result to %s: %s -- %s', path, result.status_code, result.content)
        except requests.ConnectionError as e:
            raise exceptions.ProxmoxConnectionError(str(e))

        return self.ensure_correct(result, node=node)

    def _post(
        self,
        path: str,
        data: typing.Optional[collections.abc.Iterable[tuple[str, str]]] = None,
        *,
        node: typing.Optional[str] = None,
    ) -> typing.Any:
        try:
            result = security.secure_requests_session(verify=self._validate_cert).post(
                self._compose_url_for(path),
                data=data,  # type: ignore
                headers=self.headers,
                cookies={'PVEAuthCookie': self._ticket},
                timeout=self._timeout,
            )

            logger.debug('POST result to %s: %s -- %s', path, result.status_code, result.content)
        except requests.ConnectionError as e:
            raise exceptions.ProxmoxConnectionError(str(e))

        return self.ensure_correct(result, node=node)

    def _delete(
        self,
        path: str,
        data: typing.Optional[collections.abc.Iterable[tuple[str, str]]] = None,
        *,
        node: typing.Optional[str] = None,
    ) -> typing.Any:
        try:
            result = security.secure_requests_session(verify=self._validate_cert).delete(
                self._compose_url_for(path),
                data=data,  # type: ignore
                headers=self.headers,
                cookies={'PVEAuthCookie': self._ticket},
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

    def connect(self, force: bool = False) -> None:
        if self._ticket:
            return  # Already connected

        # we could cache this for a while, we know that at least for 30 minutes
        if self.cache and not force:
            dc = self.cache.get(self._host + 'conn')
            if dc:  # Stored on cache
                self._ticket, self._csrf = dc
                return

        try:
            result = security.secure_requests_session(verify=self._validate_cert).post(
                url=self._compose_url_for('access/ticket'),
                data=self._credentials,
                headers=self.headers,
                timeout=self._timeout,
            )
            if not result.ok:
                raise exceptions.ProxmoxAuthError(result.content.decode('utf8'))
            data = result.json()['data']
            self._ticket = data['ticket']
            self._csrf = data['CSRFPreventionToken']

            if self.cache:
                self.cache.put(self._host + 'conn', (self._ticket, self._csrf), validity=1800)  # 30 minutes
        except requests.RequestException as e:
            raise exceptions.ProxmoxConnectionError(str(e)) from e

    def test(self) -> bool:
        try:
            self.connect()
        except Exception:
            # logger.error('Error testing proxmox: %s', e)
            return False
        return True

    @ensure_connected
    @cached('cluster', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_cluster_info(self, **kwargs: typing.Any) -> types.ClusterInfo:
        return types.ClusterInfo.from_dict(self._get('cluster/status'))

    @ensure_connected
    def get_next_vmid(self) -> int:
        return int(self._get('cluster/nextid')['data'])

    @ensure_connected
    def is_vmid_available(self, vmid: int) -> bool:
        try:
            self._get(f'cluster/nextid?vmid={vmid}')
        except Exception:  # Not available
            return False
        return True

    @ensure_connected
    @cached('nodeNets', consts.CACHE_DURATION, args=1, kwargs=['node'], key_helper=caching_key_helper)
    def get_node_networks(self, node: str, **kwargs: typing.Any) -> typing.Any:
        return self._get(f'nodes/{node}/network', node=node)['data']

    # pylint: disable=unused-argument
    @ensure_connected
    @cached('nodeGpuDevices', consts.CACHE_DURATION_LONG, key_helper=caching_key_helper)
    def list_node_gpu_devices(self, node: str, **kwargs: typing.Any) -> list[str]:
        return [
            device['id']
            for device in self._get(f'nodes/{node}/hardware/pci', node=node)['data']
            if device.get('mdev')
        ]

    @ensure_connected
    def list_node_vgpus(self, node: str, **kwargs: typing.Any) -> list[types.VGPUInfo]:
        return [
            types.VGPUInfo.from_dict(gpu)
            for device in self.list_node_gpu_devices(node)
            for gpu in self._get(f'nodes/{node}/hardware/pci/{device}/mdev', node=node)['data']
        ]

    @ensure_connected
    def node_has_vgpus_available(
        self, node: str, vgpu_type: typing.Optional[str], **kwargs: typing.Any
    ) -> bool:
        return any(
            gpu.available and (vgpu_type is None or gpu.type == vgpu_type) for gpu in self.list_node_vgpus(node)
        )

    @ensure_connected
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

    @ensure_connected
    def clone_vm(
        self,
        vmid: int,
        new_vmid: int,
        name: str,
        description: typing.Optional[str],
        as_linked_clone: bool,
        use_node: typing.Optional[str] = None,
        use_storage: typing.Optional[str] = None,
        use_pool: typing.Optional[str] = None,
        must_have_vgpus: typing.Optional[bool] = None,
    ) -> types.VmCreationResult:
        vmInfo = self.get_vm_info(vmid)

        src_node = vmInfo.node

        if not use_node:
            logger.debug('Selecting best node')
            # If storage is not shared, must be done on same as origin
            if use_storage and self.get_storage_info(use_storage, vmInfo.node).shared:
                node = self.get_best_node_for_vm(
                    min_memory=-1, must_have_vgpus=must_have_vgpus, mdev_type=vmInfo.vgpu_type
                )
                if node is None:
                    raise exceptions.ProxmoxError(
                        f'No switable node available for new vm {name} on Proxmox (check memory and VGPUS, space...)'
                    )
                use_node = node.name
            else:
                use_node = src_node

        # Check if mustHaveVGPUS is compatible with the node
        if must_have_vgpus is not None and must_have_vgpus != bool(self.list_node_gpu_devices(use_node)):
            raise exceptions.ProxmoxNoGPUError(f'Node "{use_node}" does not have VGPUS and they are required')

        if self.node_has_vgpus_available(use_node, vmInfo.vgpu_type):
            raise exceptions.ProxmoxNoGPUError(
                f'Node "{use_node}" does not have free VGPUS of type {vmInfo.vgpu_type} (requred by VM {vmInfo.name})'
            )

        # From normal vm, disable "linked cloning"
        if as_linked_clone and not vmInfo.template:
            as_linked_clone = False

        params: list[tuple[str, str]] = [
            ('newid', str(new_vmid)),
            ('name', name),
            ('target', use_node),
            ('full', str(int(not as_linked_clone))),
        ]

        if description:
            params.append(('description', description))

        if use_storage and as_linked_clone is False:
            params.append(('storage', use_storage))

        if use_pool:
            params.append(('pool', use_pool))

        if as_linked_clone is False:
            params.append(('format', 'qcow2'))  # Ensure clone for templates is on qcow2 format

        logger.debug('PARAMS: %s', params)

        return types.VmCreationResult(
            node=use_node,
            vmid=new_vmid,
            upid=types.UPID.from_dict(
                self._post(f'nodes/{src_node}/qemu/{vmid}/clone', data=params, node=src_node)
            ),
        )

    @ensure_connected
    @cached('hagrps', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def list_ha_groups(self, **kwargs: typing.Any) -> list[str]:
        return [g['group'] for g in self._get('cluster/ha/groups')['data']]

    @ensure_connected
    def enable_vm_ha(self, vmid: int, started: bool = False, group: typing.Optional[str] = None) -> None:
        """
        Enable high availability for a virtual machine.

        Args:
            vmid (int): The ID of the virtual machine.
            started (bool, optional): Whether the virtual machine should be started. Defaults to False.
            group (str, optional): The group to which the virtual machine belongs. Defaults to None.
        """
        self._post(
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

    @ensure_connected
    def disable_vm_ha(self, vmid: int) -> None:
        try:
            self._delete(f'cluster/ha/resources/vm%3A{vmid}')
        except Exception:
            logger.exception('removeFromHA')

    @ensure_connected
    def set_vm_protection(self, vmid: int, node: typing.Optional[str] = None, protection: bool = False) -> None:
        params: list[tuple[str, str]] = [
            ('protection', str(int(protection))),
        ]
        node = node or self.get_vm_info(vmid).node
        self._post(f'nodes/{node}/qemu/{vmid}/config', data=params, node=node)

    @ensure_connected
    def get_guest_ip_address(
        self, vmid: int, node: typing.Optional[str], ip_version: typing.Literal['4', '6', ''] = ''
    ) -> str:
        """Returns the guest ip address of the specified machine"""
        try:
            node = node or self.get_vm_info(vmid).node
            ifaces_list: list[dict[str, typing.Any]] = self._get(
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

    @ensure_connected
    def delete_vm(self, vmid: int, node: typing.Optional[str] = None, purge: bool = True) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self._delete(f'nodes/{node}/qemu/{vmid}?purge=1', node=node))

    @ensure_connected
    def list_snapshots(self, vmid: int, node: typing.Optional[str] = None) -> list[types.SnapshotInfo]:
        node = node or self.get_vm_info(vmid).node
        try:
            return [
                types.SnapshotInfo.from_dict(s)
                for s in self._get(f'nodes/{node}/qemu/{vmid}/snapshot', node=node)['data']
            ]
        except Exception:
            return []  # If we can't get snapshots, just return empty list

    @ensure_connected
    @cached('snapshots', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def supports_snapshot(self, vmid: int, node: typing.Optional[str] = None) -> bool:
        # If machine uses tpm, snapshots are not supported
        return not self.get_vm_config(vmid, node).tpmstate0

    @ensure_connected
    def create_snapshot(
        self,
        vmid: int,
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
        params.append(('snapname', name or ''))
        return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/snapshot', data=params, node=node))

    @ensure_connected
    def remove_snapshot(
        self, vmid: int, node: 'str|None' = None, name: typing.Optional[str] = None
    ) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        if name is None:
            raise exceptions.ProxmoxError('Snapshot name is required')
        return types.UPID.from_dict(self._delete(f'nodes/{node}/qemu/{vmid}/snapshot/{name}', node=node))

    @ensure_connected
    def restore_snapshot(
        self, vmid: int, node: 'str|None' = None, name: typing.Optional[str] = None
    ) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        if name is None:
            raise exceptions.ProxmoxError('Snapshot name is required')
        return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/snapshot/{name}/rollback', node=node))

    @ensure_connected
    def get_task(self, node: str, upid: str) -> types.TaskStatus:
        return types.TaskStatus.from_dict(
            self._get(f'nodes/{node}/tasks/{urllib.parse.quote(upid)}/status', node=node)
        )

    @cached('vms', consts.CACHE_DURATION, key_helper=caching_key_helper)
    @ensure_connected
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

        result: list[types.VMInfo] = []
        for node_name in node_list:
            for vm in self._get(f'nodes/{node_name}/qemu', node=node_name)['data']:
                vm['node'] = node_name
                result.append(types.VMInfo.from_dict(vm))

        return sorted(result, key=lambda x: '{}{}'.format(x.node, x.name))

    @cached('vmip', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    @ensure_connected
    def get_vm_pool_info(
        self, vmid: int, poolid: typing.Optional[str], **kwargs: typing.Any
    ) -> types.VMInfo:
        # try to locate machine in pool
        node = None
        if poolid:
            try:
                for i in self._get(f'pools/{poolid}', node=node)['data']['members']:
                    try:
                        if i['vmid'] == vmid:
                            node = i['node']
                            break
                    except Exception:  # nosec: # If vmid is not present, just try next node
                        pass
            except Exception:  # nosec: # If pool is not present, just use default getVmInfo
                pass

        return self.get_vm_info(vmid, node, **kwargs)

    @ensure_connected
    @cached('vmin', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    def get_vm_info(
        self, vmid: int, node: typing.Optional[str] = None, **kwargs: typing.Any
    ) -> types.VMInfo:
        nodes = [types.Node(node, False, False, 0, '', '', '')] if node else self.get_cluster_info().nodes
        any_node_is_down = False
        for n in nodes:
            try:
                vm = self._get(f'nodes/{n.name}/qemu/{vmid}/status/current', node=node)['data']
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

    @ensure_connected
    def get_vm_config(
        self, vmid: int, node: typing.Optional[str] = None, **kwargs: typing.Any
    ) -> types.VMConfiguration:
        node = node or self.get_vm_info(vmid).node
        return types.VMConfiguration.from_dict(self._get(f'nodes/{node}/qemu/{vmid}/config', node=node)['data'])

    @ensure_connected
    def set_vm_net_mac(
        self,
        vmid: int,
        mac: str,
        netid: typing.Optional[str] = None,
        node: typing.Optional[str] = None,
    ) -> None:
        node = node or self.get_vm_info(vmid).node
        # First, read current configuration and extract network configuration
        config = self._get(f'nodes/{node}/qemu/{vmid}/config', node=node)['data']
        if netid not in config:
            # Get first network interface (netX where X is a number)
            netid = next((k for k in config if k.startswith('net') and k[3:].isdigit()), None)
        if not netid:
            raise exceptions.ProxmoxError('No network interface found')

        netdata = config[netid]

        # Update mac address, that is the first field <model>=<mac>,<other options>
        netdata = re.sub(r'^([^=]+)=([^,]+),', r'\1={},'.format(mac), netdata)

        logger.debug('Updating mac address for VM %s: %s=%s', vmid, netid, netdata)

        self._post(
            f'nodes/{node}/qemu/{vmid}/config',
            data=[(netid, netdata)],
            node=node,
        )

    @ensure_connected
    def start_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/status/start', node=node))

    @ensure_connected
    def stop_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/status/stop', node=node))

    @ensure_connected
    def reset_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/status/reset', node=node))

    @ensure_connected
    def suspend_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        # Note: Suspend, in fact, invoques sets the machine state to "paused"
        return self.shutdown_vm(vmid, node)
        # node = node or self.get_machine_info(vmid).node
        # return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/status/suspend', node=node))

    @ensure_connected
    def shutdown_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        # if exitstatus is "OK" or contains "already running", all is fine
        node = node or self.get_vm_info(vmid).node
        return types.UPID.from_dict(self._post(f'nodes/{node}/qemu/{vmid}/status/shutdown', node=node))

    @ensure_connected
    def convert_vm_to_template(self, vmid: int, node: typing.Optional[str] = None) -> None:
        node = node or self.get_vm_info(vmid).node
        self._post(f'nodes/{node}/qemu/{vmid}/template', node=node)
        # Ensure cache is reset for this VM (as it is now a template)
        self.get_vm_info(vmid, force=True)

    # proxmox has a "resume", but start works for suspended vm so we use it
    @ensure_connected
    def resume_vm(self, vmid: int, node: typing.Optional[str] = None) -> types.UPID:
        return self.start_vm(vmid, node)

    @ensure_connected
    @cached('storage', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_storage_info(self, storage: str, node: str, **kwargs: typing.Any) -> types.StorageInfo:
        return types.StorageInfo.from_dict(
            self._get(f'nodes/{node}/storage/{urllib.parse.quote(storage)}/status', node=node)['data']
        )

    @ensure_connected
    @cached('storages', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def list_storages(
        self,
        node: typing.Union[None, str, collections.abc.Iterable[str]] = None,
        content: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> list[types.StorageInfo]:
        """We use a list for storage instead of an iterator, so we can cache it..."""
        nodes: collections.abc.Iterable[str]
        if node is None:
            nodes = [n.name for n in self.get_cluster_info().nodes if n.online]
        elif isinstance(node, str):
            nodes = [node]
        else:
            nodes = node
        params = '' if not content else '?content={}'.format(urllib.parse.quote(content))
        result: list[types.StorageInfo] = []

        for node_name in nodes:
            for storage in self._get(f'nodes/{node_name}/storage{params}', node=node_name)['data']:
                storage['node'] = node_name
                storage['content'] = storage['content'].split(',')
                result.append(types.StorageInfo.from_dict(storage))

        return result

    @ensure_connected
    @cached('nodeStats', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    def get_node_stats(self, **kwargs: typing.Any) -> list[types.NodeStats]:
        return [
            types.NodeStats.from_dict(nodeStat) for nodeStat in self._get('cluster/resources?type=node')['data']
        ]

    @ensure_connected
    @cached('pools', consts.CACHE_DURATION // 6, key_helper=caching_key_helper)
    def list_pools(self, **kwargs: typing.Any) -> list[types.PoolInfo]:
        return [types.PoolInfo.from_dict(poolInfo) for poolInfo in self._get('pools')['data']]

    @ensure_connected
    @cached('pool', consts.CACHE_DURATION, key_helper=caching_key_helper)
    def get_pool_info(
        self, pool_id: str, retrieve_vm_names: bool = False, **kwargs: typing.Any
    ) -> types.PoolInfo:
        pool_info = types.PoolInfo.from_dict(self._get(f'pools/{pool_id}')['data'])
        if retrieve_vm_names:
            for i in range(len(pool_info.members)):
                try:
                    pool_info.members[i].vmname = self.get_vm_info(pool_info.members[i].vmid).name or ''
                except Exception:
                    pool_info.members[i].vmname = f'VM-{pool_info.members[i].vmid}'
        return pool_info

    @ensure_connected
    def get_console_connection(
        self, vmid: int, node: typing.Optional[str] = None
    ) -> typing.Optional[core_types.services.ConsoleConnectionInfo]:
        """
        Gets the connetion info for the specified machine
        """
        node = node or self.get_vm_info(vmid).node
        res: dict[str, typing.Any] = self._post(f'nodes/{node}/qemu/{vmid}/spiceproxy', node=node)['data']
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

    @ensure_connected
    def journal(self, node: str, lastentries: int = 4, **kwargs: typing.Any) -> list[str]:
        try:
            return self._get(f'nodes/{node}/journal?lastentries={lastentries}')['data']
        except Exception:
            return []
