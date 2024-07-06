#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import services, types
from uds.core.services.generics.fixed.service import FixedService
from uds.core.services.generics.fixed.userservice import FixedUserService
from uds.core.ui import gui

from . import helpers
from .deployment_fixed import ProxmoxUserServiceFixed

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

    from .proxmox import types as prox_types
    from .provider import ProxmoxProvider

logger = logging.getLogger(__name__)


class ProxmoxServiceFixed(FixedService):  # pylint: disable=too-many-public-methods
    """
    Proxmox fixed machines service.
    """

    type_name = _('Proxmox Fixed Machines')
    type_type = 'ProxmoxFixedService'
    type_description = _('Proxmox Services based on fixed machines. Needs qemu agent installed on machines.')
    icon_file = 'service.png'

    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = None
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = ProxmoxUserServiceFixed

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI

    # Gui
    token = FixedService.token

    pool = gui.ChoiceField(
        label=_("Resource Pool"),
        readonly=False,
        order=20,
        fills={
            'callback_name': 'pmFillMachinesFromResource',
            'function': helpers.get_machines,
            'parameters': ['prov_uuid', 'pool'],
        },
        tooltip=_('Resource Pool containing base machines'),
        required=True,
        tab=_('Machines'),
        old_field_name='resourcePool',
    )

    machines = FixedService.machines
    use_snapshots = FixedService.use_snapshots

    prov_uuid = gui.HiddenField(value=None)

    # Uses default FixedService.initialize

    def init_gui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        # Log with call stack
        self.prov_uuid.value = self.provider().get_uuid()

        self.pool.set_choices(
            [gui.choice_item('', _('None'))]
            + [gui.choice_item(p.id, p.id) for p in self.provider().api.list_pools()]
        )

    def provider(self) -> 'ProxmoxProvider':
        return typing.cast('ProxmoxProvider', super().provider())

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def get_vm_info(self, vmid: int) -> 'prox_types.VMInfo':
        return self.provider().api.get_vm_info(vmid, self.pool.value.strip()).validate()
    
    def is_ready(self, vmid: str) -> bool:
        return self.provider().api.get_vm_info(int(vmid)).validate().status.is_running()

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        # Obtain machines names and ids for asignables
        # Only machines that already exists on proxmox and are not already assigned
        vms: dict[int, str] = {}

        for member in self.provider().api.get_pool_info(self.pool.value.strip(), retrieve_vm_names=True).members:
            vms[member.vmid] = member.vmname

        with self._assigned_access() as assigned_vms:
            return [
                gui.choice_item(k, vms[int(k)])
                for k in self.machines.as_list()
                if k not in assigned_vms
                and int(k) in vms  # Only machines not assigned, and that exists on provider will be available
            ]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> types.states.TaskState:
        proxmox_service_instance = typing.cast(ProxmoxUserServiceFixed, userservice_instance)
        with self._assigned_access() as assigned_vms:
            if assignable_id not in assigned_vms:
                assigned_vms.add(assignable_id)
                return proxmox_service_instance.assign(assignable_id)

        return proxmox_service_instance.error('VM not available!')

    def snapshot_creation(self, userservice_instance: FixedUserService) -> None:
        userservice_instance = typing.cast(ProxmoxUserServiceFixed, userservice_instance)
        if self.use_snapshots.as_bool():
            vmid = int(userservice_instance._vmid)
            logger.debug('Using snapshots')
            # If no snapshot exists for this vm, try to create one for it on background
            # Lauch an snapshot. We will not wait for it to finish, but instead let it run "as is"
            try:
                if not self.provider().api.get_current_vm_snapshot(vmid):
                    logger.debug('No current snapshot')
                    self.provider().api.create_snapshot(
                        vmid,
                        name='UDS Snapshot',
                    )
            except Exception as e:
                self.do_log(types.log.LogLevel.WARNING, 'Could not create SNAPSHOT for this VM. ({})'.format(e))

    def snapshot_recovery(self, userservice_instance: FixedUserService) -> None:
        userservice_instance = typing.cast(ProxmoxUserServiceFixed, userservice_instance)
        if self.use_snapshots.as_bool():
            vmid = int(userservice_instance._vmid)
            try:
                # try to revert to snapshot
                snapshot = self.provider().api.get_current_vm_snapshot(vmid)
                if snapshot:
                    userservice_instance._store_task(
                        self.provider().api.restore_snapshot(vmid, name=snapshot.name)
                    )
            except Exception as e:
                self.do_log(types.log.LogLevel.WARNING, 'Could not restore SNAPSHOT for this VM. ({})'.format(e))

    def get_and_assign(self) -> str:
        found_vmid: typing.Optional[str] = None
        try:
            with self._assigned_access() as assigned_vms:
                for checking_vmid in self.machines.as_list():
                    if checking_vmid not in assigned_vms:  # Not already assigned
                        try:
                            # Invoke to check it exists, do not need to store the result
                            self.provider().api.get_vm_pool_info(int(checking_vmid), self.pool.value.strip())
                            found_vmid = checking_vmid
                            break
                        except Exception:  # Notifies on log, but skipt it
                            self.provider().do_log(
                                types.log.LogLevel.WARNING, 'Machine {} not accesible'.format(found_vmid)
                            )
                            logger.warning(
                                'The service has machines that cannot be checked on proxmox (connection error or machine has been deleted): %s',
                                found_vmid,
                            )

                if found_vmid:
                    assigned_vms.add(found_vmid)
        except Exception as e:  #
            logger.debug('Error getting machine: %s', e)
            raise Exception('No machine available')

        if not found_vmid:
            raise Exception('All machines from list already assigned.')

        return str(found_vmid)

    def get_mac(self, vmid: str) -> str:
        config = self.provider().api.get_vm_config(int(vmid))
        return config.networks[0].mac.lower()

    def get_ip(self, vmid: str) -> str:
        return self.provider().api.get_guest_ip_address(int(vmid))

    def get_name(self, vmid: str) -> str:
        return self.provider().api.get_vm_info(int(vmid)).name or ''
