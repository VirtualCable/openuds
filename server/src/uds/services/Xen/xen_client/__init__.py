# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2023 Virtual Cable S.L.U.
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
import ssl
import xmlrpc.client
import logging
import typing

from uds.core import consts

from uds.core.util.decorators import cached

import XenAPI  # pyright: ignore


logger = logging.getLogger(__name__)

TAG_TEMPLATE = "uds-template"
TAG_MACHINE = "uds-machine"


class XenFault(Exception):
    pass


def cache_key_helper(server_api: 'XenServer') -> str:
    return server_api._url  # pyright: ignore[reportPrivateUsage]


class XenFailure(XenAPI.Failure, XenFault):
    exBadVmPowerState = 'VM_BAD_POWER_STATE'
    exVmMissingPVDrivers = 'VM_MISSING_PV_DRIVERS'
    exHandleInvalid = 'HANDLE_INVALID'
    exHostIsSlave = 'HOST_IS_SLAVE'
    exSRError = 'SR_BACKEND_FAILURE_44'

    def __init__(self, details: typing.Optional[list[typing.Any]] = None):
        details = [] if details is None else details
        super(XenFailure, self).__init__(details)

    def isHandleInvalid(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exHandleInvalid

    def needs_xen_tools(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exVmMissingPVDrivers

    def bad_power_state(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exBadVmPowerState

    def is_slave(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exHostIsSlave

    def as_human_readable(self) -> str:
        try:
            error_list = {
                XenFailure.exBadVmPowerState: 'Machine state is invalid for requested operation (needs {2} and state is {3})',
                XenFailure.exVmMissingPVDrivers: 'Machine needs Xen Server Tools to allow requested operation',
                XenFailure.exHostIsSlave: 'The connected host is an slave, try to connect to {1}',
                XenFailure.exSRError: 'Error on SR: {2}',
                XenFailure.exHandleInvalid: 'Invalid reference to {1}',
            }
            err = error_list.get(typing.cast(typing.Any, self.details[0]), 'Error {0}')

            return err.format(*typing.cast(list[typing.Any], self.details))
        except Exception:
            return 'Unknown exception: {0}'.format(self.details)

    def __str__(self) -> str:
        return self.as_human_readable()


class XenException(XenFault):
    def __init__(self, message: typing.Any):
        XenFault.__init__(self, message)
        logger.debug('Exception create: %s', message)


class XenPowerState:  # pylint: disable=too-few-public-methods
    halted: str = 'Halted'
    running: str = 'Running'
    suspended: str = 'Suspended'
    paused: str = 'Paused'


class XenServer:  # pylint: disable=too-many-public-methods
    _originalHost: str
    _host: str
    _host_backup: str
    _port: str
    _use_ssl: bool
    _verify_ssl: bool
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
        useSSL: bool = False,
        verifySSL: bool = False,
    ):
        self._originalHost = self._host = host
        self._host_backup = host_backup or ''
        self._port = str(port)
        self._use_ssl = bool(useSSL)
        self._verify_ssl = bool(verifySSL)
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

    def check_login(self) -> bool:
        if not self._logged_in:
            self.login(swithc_to_master=True)
        return self._logged_in

    def get_xenapi_property(self, prop: str) -> typing.Any:
        if not self.check_login():
            raise Exception("Can't log in")
        return getattr(self._session.xenapi, prop)

    # Properties to fast access XenApi classes
    @property
    def Async(self) -> typing.Any:
        return self.get_xenapi_property('Async')

    @property
    def task(self) -> typing.Any:
        return self.get_xenapi_property('task')

    @property
    def VM(self) -> typing.Any:
        return self.get_xenapi_property('VM')

    @property
    def SR(self) -> typing.Any:
        return self.get_xenapi_property('SR')

    @property
    def pool(self) -> typing.Any:
        return self.get_xenapi_property('pool')

    @property
    def host(self) -> typing.Any:  # Host
        return self.get_xenapi_property('host')

    @property
    def network(self) -> typing.Any:  # Networks
        return self.get_xenapi_property('network')

    @property
    def VIF(self) -> typing.Any:  # Virtual Interface
        return self.get_xenapi_property('VIF')

    @property
    def VDI(self) -> typing.Any:  # Virtual Disk Image
        return self.get_xenapi_property('VDI')

    @property
    def VBD(self) -> typing.Any:  # Virtual Block Device
        return self.get_xenapi_property('VBD')

    @property
    def VM_guest_metrics(self) -> typing.Any:
        return self.get_xenapi_property('VM_guest_metrics')

    # Properties to access private vars
    # p
    def has_pool(self) -> bool:
        return self.check_login() and bool(self._pool_name)

    @cached(prefix='xen_pool', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_pool_name(self) -> str:
        pool = self.pool.get_all()[0]
        return self.pool.get_name_label(pool)

    # Login/Logout
    def login(self, swithc_to_master: bool = False, backup_checked: bool = False) -> None:
        try:
            # We recalculate here url, because we can "switch host" on any moment
            self._url = self._protocol + self._host + ':' + self._port

            transport = None

            if self._use_ssl:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS)
                if self._verify_ssl is False:
                    context.verify_mode = ssl.CERT_NONE
                else:
                    context.verify_mode = ssl.CERT_REQUIRED
                    context.check_hostname = True
                transport = xmlrpc.client.SafeTransport(context=context)
                logger.debug('Transport: %s', transport)

            self._session = XenAPI.Session(self._url, transport=transport)
            self._session.xenapi.login_with_password(self._username, self._password)
            self._logged_in = True
            self._api_version = self._session.API_version
            self._pool_name = str(self.get_pool_name())
        except (
            XenAPI.Failure
        ) as e:  # XenAPI.Failure: ['HOST_IS_SLAVE', '172.27.0.29'] indicates that this host is an slave of 172.27.0.29, connect to it...
            if swithc_to_master and e.details[0] == 'HOST_IS_SLAVE':
                logger.info(
                    '%s is an Slave, connecting to master at %s',
                    self._host,
                    typing.cast(typing.Any, e.details[1])
                )
                self._host = e.details[1]
                self.login(backup_checked=backup_checked)
            else:
                raise XenFailure(e.details)
        except Exception:
            if self._host == self._host_backup or not self._host_backup or backup_checked:
                logger.exception('Connection to master server is broken and backup connection unavailable.')
                raise
            # Retry connection to backup host
            self._host = self._host_backup
            self.login(backup_checked=True)

    def test(self) -> None:
        self.login(False)

    def logout(self) -> None:
        self._session.logout()
        self._logged_in = False
        self._session = None
        self._pool_name = self._api_version = ''

    def get_host(self) -> str:
        return self._host

    def set_host(self, host: str) -> None:
        self._host = host

    def get_task_info(self, task: str) -> dict[str, typing.Any]:
        progress = 0
        result: typing.Any = None
        destroy_task = False
        try:
            status = self.task.get_status(task)
            logger.debug('Task %s in state %s', task, status)
            if status == 'pending':
                status = 'running'
                progress = int(self.task.get_progress(task) * 100)
            elif status == 'success':
                result = self.task.get_result(task)
                destroy_task = True
            elif status == 'failure':
                result = XenFailure(self.task.get_error_info(task))
                destroy_task = True
        except XenAPI.Failure as e:
            logger.debug('XenServer Failure: %s', typing.cast(str, e.details[0]))
            if e.details[0] == 'HANDLE_INVALID':
                result = None
                status = 'unknown'
                progress = 0
            else:
                destroy_task = True
                result = typing.cast(str, e.details[0])
                status = 'failure'
        except ConnectionError as e:
            logger.debug('Connection error: %s', e)
            result = 'Connection error'
            status = 'failure'
        except Exception as e:
            logger.exception('Unexpected exception!')
            result = str(e)
            status = 'failure'

        # Removes <value></value> if present
        if result and not isinstance(result, XenFailure) and result.startswith('<value>'):
            result = result[7:-8]

        if destroy_task:
            try:
                self.task.destroy(task)
            except Exception as e:
                logger.warning('Destroy task %s returned error %s', task, str(e))

        return {'result': result, 'progress': progress, 'status': str(status), 'connection_error': True}

    @cached(prefix='xen_srs', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_srs(self) -> list[dict[str, typing.Any]]:
        return_list: list[dict[str, typing.Any]] = []
        for srId in self.SR.get_all():
            # Only valid SR shared, non iso
            name_label = self.SR.get_name_label(srId)
            # Skip non valid...
            if self.SR.get_content_type(srId) == 'iso' or self.SR.get_shared(srId) is False or name_label == '':
                continue

            valid = True
            allowed_ops = self.SR.get_allowed_operations(srId)
            for v in ['vdi_create', 'vdi_clone', 'vdi_snapshot', 'vdi_destroy']:
                if v not in allowed_ops:
                    valid = False

            if valid:
                return_list.append(
                    {
                        'id': srId,
                        'name': name_label,
                        'size': XenServer.to_mb(self.SR.get_physical_size(srId)),
                        'used': XenServer.to_mb(self.SR.get_physical_utilisation(srId)),
                    }
                )
        return return_list

    @cached(prefix='xen_sr', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_sr_info(self, srid: str) -> dict[str, typing.Any]:
        return {
            'id': srid,
            'name': self.SR.get_name_label(srid),
            'size': XenServer.to_mb(self.SR.get_physical_size(srid)),
            'used': XenServer.to_mb(self.SR.get_physical_utilisation(srid)),
        }

    @cached(prefix='xen_nets', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_networks(self, **kwargs: typing.Any) -> list[dict[str, typing.Any]]:
        return_list: list[dict[str, typing.Any]] = []
        for netId in self.network.get_all():
            if self.network.get_other_config(netId).get('is_host_internal_management_network', False) is False:
                return_list.append(
                    {
                        'id': netId,
                        'name': self.network.get_name_label(netId),
                    }
                )

        return return_list

    @cached(prefix='xen_net', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_network_info(self, net_id: str) -> dict[str, typing.Any]:
        return {'id': net_id, 'name': self.network.get_name_label(net_id)}

    @cached(prefix='xen_vms', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_machines(self) -> list[dict[str, typing.Any]]:
        return_list: list[dict[str, typing.Any]] = []
        try:
            vms = self.VM.get_all()
            for vm in vms:
                try:
                    # if self.VM.get_is_a_template(vm):  #  Sample set_tags, easy..
                    #     self.VM.set_tags(vm, ['template'])
                    #     continue
                    if self.VM.get_is_control_domain(vm) or self.VM.get_is_a_template(vm):
                        continue

                    return_list.append({'id': vm, 'name': self.VM.get_name_label(vm)})
                except Exception as e:
                    logger.warning('VM %s returned error %s', vm, str(e))
                    continue
            return return_list
        except XenAPI.Failure as e:
            raise XenFailure(e.details)
        except Exception as e:
            raise XenException(str(e))

    def get_machine_power_state(self, vmId: str) -> str:
        try:
            power_state = self.VM.get_power_state(vmId)
            logger.debug('Power state of %s: %s', vmId, power_state)
            return power_state
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    @cached(prefix='xen_vm', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_machine_info(self, vmid: str, **kwargs: typing.Any) -> dict[str, typing.Any]:
        try:
            return self.VM.get_record(vmid)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    @cached(prefix='xen_vm_f', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_machine_folder(self, vmid: str, **kwargs: typing.Any) -> str:
        try:
            other_config = self.VM.get_other_config(vmid)
            return other_config.get('folder', '')
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def start_machine(self, vmId: str, as_async: bool = True) -> typing.Optional[str]:
        vmState = self.get_machine_power_state(vmId)
        if vmState == XenPowerState.running:
            return None  # Already powered on

        if vmState == XenPowerState.suspended:
            return self.resume_machine(vmId, as_async)
        return (self.Async if as_async else self).VM.start(vmId, False, False)

    def stop_machine(self, vmid: str, as_async: bool = True) -> typing.Optional[str]:
        vmState = self.get_machine_power_state(vmid)
        if vmState in (XenPowerState.suspended, XenPowerState.halted):
            return None  # Already powered off
        return (self.Async if as_async else self).VM.hard_shutdown(vmid)

    def reset_machine(self, vmid: str, as_async: bool = True) -> typing.Optional[str]:
        vmState = self.get_machine_power_state(vmid)
        if vmState in (XenPowerState.suspended, XenPowerState.halted):
            return None  # Already powered off, cannot reboot
        return (self.Async if as_async else self).VM.hard_reboot(vmid)

    def can_suspend_machine(self, vmid: str) -> bool:
        operations = self.VM.get_allowed_operations(vmid)
        logger.debug('Operations: %s', operations)
        return 'suspend' in operations

    def suspend_machine(self, vmid: str, as_async: bool = True) -> typing.Optional[str]:
        vm_state = self.get_machine_power_state(vmid)
        if vm_state == XenPowerState.suspended:
            return None
        return (self.Async if as_async else self).VM.suspend(vmid)

    def resume_machine(self, vmid: str, as_async: bool = True) -> typing.Optional[str]:
        vm_state = self.get_machine_power_state(vmid)
        if vm_state != XenPowerState.suspended:
            return None
        return (self.Async if as_async else self).VM.resume(vmid, False, False)

    def shutdown_machine(self, vmid: str, as_async: bool = True) -> typing.Optional[str]:
        vm_state = self.get_machine_power_state(vmid)
        if vm_state in (XenPowerState.suspended, XenPowerState.halted):
            return None
        return (self.Async if as_async else self).VM.clean_shutdown(vmid)

    def clone_machine(self, vmId: str, target_name: str, target_sr: typing.Optional[str] = None) -> str:
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
        """
        logger.debug('Cloning VM %s to %s on sr %s', vmId, target_name, target_sr)
        operations = self.VM.get_allowed_operations(vmId)
        logger.debug('Allowed operations: %s', operations)

        try:
            if target_sr:
                if 'copy' not in operations:
                    raise XenException('Copy is not supported for this machine (maybe it\'s powered on?)')
                task = self.Async.VM.copy(vmId, target_name, target_sr)
            else:
                if 'clone' not in operations:
                    raise XenException('Clone is not supported for this machine (maybe it\'s powered on?)')
                task = self.Async.VM.clone(vmId, target_name)
            return task
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def remove_machine(self, vmid: str) -> None:
        logger.debug('Removing machine')
        vdis_to_delete: list[str] = []
        for vdb in self.VM.get_VBDs(vmid):
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
        self.VM.destroy(vmid)
        for vdi in vdis_to_delete:
            self.VDI.destroy(vdi)

    def configure_machine(
        self,
        vmid: str,
        mac: typing.Optional[dict[str, str]] = None,
        memory: typing.Optional[typing.Union[str, int]] = None,
    ) -> None:
        """
        Optional args:
            mac = { 'network': netId, 'mac': mac }
            memory = MEM in MB, minimal is 128

        Mac address should be in the range 02:xx:xx:xx:xx (recommended, but not a "have to")
        """

        # If requested mac address change
        try:
            if mac is not None:
                all_VIFs: list[str] = self.VM.get_VIFs(vmid)
                if not all_VIFs:
                    raise XenException('No Network interfaces found!')
                found = (all_VIFs[0], self.VIF.get_record(all_VIFs[0]))
                for vifId in all_VIFs:
                    vif = self.VIF.get_record(vifId)
                    logger.info('VIF: %s', vif)

                    if vif['network'] == mac['network']:
                        found = (vifId, vif)
                        break

                logger.debug('Found VIF: %s', found[1])
                vifId, vif = found
                self.VIF.destroy(vifId)

                vif['MAC'] = mac['mac']
                vif['network'] = mac['network']
                vif['MAC_autogenerated'] = False
                self.VIF.create(vif)

            # If requested memory change
            if memory:
                logger.debug('Setting up memory to %s MB', memory)
                # Convert memory to MB
                memory = str(int(memory) * 1024 * 1024)
                self.VM.set_memory_limits(vmid, memory, memory, memory, memory)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def get_first_ip(
        self, vmid: str, ip_type: typing.Optional[typing.Union[typing.Literal['4'], typing.Literal['6']]] = None
    ) -> str:
        """Returns the first IP of the machine, or '' if not found"""
        try:
            guest_metrics = self.VM_guest_metrics.get_record(self.VM.get_guest_metrics(vmid))
            networks = guest_metrics.get('networks', {})
            # Networks has this format:
            # {'0/ip': '172.27.242.218',
            #  '0/ipv4/0': '172.27.242.218',
            #  '0/ipv6/1': 'fe80::a496:4ff:feca:404d',
            #  '0/ipv6/0': '2a0c:5a81:2304:8100:a496:4ff:feca:404d'}
            if ip_type != '6':
                if '0/ip' in networks:
                    return networks['0/ip']

            for net_name in sorted(networks.keys()):
                if ip_type is None or f'/ipv{ip_type}/' in net_name:
                    return networks[net_name]
            return ''
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def get_first_mac(self, vmid: str) -> str:
        """Returns the first MAC of the machine, or '' if not found"""
        try:
            vifs = self.VM.get_VIFs(vmid)
            if not vifs:
                return ''
            vif = self.VIF.get_record(vifs[0])
            return vif['MAC']
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def provision_machine(self, vmid: str, as_async: bool = True) -> str:
        tags = self.VM.get_tags(vmid)
        try:
            del tags[tags.index(TAG_TEMPLATE)]
        except Exception:  # nosec: ignored, maybe tag is not pressent
            pass
        tags.append(TAG_MACHINE)
        self.VM.set_tags(vmid, tags)

        if as_async:
            return self.Async.VM.provision(vmid)
        return self.VM.provision(vmid)

    def create_snapshot(self, vmid: str, name: str) -> str:
        try:
            return self.Async.VM.snapshot(vmid, name)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def restore_snapshot(self, snapshot_id: str) -> str:
        try:
            return self.Async.VM.snapshot_revert(snapshot_id)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def remove_snapshot(self, snapshot_id: str) -> str:
        try:
            return self.Async.VM.destroy(snapshot_id)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    @cached(prefix='xen_snapshots', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_snapshots(self, vmid: str, full_info: bool = False, **kwargs: typing.Any) -> list[dict[str, typing.Any]]:
        """Returns a list of snapshots for the specified VM, sorted by snapshot_time in descending order.
        (That is, the most recent snapshot is first in the list.)

         Args:
             vmid: The VM for which to list snapshots.
             full_info: If True, return full information about each snapshot. If False, return only the snapshot ID

         Returns:
             A list of dictionaries, each containing the following keys:
                 id: The snapshot ID.
                 name: The snapshot name.
        """
        try:
            snapshots = self.VM.get_snapshots(vmid)
            if not full_info:
                return [{'id': snapshot for snapshot in snapshots}]
            # Return full info, thatis, name, id and snapshot_time
            return_list: list[dict[str, typing.Any]] = []
            for snapshot in snapshots:
                return_list.append(
                    {
                        'id': snapshot,
                        'name': self.VM.get_name_label(snapshot),
                        'snapshot_time': self.VM.get_snapshot_time(snapshot),
                    }
                )
            return sorted(return_list, key=lambda x: x['snapshot_time'], reverse=True)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    @cached(prefix='xen_folders', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_folders(self, **kwargs: typing.Any) -> list[str]:
        """list "Folders" from the "Organizations View" of the XenServer

        Returns:
            A list of 'folders' (organizations, str) in the XenServer
        """
        folders: set[str] = set('/')  # Add root folder for machines without folder
        for vm in self.list_machines():
            other_config = self.VM.get_other_config(vm['id'])
            folder: typing.Optional[str] = other_config.get('folder')
            if folder:
                folders.add(folder)
        return sorted(folders)

    def get_machines_from_folder(
        self, folder: str, retrieve_names: bool = False
    ) -> list[dict[str, typing.Any]]:
        result_list: list[dict[str, typing.Any]] = []
        for vm in self.list_machines():
            other_config = self.VM.get_other_config(vm['id'])
            if other_config.get('folder', '/') == folder:
                if retrieve_names:
                    vm['name'] = self.VM.get_name_label(vm['id'])
                result_list.append(vm)
        return result_list

    def convert_to_template(self, vmId: str, shadowMultiplier: int = 4) -> None:
        try:
            operations = self.VM.get_allowed_operations(vmId)
            logger.debug('Allowed operations: %s', operations)
            if 'make_into_template' not in operations:
                raise XenException('Convert in template is not supported for this machine')
            self.VM.set_is_a_template(vmId, True)

            # Apply that is an "UDS Template" taggint it
            tags = self.VM.get_tags(vmId)
            try:
                del tags[tags.index(TAG_MACHINE)]
            except Exception:  # nosec: ignored, maybe tag is not pressent
                pass
            tags.append(TAG_TEMPLATE)
            self.VM.set_tags(vmId, tags)

            # Set multiplier
            try:
                self.VM.set_HVM_shadow_multiplier(vmId, float(shadowMultiplier))
            except Exception:  # nosec: Can't set shadowMultiplier, nothing happens
                pass
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def remove_template(self, templateId: str) -> None:
        self.remove_machine(templateId)

    def start_deploy_from_template(self, templateId: str, target_name: str) -> str:
        """
        After cloning template, we must deploy the VM so it's a full usable VM
        """
        return self.clone_machine(templateId, target_name)
