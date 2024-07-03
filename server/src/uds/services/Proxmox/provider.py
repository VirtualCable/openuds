#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import services, types, consts
from uds.core.ui import gui
from uds.core.util import validators, fields
from uds.core.util.decorators import cached
from uds.core.util.unique_id_generator import UniqueIDGenerator

from .proxmox import client, types as prox_types, exceptions as prox_exceptions
from .service_linked import ProxmoxServiceLinked
from .service_fixed import ProxmoxServiceFixed

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import environment

logger = logging.getLogger(__name__)

MAX_VMID: typing.Final[int] = 999999999


def cache_key_helper(self: 'ProxmoxProvider') -> str:
    """
    Helper function to generate cache keys for the ProxmoxProvider class
    """
    return f'{self.host.value}-{self.port.as_int()}'


class ProxmoxProvider(services.ServiceProvider):
    type_name = _('Proxmox Platform Provider')
    type_type = 'ProxmoxPlatform'
    type_description = _('Proxmox platform service provider')
    icon_file = 'provider.png'

    offers = [ProxmoxServiceLinked, ProxmoxServiceFixed]

    host = gui.TextField(
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('Proxmox Server IP or Hostname'),
        required=True,
    )
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        order=2,
        tooltip=_('Proxmox API port (default is 8006)'),
        required=True,
        default=8006,
    )

    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=3,
        tooltip=_('User with valid privileges on Proxmox, (use "user@authenticator" form)'),
        required=True,
        default='root@pam',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=4,
        tooltip=_('Password of the user of Proxmox'),
        required=True,
    )

    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field()

    start_vmid = gui.NumericField(
        length=3,
        label=_('Starting VmId'),
        default=10000,
        min_value=10000,
        max_value=100000,
        order=91,
        tooltip=_('Starting machine id on proxmox'),
        required=True,
        readonly=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='startVmId',
    )

    macs_range = fields.macs_range_field(default='52:54:00:00:00:00-52:54:00:FF:FF:FF')

    # Own variables
    _cached_api: typing.Optional[client.ProxmoxClient] = None
    _vmid_generator: UniqueIDGenerator

    def _api(self) -> client.ProxmoxClient:
        """
        Returns the connection API object
        """
        if self._cached_api is None:
            self._cached_api = client.ProxmoxClient(
                self.host.value,
                self.port.as_int(),
                self.username.value,
                self.password.value,
                self.timeout.as_int(),
                False,
                self.cache,
            )

        return self._cached_api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._cached_api = None

        if values is not None:
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            logger.debug(self.host.value)

        # All proxmox use same UniqueId generator, even if they are different servers
        self._vmid_generator = UniqueIDGenerator('proxmoxvmid', 'proxmox')

    def test_connection(self) -> bool:
        """
        Test that conection to Proxmox server is fine

        Returns

            True if all went fine, false if id didn't
        """

        return self._api().test()

    def list_machines(self, force: bool = False) -> list[prox_types.VMInfo]:
        return self._api().list_machines(force=force)

    def get_vm_info(self, vmid: int, poolid: typing.Optional[str] = None) -> prox_types.VMInfo:
        return self._api().get_machine_pool_info(vmid, poolid, force=True)

    def get_vm_config(self, vmid: int) -> prox_types.VMConfiguration:
        return self._api().get_machine_configuration(vmid, force=True)

    def get_storage_info(self, storageid: str, node: str, force: bool = False) -> prox_types.StorageInfo:
        return self._api().get_storage(storageid, node, force=force)

    def list_storages(
        self, node: typing.Optional[str] = None, force: bool = False
    ) -> list[prox_types.StorageInfo]:
        return self._api().list_storages(node=node, content='images', force=force)

    def list_pools(self, force: bool = False) -> list[prox_types.PoolInfo]:
        return self._api().list_pools(force=force)

    def get_pool_info(
        self, pool_id: str, retrieve_vm_names: bool = False, force: bool = False
    ) -> prox_types.PoolInfo:
        return self._api().get_pool_info(pool_id, retrieve_vm_names=retrieve_vm_names, force=force)

    def create_template(self, vmid: int) -> None:
        self._api().convert_to_template(vmid)

    def clone_vm(
        self,
        vmid: int,
        name: str,
        description: typing.Optional[str],
        as_linked_clone: bool,
        target_node: typing.Optional[str] = None,
        target_storage: typing.Optional[str] = None,
        target_pool: typing.Optional[str] = None,
        must_have_vgpus: typing.Optional[bool] = None,
    ) -> prox_types.VmCreationResult:
        return self._api().clone_machine(
            vmid,
            self.get_new_vmid(),
            name,
            description,
            as_linked_clone,
            target_node,
            target_storage,
            target_pool,
            must_have_vgpus,
        )

    def start_machine(self, vmid: int) -> prox_types.UPID:
        return self._api().start_machine(vmid)

    def stop_machine(self, vmid: int) -> prox_types.UPID:
        return self._api().stop_machine(vmid)

    def reset_machine(self, vmid: int) -> prox_types.UPID:
        return self._api().reset_machine(vmid)

    def suspend_machine(self, vmId: int) -> prox_types.UPID:
        return self._api().suspend_machine(vmId)

    def shutdown_machine(self, vmid: int) -> prox_types.UPID:
        return self._api().shutdown_machine(vmid)

    def remove_machine(self, vmid: int) -> prox_types.UPID:
        return self._api().remove_machine(vmid)

    def get_task_info(self, node: str, upid: str) -> prox_types.TaskStatus:
        return self._api().get_task(node, upid)

    def enable_machine_ha(self, vmid: int, started: bool = False, group: typing.Optional[str] = None) -> None:
        self._api().enable_machine_ha(vmid, started, group)

    def set_machine_mac(self, vmid: int, macAddress: str) -> None:
        self._api().set_machine_mac(vmid, macAddress)

    def disable_machine_ha(self, vmid: int) -> None:
        self._api().disable_machine_ha(vmid)

    def set_protection(self, vmid: int, node: typing.Optional[str] = None, protection: bool = False) -> None:
        self._api().set_protection(vmid, node, protection)

    def list_ha_groups(self) -> list[str]:
        return self._api().list_ha_groups()

    def get_console_connection(
        self,
        vmid: str,
        node: typing.Optional[str] = None,
    ) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self._api().get_console_connection(int(vmid), node)

    def get_new_vmid(self) -> int:
        MAX_RETRIES: typing.Final[int] = 512  # So we don't loop forever, just in case...
        vmid = 0
        for _ in range(MAX_RETRIES):
            vmid = self._vmid_generator.get(self.start_vmid.as_int(), MAX_VMID)
            if self._api().is_vmid_available(vmid):
                return vmid
            # All assigned vmid will be left as unusable on UDS until released by time (3 years)
            # This is not a problem at all, in the rare case that a machine id is released from uds db
            # if it exists when we try to create a new one, we will simply try to get another one
        raise prox_exceptions.ProxmoxError(f'Could not get a new vmid!!: last tried {vmid}')

    def get_guest_ip_address(self, vmid: int, node: typing.Optional[str] = None, ip_version: typing.Literal['4', '6', ''] = '') -> str:
        return self._api().get_guest_ip_address(vmid, node, ip_version)

    def supports_snapshot(self, vmid: int, node: typing.Optional[str] = None) -> bool:
        return self._api().supports_snapshot(vmid, node)

    def get_current_snapshot(
        self, vmid: int, node: typing.Optional[str] = None
    ) -> typing.Optional[prox_types.SnapshotInfo]:
        return (
            sorted(
                filter(lambda x: x.snaptime, self._api().list_snapshots(vmid, node)),
                key=lambda x: x.snaptime or 0,
                reverse=True,
            )
            + [None]
        )[0]

    def create_snapshot(
        self,
        vmid: int,
        node: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> prox_types.UPID:
        return self._api().create_snapshot(vmid, node, name, description)

    def restore_snapshot(
        self, vmid: int, node: typing.Optional[str] = None, name: typing.Optional[str] = None
    ) -> prox_types.UPID:
        """
        In fact snapshot is not optional, but node is and want to keep the same signature as the api
        """
        return self._api().restore_snapshot(vmid, node, name)

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def is_available(self) -> bool:
        return self._api().test()

    def get_macs_range(self) -> str:
        return self.macs_range.value

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        """
        Test Proxmox Connectivity

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably internacionalizated..

        """
        # try:
        #    # We instantiate the provider, but this may fail...
        #    instance = Provider(env, data)
        #    logger.debug('Methuselah has {0} years and is {1} :-)'
        #                 .format(instance.methAge.value, instance.methAlive.value))
        # except exceptions.ValidationException as e:
        #    # If we say that meth is alive, instantiation will
        #    return [False, str(e)]
        # except Exception as e:
        #    logger.exception("Exception caugth!!!")
        #    return [False, str(e)]
        # return [True, _('Nothing tested, but all went fine..')]
        prox = ProxmoxProvider(env, data)
        if prox.test_connection() is True:
            return types.core.TestResult(True, _('Test passed'))

        return types.core.TestResult(False, _('Connection failed. Check connection params'))
