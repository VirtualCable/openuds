# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2024 Virtual Cable S.L.U.
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

import xmlrpc.client
import logging
import typing

from uds.core import consts
from uds.core.util.decorators import cached
from uds.core.util import security

import XenAPI  # pyright: ignore

from . import types as xen_types
from . import exceptions

logger = logging.getLogger(__name__)

TAG_TEMPLATE = "uds-template"
TAG_MACHINE = "uds-machine"


def cache_key_helper(server_api: 'XenClient') -> str:
    return server_api._url  # pyright: ignore[reportPrivateUsage]


class SafeTimeoutTransport(xmlrpc.client.SafeTransport):
    _timeout: int = 0

    def set_timeout(self, timeout: int) -> None:
        self._timeout = timeout

    def make_connection(self, host: typing.Any) -> typing.Any:
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class TimeoutTransport(xmlrpc.client.Transport):
    _timeout: int = 0

    def set_timeout(self, timeout: int) -> None:
        self._timeout = timeout

    def make_connection(self, host: typing.Any) -> typing.Any:
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class XenClient:  # pylint: disable=too-many-public-methods
    _originalHost: str
    _host: str
    _host_backup: str
    _port: str
    _use_ssl: bool
    _verify_ssl: bool
    _timeout: int
    _protocol: str
    _url: str
    _logged_in: bool
    _username: str
    _password: str
    _session: typing.Any
    _pool_name: str
    _api_version: str

    def __init__(
        self,
        host: str,
        host_backup: str,
        port: int,
        username: str,
        password: str,
        ssl: bool = True,
        verify_ssl: bool = False,
        timeout: int = 10,
    ):
        self._originalHost = self._host = host
        self._host_backup = host_backup or ''
        self._port = str(port)
        self._use_ssl = bool(ssl)
        self._verify_ssl = bool(verify_ssl)
        self._timeout = timeout
        self._protocol = 'http' + ('s' if self._use_ssl else '') + '://'
        self._url = ''
        self._logged_in = False
        self._username = username
        self._password = password
        self._session = None
        self._pool_name = self._api_version = ''

    @staticmethod
    def to_mb(number: typing.Union[str, int]) -> int:
        return int(number) // (1024 * 1024)

    # Properties to access private vars
    # p
    def _get_xenapi_property(self, prop: str) -> typing.Any:
        if not self.check_login():
            raise Exception("Can't login")
        return getattr(self._session.xenapi, prop)

    # Properties to fast access XenApi classes
    @property
    def Async(self) -> typing.Any:
        return self._get_xenapi_property('Async')

    @property
    def task(self) -> typing.Any:
        return self._get_xenapi_property('task')

    @property
    def VM(self) -> typing.Any:
        return self._get_xenapi_property('VM')

    @property
    def SR(self) -> typing.Any:
        return self._get_xenapi_property('SR')

    @property
    def pool(self) -> typing.Any:
        return self._get_xenapi_property('pool')

    @property
    def host(self) -> typing.Any:  # Host
        return self._get_xenapi_property('host')

    @property
    def network(self) -> typing.Any:  # Networks
        return self._get_xenapi_property('network')

    @property
    def VIF(self) -> typing.Any:  # Virtual Interface
        return self._get_xenapi_property('VIF')

    @property
    def VDI(self) -> typing.Any:  # Virtual Disk Image
        return self._get_xenapi_property('VDI')

    @property
    def VBD(self) -> typing.Any:  # Virtual Block Device
        return self._get_xenapi_property('VBD')

    @property
    def VM_guest_metrics(self) -> typing.Any:
        return self._get_xenapi_property('VM_guest_metrics')

    def has_pool(self) -> bool:
        self.check_login()
        return bool(self._pool_name)

    @cached(prefix='xen_pool', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_pool_name(self, **kwargs: typing.Any) -> str:
        try:
            pool = self.pool.get_all()[0]
            return self.pool.get_name_label(pool)
        except Exception:
            return ''

    # Login/Logout
    def login(self, switch_to_master: bool = False, backup_checked: bool = False) -> None:
        try:
            # We recalculate here url, because we can "switch host" on any moment
            self._url = self._protocol + self._host + ':' + self._port

            transport = None

            if self._use_ssl:
                context = security.create_client_sslcontext(verify=self._verify_ssl)
                transport = SafeTimeoutTransport(context=context)
                transport.set_timeout(self._timeout)
                logger.debug('Transport: %s', transport)
            else:
                transport = TimeoutTransport()
                transport.set_timeout(self._timeout)
                logger.debug('Transport: %s', transport)

            self._session = XenAPI.Session(self._url, transport=transport)
            self._session.xenapi.login_with_password(
                self._username, self._password, '', 'UDS XenServer Connector'
            )
            self._logged_in = True
            self._api_version = self._session.API_version
            self._pool_name = self.get_pool_name(force=True)
        except (
            XenAPI.Failure
        ) as e:  # XenAPI.Failure: ['HOST_IS_SLAVE', '172.27.0.29'] indicates that this host is an slave of 172.27.0.29, connect to it...
            if switch_to_master and e.details[0] == 'HOST_IS_SLAVE':
                logger.info(
                    '%s is an Slave, connecting to master at %s',
                    self._host,
                    typing.cast(typing.Any, e.details[1]),
                )
                self._host = e.details[1]
                self.login(backup_checked=backup_checked)
            else:
                raise exceptions.XenFailure(e.details)
        except Exception:
            if self._host == self._host_backup or not self._host_backup or backup_checked:
                logger.exception('Connection to master server is broken and backup connection unavailable.')
                raise
            # Retry connection to backup host
            self._host = self._host_backup
            self.login(backup_checked=True)

    def logout(self) -> None:
        if self._logged_in:
            try:
                self._session.xenapi.logout()
                self._session.transport.close()
            except Exception as e:
                logger.warning('Error logging out: %s', e)

        self._logged_in = False
        self._session = None
        self._pool_name = self._api_version = ''

    def check_login(self) -> bool:
        if not self._logged_in:
            self.login(switch_to_master=True)
        return self._logged_in

    def test(self) -> None:
        self.login(False)

    def get_task_info(self, task_opaque_ref: str) -> xen_types.TaskInfo:
        try:
            with exceptions.translator():
                task_info = xen_types.TaskInfo.from_dict(self.task.get_record(task_opaque_ref), task_opaque_ref)
        except exceptions.XenNotFoundError:
            task_info = xen_types.TaskInfo.unknown_task(task_opaque_ref)

        return task_info

    @cached(prefix='xen_srs', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def list_srs(self) -> list[xen_types.StorageInfo]:
        return_list: list[xen_types.StorageInfo] = []
        for sr_id, sr_raw in typing.cast(dict[str, typing.Any], self.SR.get_all_records()).items():
            sr = xen_types.StorageInfo.from_dict(sr_raw, sr_id)
            if sr.is_usable():
                return_list.append(sr)

        return return_list

    @cached(prefix='xen_sr', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def get_sr_info(self, sr_opaque_ref: str) -> xen_types.StorageInfo:
        return xen_types.StorageInfo.from_dict(self.SR.get_record(sr_opaque_ref), sr_opaque_ref)

    @cached(prefix='xen_nets', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def list_networks(self, **kwargs: typing.Any) -> list[xen_types.NetworkInfo]:
        return_list: list[xen_types.NetworkInfo] = []
        for netid in self.network.get_all():
            netinfo = xen_types.NetworkInfo.from_dict(self.network.get_record(netid), netid)
            if netinfo.is_host_internal_management_network is False:
                return_list.append(netinfo)

        return return_list

    @cached(prefix='xen_net', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def get_network_info(self, network_opaque_ref: str) -> xen_types.NetworkInfo:
        return xen_types.NetworkInfo.from_dict(self.network.get_record(network_opaque_ref), network_opaque_ref)

    @cached(prefix='xen_vms', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def list_vms(self) -> list[xen_types.VMInfo]:
        return_list: list[xen_types.VMInfo] = []

        try:
            for vm_id, vm_raw in typing.cast(dict[str, typing.Any], self.VM.get_all_records()).items():
                vm = xen_types.VMInfo.from_dict(vm_raw, vm_id)
                if vm.is_usable():
                    return_list.append(vm)
            return return_list
        except XenAPI.Failure as e:
            raise exceptions.XenFailure(e.details)
        except Exception as e:
            raise exceptions.XenException(str(e))

    @cached(prefix='xen_vm', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def get_vm_info(self, vm_opaque_ref: str, **kwargs: typing.Any) -> xen_types.VMInfo:
        return xen_types.VMInfo.from_dict(self.VM.get_record(vm_opaque_ref), vm_opaque_ref)

    @exceptions.catched
    def _start_vm(self, vm_opaque_ref: str, as_async: bool = True) -> str:
        vminfo = self.get_vm_info(vm_opaque_ref, force=True)
        if vminfo.power_state.is_running():
            return ''

        if vminfo.power_state == xen_types.PowerState.SUSPENDED:
            return self._suspend_vm(vm_opaque_ref, as_async)

        return (self.Async if as_async else self).VM.start(vm_opaque_ref, False, False)

    @exceptions.catched
    def _stop_vm(self, vm_opaque_ref: str, as_async: bool = True) -> str:
        vminfo = self.get_vm_info(vm_opaque_ref, force=True)
        if vminfo.power_state.is_stopped():
            return ''

        return (self.Async if as_async else self).VM.hard_shutdown(vm_opaque_ref)

    @exceptions.catched
    def _reset_vm(self, vm_opaque_ref: str, as_async: bool = True) -> str:
        vminfo = self.get_vm_info(vm_opaque_ref, force=True)
        if vminfo.power_state.is_stopped():  # Start it if it's stopped
            return self._start_vm(vm_opaque_ref, as_async)

        return (self.Async if as_async else self).VM.hard_reboot(vm_opaque_ref)

    @exceptions.catched
    def _suspend_vm(self, vm_opaque_ref: str, as_async: bool = True) -> str:
        vminfo = self.get_vm_info(vm_opaque_ref, force=True)
        if vminfo.power_state.is_stopped():
            return ''

        if vminfo.supports_suspend() is False:
            # Shutdown machine if it can't be suspended
            return self._shutdown_vm(vm_opaque_ref, as_async)

        return (self.Async if as_async else self).VM.suspend(vm_opaque_ref)

    @exceptions.catched
    def _resume_vm(self, vm_opaque_ref: str, as_async: bool = True) -> str:
        vminfo = self.get_vm_info(vm_opaque_ref, force=True)
        if vminfo.power_state.is_running():
            return ''

        if vminfo.supports_suspend() is False:
            # Start machine if it can't be resumed
            return self._start_vm(vm_opaque_ref, as_async)

        return (self.Async if as_async else self).VM.resume(vm_opaque_ref, False, False)

    @exceptions.catched
    def _shutdown_vm(self, vm_opaque_ref: str, as_async: bool = True) -> str:
        vminfo = self.get_vm_info(vm_opaque_ref)
        if vminfo.power_state.is_stopped():
            return ''

        if vminfo.supports_clean_shutdown() is False:
            return self._stop_vm(vm_opaque_ref, as_async)

        return (self.Async if as_async else self).VM.clean_shutdown(vm_opaque_ref)

    # All operations exceptions processes in its _ counterpart
    # Also, async operations can return '' if not needed to wait for task
    def start_vm(self, vm_opaque_ref: str) -> str:
        return self._start_vm(vm_opaque_ref, True)  # We know it's not None on async

    def start_vm_sync(self, vm_opaque_ref: str) -> None:
        self._start_vm(vm_opaque_ref, False)

    def stop_vm(self, vm_opaque_ref: str) -> str:
        return self._stop_vm(vm_opaque_ref, True)

    def stop_vm_sync(self, vm_opaque_ref: str) -> None:
        self._stop_vm(vm_opaque_ref, False)

    def reset_vm(self, vm_opaque_ref: str) -> str:
        return self._reset_vm(vm_opaque_ref, True)

    def reset_vm_sync(self, vm_opaque_ref: str) -> None:
        self._reset_vm(vm_opaque_ref, False)

    def suspend_vm(self, vm_opaque_ref: str) -> str:
        return self._suspend_vm(vm_opaque_ref, True)

    def suspend_vm_sync(self, vm_opaque_ref: str) -> None:
        self._suspend_vm(vm_opaque_ref, False)

    def resume_vm(self, vm_opaque_ref: str) -> str:
        return self._resume_vm(vm_opaque_ref, True)

    def resume_vm_sync(self, vm_opaque_ref: str) -> None:
        self._resume_vm(vm_opaque_ref, False)

    def shutdown_vm(self, vm_opaque_ref: str) -> str:
        return self._shutdown_vm(vm_opaque_ref, True)

    def shutdown_vm_sync(self, vm_opaque_ref: str) -> None:
        self._shutdown_vm(vm_opaque_ref, False)

    @exceptions.catched
    def clone_vm(self, vm_opaque_ref: str, target_name: str, target_sr: typing.Optional[str] = None) -> str:
        """
        If target_sr is NONE:
            Clones the specified VM, making a new VM.
            Clone automatically exploits the capabilities of the underlying storage repository
            in which the VM's disk images are stored (e.g. Copy on Write).
        Else:
            Copied the specified VM, making a new VM. Unlike clone, copy does not exploits the capabilities
            of the underlying storage repository in which the VM's disk images are stored.
            Instead, copy guarantees that the disk images of the newly created VM will be
            'full disks' - i.e. not part of a CoW chain.
        This function can only be called when the VM is in the Halted State.

        Args:
            vm_opaque_ref: The VM to clone
            target_name: The name of the new VM
            target_sr: The storage repository where the new VM will be stored. If None, the VM will be cloned

        Returns:
            The task id of the operation
        """
        logger.debug('Cloning VM %s to %s on sr %s', vm_opaque_ref, target_name, target_sr)
        operations = self.VM.get_allowed_operations(vm_opaque_ref)
        logger.debug('Allowed operations: %s', operations)

        try:
            if target_sr:
                if 'copy' not in operations:
                    raise exceptions.XenFatalError(
                        'Copy is not supported for this machine (maybe it\'s powered on?)'
                    )
                task = self.Async.VM.copy(vm_opaque_ref, target_name, target_sr)
            else:
                if 'clone' not in operations:
                    raise exceptions.XenFatalError(
                        'Clone is not supported for this machine (maybe it\'s powered on?)'
                    )
                task = self.Async.VM.clone(vm_opaque_ref, target_name)
            return task
        except XenAPI.Failure as e:
            raise exceptions.XenFailure(e.details)

    @exceptions.catched
    def delete_vm(self, vm_opaque_ref: str) -> None:
        logger.debug('Removing machine')
        # VDIS are not automatically deleted, so we must delete them first
        vdis_to_delete: list[str] = []
        for vdb in self.VM.get_VBDs(vm_opaque_ref):
            vdi = ''
            try:
                vdi = self.VBD.get_VDI(vdb)
                if vdi == 'OpaqueRef:NULL':
                    logger.debug('VDB without VDI')
                    continue
                logger.debug('VDI: %s', vdi)
            except Exception:
                logger.exception('Exception getting VDI from VDB')
            if self.VDI.get_read_only(vdi) is True:
                logger.debug('%s is read only, skipping', vdi)
                continue
            logger.debug('VDI to delete: %s', vdi)
            vdis_to_delete.append(vdi)
        self.VM.destroy(vm_opaque_ref)

        for vdi in vdis_to_delete:
            self.VDI.destroy(vdi)

    @exceptions.catched
    def configure_vm(
        self,
        vm_opaque_ref: str,
        *,  # All following args are keyword only
        mac_info: typing.Optional[xen_types.MacTypeSetter] = None,
        memory: typing.Optional[int] = None,
    ) -> None:
        """
        Optional args:
            mac = { 'network': netId, 'mac': mac }
            memory = MEM in MB, minimal is 128

        Mac address should be in the range 02:xx:xx:xx:xx (recommended, but not a "have to")
        """

        # If requested mac address change
        if mac_info is not None:
            vm_vifs: list[str] = self.VM.get_VIFs(vm_opaque_ref)
            if not vm_vifs:
                raise exceptions.XenException('No Network interfaces found!')
            found = (vm_vifs[0], self.VIF.get_record(vm_vifs[0]))
            for vif_id in vm_vifs:
                vif = self.VIF.get_record(vif_id)
                logger.info('VIF: %s', vif)

                if vif['network'] == mac_info['network']:
                    found = (vif_id, vif)
                    break

            logger.debug('Found VIF: %s', found[1])
            vif_id, vif = found
            self.VIF.destroy(vif_id)

            vif['MAC'] = mac_info['mac']
            vif['network'] = mac_info['network']
            vif['MAC_autogenerated'] = False
            self.VIF.create(vif)

        # If requested memory change
        if memory:
            logger.debug('Setting up memory to %s MB', memory)
            # Convert memory to MB
            memory = memory * 1024 * 1024
            self.VM.set_memory_limits(vm_opaque_ref, memory, memory, memory, memory)

    @cached(prefix='xen_folders', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def list_folders(self, **kwargs: typing.Any) -> list[str]:
        """list "Folders" from the "Organizations View" of the XenServer

        Returns:
            A list of 'folders' (organizations, str) in the XenServer
        """
        folders: set[str] = set('/')  # Add root folder for machines without folder
        for vm in self.list_vms():
            if vm.folder:
                folders.add(vm.folder)

        return sorted(folders)

    @exceptions.catched
    def list_vms_in_folder(self, folder: str) -> list[xen_types.VMInfo]:
        """
        List all VMs in a folder (case insensitive)

        Args:
            folder: The folder to list VMs from

        Returns:
            A list of VMs in the specified folder
        """
        folder = folder.upper()
        result_list: list[xen_types.VMInfo] = []
        for vm in self.list_vms():
            if vm.folder.upper() == folder:
                result_list.append(vm)
        return result_list

    @exceptions.catched
    def get_first_ip(
        self,
        vm_opaque_ref: str,
        ip_version: typing.Optional[typing.Union[typing.Literal['4'], typing.Literal['6']]] = None,
    ) -> str:
        """Returns the first IP of the machine, or '' if not found"""
        guest_metric_opaque_ref = self.VM.get_guest_metrics(vm_opaque_ref)
        if guest_metric_opaque_ref == 'OpaqueRef:NULL':
            return ''  # No guest metrics, no IP
        guest_metrics = self.VM_guest_metrics.get_record(guest_metric_opaque_ref)
        networks = guest_metrics.get('networks', {})
        # Networks has this format:
        # {'0/ip': '172.27.242.218',
        #  '0/ipv4/0': '172.27.242.218',
        #  '0/ipv6/1': 'fe80::a496:4ff:feca:404d',
        #  '0/ipv6/0': '2a0c:5a81:2304:8100:a496:4ff:feca:404d'}
        if ip_version != '6':
            if '0/ip' in networks:
                return networks['0/ip']

        for net_name in sorted(networks.keys()):
            if ip_version is None or f'/ipv{ip_version}/' in net_name:
                return networks[net_name]
        return ''

    @exceptions.catched
    def get_first_mac(self, vm_opaque_ref: str) -> str:
        """Returns the first MAC of the machine, or '' if not found"""
        vifs = self.VM.get_VIFs(vm_opaque_ref)
        if not vifs:
            return ''
        vif = self.VIF.get_record(vifs[0])
        return vif['MAC']

    @exceptions.catched
    def create_snapshot(self, vm_opaque_ref: str, name: str) -> str:
        # Ensure VM exists, so it raises an exception if not
        self.get_vm_info(vm_opaque_ref, force=True)
        return self.Async.VM.snapshot(vm_opaque_ref, name)

    @exceptions.catched
    def restore_snapshot(self, snapshot_opaque_ref: str) -> str:
        self.get_vm_info(snapshot_opaque_ref, force=True)
        return self.Async.VM.revert(snapshot_opaque_ref)

    @exceptions.catched
    def delete_snapshot(self, snapshot_opaque_ref: str) -> None:
        # In fact, it's the same as delete_vm
        # VDIs are not automatically deleted, so we must also delete them
        self.delete_vm(snapshot_opaque_ref)

    @cached(prefix='xen_snapshots', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    @exceptions.catched
    def list_snapshots(
        self, vm_opaque_ref: str, full_info: bool = True, **kwargs: typing.Any
    ) -> list[xen_types.VMInfo]:
        """Returns a list of snapshots for the specified VM, sorted by snapshot_time in descending order.
        (That is, the most recent snapshot is first in the list.)

         Args:
             vm_opaque_ref: The VM for which to list snapshots.
             full_info: If True, return full information about each snapshot. If False, return only the snapshot ID

         Returns:
                A list of snapshots for the specified VM, sorted by snapshot_time in descending order.
        """
        snapshots = self.VM.get_snapshots(vm_opaque_ref)

        if not full_info:
            return [xen_types.VMInfo.null(snapshot) for snapshot in snapshots]

        # Return full info, thatis, name, id and snapshot_time
        return sorted(
            [self.get_vm_info(snapshot) for snapshot in snapshots],
            key=lambda x: x.snapshot_time,
            reverse=True,
        )

    @exceptions.catched
    def convert_to_template(self, vm_opaque_ref: str, shadow_multiplier: int = 4) -> None:
        operations = self.VM.get_allowed_operations(vm_opaque_ref)
        logger.debug('Allowed operations: %s', operations)
        if 'make_into_template' not in operations:
            raise exceptions.XenException('Convert in template is not supported for this machine')
        self.VM.set_is_a_template(vm_opaque_ref, True)

        # Apply that is an "UDS Template" taggint it
        tags = self.VM.get_tags(vm_opaque_ref)
        try:
            del tags[tags.index(TAG_MACHINE)]
        except Exception:  # nosec: ignored, maybe tag is not pressent
            pass
        tags.append(TAG_TEMPLATE)
        self.VM.set_tags(vm_opaque_ref, tags)

        # Set multiplier
        try:
            self.VM.set_HVM_shadow_multiplier(vm_opaque_ref, float(shadow_multiplier))
        except Exception:  # nosec: Can't set shadowMultiplier, nothing happens
            pass

    @exceptions.catched
    def provision_vm(self, vm_opaque_ref: str) -> None:
        tags = self.VM.get_tags(vm_opaque_ref)
        try:
            del tags[tags.index(TAG_TEMPLATE)]
        except Exception:  # nosec: ignored, maybe tag is not pressent
            pass
        tags.append(TAG_MACHINE)
        self.VM.set_tags(vm_opaque_ref, tags)

        self.VM.provision(vm_opaque_ref)

    @exceptions.catched
    def delete_template(self, template_opaque_ref: str) -> None:
        # In fact, this is a "delete_vm" operation
        self.delete_vm(template_opaque_ref)

    @exceptions.catched
    def deploy_from_template(self, template_opaque_ref: str, target_name: str) -> str:
        """
        After cloning template, we must deploy the VM so it's a full usable VM
        """
        return self.clone_vm(template_opaque_ref, target_name)
