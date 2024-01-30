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
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import services, types, consts
from uds.core.ui import gui
from uds.core.util import validators, fields
from uds.core.util.decorators import cached
from uds.core.util.unique_id_generator import UniqueIDGenerator
from uds.core.util.unique_mac_generator import UniqueMacGenerator

from . import client
from .service import ProxmoxLinkedService
from .service_fixed import ProxmoxFixedService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.module import Module

logger = logging.getLogger(__name__)

MAX_VM_ID: typing.Final[int] = 999999999


class ProxmoxProvider(services.ServiceProvider):
    type_name = _('Proxmox Platform Provider')
    type_type = 'ProxmoxPlatform'
    type_description = _('Proxmox platform service provider')
    icon_file = 'provider.png'

    offers = [ProxmoxLinkedService, ProxmoxFixedService]

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
    def initialize(self, values: 'Module.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._cached_api = None

        if values is not None:
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            logger.debug(self.host.value)

        # All proxmox use same UniqueId generator
        self._vmid_generator = UniqueIDGenerator('vmid', 'proxmox', 'proxmox')

    def test_connection(self) -> bool:
        """
        Test that conection to Proxmox server is fine

        Returns

            True if all went fine, false if id didn't
        """

        return self._api().test()

    def list_machines(self) -> list[client.types.VMInfo]:
        return self._api().list_machines()

    def get_machine_info(self, vmId: int, poolId: typing.Optional[str] = None) -> client.types.VMInfo:
        return self._api().get_machines_pool_info(vmId, poolId, force=True)

    def get_machine_configuration(self, vmId: int) -> client.types.VMConfiguration:
        return self._api().get_machine_configuration(vmId, force=True)

    def get_storage_info(self, storageId: str, node: str) -> client.types.StorageInfo:
        return self._api().get_storage(storageId, node)

    def list_storages(self, node: typing.Optional[str]) -> list[client.types.StorageInfo]:
        return self._api().list_storages(node=node, content='images')

    def list_pools(self) -> list[client.types.PoolInfo]:
        return self._api().list_pools()
    
    def get_pool_info(self, pool_id: str, retrieve_vm_names: bool = False) -> client.types.PoolInfo:
        return self._api().get_pool_info(pool_id, retrieve_vm_names=retrieve_vm_names)

    def create_template(self, vmId: int) -> None:
        return self._api().convertToTemplate(vmId)

    def clone_machine(
        self,
        vmid: int,
        name: str,
        description: typing.Optional[str],
        as_linked_clone: bool,
        target_node: typing.Optional[str] = None,
        target_storage: typing.Optional[str] = None,
        target_pool: typing.Optional[str] = None,
        must_have_vgpus: typing.Optional[bool] = None,
    ) -> client.types.VmCreationResult:
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

    def start_machine(self, vmId: int) -> client.types.UPID:
        return self._api().start_machine(vmId)

    def stop_machine(self, vmid: int) -> client.types.UPID:
        return self._api().stop_machine(vmid)

    def reset_machine(self, vmid: int) -> client.types.UPID:
        return self._api().reset_machine(vmid)

    def suspend_machine(self, vmId: int) -> client.types.UPID:
        return self._api().suspend_machine(vmId)

    def shutdown_machine(self, vmId: int) -> client.types.UPID:
        return self._api().shutdown_machine(vmId)

    def remove_machine(self, vmid: int) -> client.types.UPID:
        return self._api().remove_machine(vmid)

    def get_task_info(self, node: str, upid: str) -> client.types.TaskStatus:
        return self._api().get_task(node, upid)

    def enable_ha(self, vmId: int, started: bool = False, group: typing.Optional[str] = None) -> None:
        self._api().enable_machine_ha(vmId, started, group)

    def set_machine_mac(self, vmId: int, macAddress: str) -> None:
        self._api().set_machine_ha(vmId, macAddress)

    def disable_ha(self, vmid: int) -> None:
        self._api().disable_machine_ha(vmid)

    def set_protection(self, vmId: int, node: typing.Optional[str] = None, protection: bool = False) -> None:
        self._api().set_protection(vmId, node, protection)

    def list_ha_groups(self) -> list[str]:
        return self._api().list_ha_groups()

    def get_console_connection(
        self, machineId: str
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
        return self._api().get_console_connection(machineId)

    def get_new_vmid(self) -> int:
        while True:  # look for an unused VmId
            vmid = self._vmid_generator.get(self.start_vmid.as_int(), MAX_VM_ID)
            if self._api().is_vmid_available(vmid):
                return vmid
            # All assigned VMId will be left as unusable on UDS until released by time (3 years)
            # This is not a problem at all, in the rare case that a machine id is released from uds db
            # if it exists when we try to create a new one, we will simply try to get another one

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_available(self) -> bool:
        return self._api().test()

    def get_macs_range(self) -> str:
        return self.macs_range.value

    @staticmethod
    def test(env: 'Environment', data: 'Module.ValuesType') -> list[typing.Any]:
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
            return [True, 'Test successfully passed']

        return [False, _("Connection failed. Check connection params")]
