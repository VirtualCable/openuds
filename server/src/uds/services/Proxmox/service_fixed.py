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
import logging
import typing

from django.utils.translation import gettext_noop as _, gettext
from uds.core import services, types, consts, exceptions
from uds.core.services.expecializations.fixed_machine.fixed_service import FixedService
from uds.core.services.expecializations.fixed_machine.fixed_userservice import FixedUserService
from uds.core.ui import gui
from uds.core.util import validators, log
from uds.core.util.decorators import cached
from uds.core.workers import initialize

from . import helpers
from .deployment_fixed import ProxmoxFixedUserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds import models

    from . import client
    from .provider import ProxmoxProvider

logger = logging.getLogger(__name__)


class ProxmoxFixedService(FixedService):  # pylint: disable=too-many-public-methods
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
    user_service_type = ProxmoxFixedUserService

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
    # Keep name as "machine" so we can use VCHelpers.getMachines
    machines = gui.MultiChoiceField(
        label=_("Machines"),
        order=21,
        tooltip=_('Machines for this service'),
        required=True,
        tab=_('Machines'),
        rows=10,
    )

    use_snapshots = gui.CheckBoxField(
        label=_('Use snapshots'),
        default=False,
        order=22,
        tooltip=_('If active, UDS will try to create an snapshot on VM use and recover if on exit.'),
        tab=_('Machines'),
        old_field_name='useSnapshots',
    )

    prov_uuid = gui.HiddenField(value=None)

    def initialize(self, values: 'Module.ValuesType') -> None:
        """
        Loads the assigned machines from storage
        """
        if values:
            if not self.machines.value:
                raise exceptions.ui.ValidationError(gettext('We need at least a machine'))

            self.storage.put_pickle('userservices_limit', len(self.machines.as_list()))

            # Remove machines not in values from "assigned" set
            self._save_assigned_machines(self._get_assigned_machines() & set(self.machines.as_list()))
            self.token.value = self.token.value.strip()
        self.userservices_limit = self.storage.get_unpickle('userservices_limit')

    def init_gui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.prov_uuid.value = self.parent().get_uuid()

        self.pool.set_choices(
            [gui.choice_item('', _('None'))]
            + [gui.choice_item(p.poolid, p.poolid) for p in self.parent().list_pools()]
        )

    def parent(self) -> 'ProxmoxProvider':
        return typing.cast('ProxmoxProvider', super().parent())

    def get_machine_info(self, vmId: int) -> 'client.types.VMInfo':
        return self.parent().get_machine_info(vmId, self.pool.value.strip())

    def get_task_info(self, node: str, upid: str) -> 'client.types.TaskStatus':
        return self.parent().get_task_info(node, upid)

    def start_machine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().start_machine(vmId)

    def stop_machine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().stop_machine(vmId)

    def reset_machine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().reset_machine(vmId)

    def suspend_machine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().suspend_machine(vmId)

    def shutdown_machine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().shutdown_machine(vmId)

    def enumerate_assignables(self) -> list[tuple[str, str]]:
        # Obtain machines names and ids for asignables
        vms: dict[int, str] = {}

        for member in self.parent().get_pool_info(self.pool.value.strip(), retrieve_vm_names=True).members:
            vms[member.vmid] = member.vmname

        assigned_vms = self._get_assigned_machines()
        return [(k, vms.get(int(k), 'Unknown!')) for k in self.machines.as_list() if int(k) not in assigned_vms]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', user_deployment: 'services.UserService'
    ) -> str:
        userservice_instance = typing.cast(ProxmoxFixedUserService, user_deployment)
        assigned_vms = self._get_assigned_machines()
        if assignable_id not in assigned_vms:
            assigned_vms.add(assignable_id)
            self._save_assigned_machines(assigned_vms)
            return userservice_instance.assign(assignable_id)

        return userservice_instance.error('VM not available!')

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_avaliable(self) -> bool:
        return self.parent().is_available()

    def process_snapshot(self, remove: bool, userservice_instace: FixedUserService) -> str:
        userservice_instace = typing.cast(ProxmoxFixedUserService, userservice_instace)
        if self.use_snapshots.as_bool():
            vmid = int(userservice_instace._vmid)
            if remove:
                try:
                    # try to revert to snapshot
                    snapshot = self.parent().get_current_snapshot(vmid)
                    if snapshot:
                        userservice_instace._store_task(
                            self.parent().restore_snapshot(vmid, name=snapshot.name)
                        )
                except Exception as e:
                    self.do_log(log.LogLevel.WARNING, 'Could not restore SNAPSHOT for this VM. ({})'.format(e))

            else:
                logger.debug('Using snapshots')
                # If no snapshot exists for this vm, try to create one for it on background
                # Lauch an snapshot. We will not wait for it to finish, but instead let it run "as is"
                try:
                    if not self.parent().get_current_snapshot(vmid):
                        logger.debug('Not current snapshot')
                        self.parent().create_snapshot(
                            vmid,
                            name='UDS Snapshot',
                        )
                except Exception as e:
                    self.do_log(log.LogLevel.WARNING, 'Could not create SNAPSHOT for this VM. ({})'.format(e))

        return types.states.State.RUNNING

    def get_and_assign_machine(self) -> str:
        found_vmid: typing.Optional[int] = None
        try:
            assigned_vms = self._get_assigned_machines()
            for k in self.machines.as_list():
                checking_vmid = int(k)
                if found_vmid not in assigned_vms:  # Not assigned
                    # Check that the machine exists...
                    try:
                        vm_info = self.parent().get_machine_info(checking_vmid, self.pool.value.strip())
                        found_vmid = checking_vmid
                        break
                    except Exception:  # Notifies on log, but skipt it
                        self.parent().do_log(
                            log.LogLevel.WARNING, 'Machine {} not accesible'.format(found_vmid)
                        )
                        logger.warning(
                            'The service has machines that cannot be checked on proxmox (connection error or machine has been deleted): %s',
                            found_vmid,
                        )

            if found_vmid:
                assigned_vms.add(str(found_vmid))
                self._save_assigned_machines(assigned_vms)
        except Exception:  #
            raise Exception('No machine available')

        if not found_vmid:
            raise Exception('All machines from list already assigned.')

        return str(found_vmid)

    def get_first_network_mac(self, vmid: str) -> str:
        config = self.parent().get_machine_configuration(int(vmid))
        return config.networks[0].mac.lower()

    def get_guest_ip_address(self, vmid: str) -> str:
        return self.parent().get_guest_ip_address(int(vmid))

    def get_machine_name(self, vmid: str) -> str:
        return self.parent().get_machine_info(int(vmid)).name or ''

    def remove_and_free_machine(self, vmid: str) -> None:
        try:
            self._save_assigned_machines(self._get_assigned_machines() - {str(vmid)})  # Remove from assigned
        except Exception as e:
            logger.warn('Cound not save assigned machines on fixed pool: %s', e)
