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

from django.utils.translation import gettext
from django.utils.translation import gettext_noop as _

from uds.core import consts, exceptions, services, types
from uds.core.services.specializations.fixed_machine.fixed_service import FixedService
from uds.core.services.specializations.fixed_machine.fixed_userservice import FixedUserService
from uds.core.ui import gui
from uds.core.util import log
from uds.core.util.decorators import cached

from . import helpers
from .deployment_fixed import ProxmoxFixedUserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.module import Module

    from . import client
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

    machines = FixedService.machines
    use_snapshots = FixedService.use_snapshots

    prov_uuid = gui.HiddenField(value=None)

    def initialize(self, values: 'types.core.ValuesType') -> None:
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
        # Log with call stack
        self.prov_uuid.value = self.provider().get_uuid()

        self.pool.set_choices(
            [gui.choice_item('', _('None'))]
            + [gui.choice_item(p.poolid, p.poolid) for p in self.provider().list_pools()]
        )

    def provider(self) -> 'ProxmoxProvider':
        return typing.cast('ProxmoxProvider', super().provider())

    def get_machine_info(self, vmId: int) -> 'client.types.VMInfo':
        return self.provider().get_machine_info(vmId, self.pool.value.strip())

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        # Obtain machines names and ids for asignables
        vms: dict[int, str] = {}

        for member in self.provider().get_pool_info(self.pool.value.strip(), retrieve_vm_names=True).members:
            vms[member.vmid] = member.vmname

        assigned_vms = self._get_assigned_machines()
        return [
            gui.choice_item(k, vms.get(int(k), 'Unknown!'))
            for k in self.machines.as_list()
            if int(k) not in assigned_vms
        ]

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

    def process_snapshot(self, remove: bool, userservice_instance: FixedUserService) -> None:
        userservice_instance = typing.cast(ProxmoxFixedUserService, userservice_instance)
        if self.use_snapshots.as_bool():
            vmid = int(userservice_instance._vmid)
            if remove:
                try:
                    # try to revert to snapshot
                    snapshot = self.provider().get_current_snapshot(vmid)
                    if snapshot:
                        userservice_instance._store_task(
                            self.provider().restore_snapshot(vmid, name=snapshot.name)
                        )
                except Exception as e:
                    self.do_log(log.LogLevel.WARNING, 'Could not restore SNAPSHOT for this VM. ({})'.format(e))

            else:
                logger.debug('Using snapshots')
                # If no snapshot exists for this vm, try to create one for it on background
                # Lauch an snapshot. We will not wait for it to finish, but instead let it run "as is"
                try:
                    if not self.provider().get_current_snapshot(vmid):
                        logger.debug('No current snapshot')
                        self.provider().create_snapshot(
                            vmid,
                            name='UDS Snapshot',
                        )
                except Exception as e:
                    self.do_log(log.LogLevel.WARNING, 'Could not create SNAPSHOT for this VM. ({})'.format(e))

    def get_and_assign_machine(self) -> str:
        found_vmid: typing.Optional[str] = None
        try:
            assigned_vms = self._get_assigned_machines()
            for checking_vmid in self.machines.as_list():
                if checking_vmid not in assigned_vms:  # Not already assigned
                    try:
                        # Invoke to check it exists, do not need to store the result
                        self.provider().get_machine_info(int(checking_vmid), self.pool.value.strip())
                        found_vmid = checking_vmid
                        break
                    except Exception:  # Notifies on log, but skipt it
                        self.provider().do_log(
                            log.LogLevel.WARNING, 'Machine {} not accesible'.format(found_vmid)
                        )
                        logger.warning(
                            'The service has machines that cannot be checked on proxmox (connection error or machine has been deleted): %s',
                            found_vmid,
                        )

            if found_vmid:
                assigned_vms.add(found_vmid)
                self._save_assigned_machines(assigned_vms)
        except Exception:  #
            raise Exception('No machine available')

        if not found_vmid:
            raise Exception('All machines from list already assigned.')

        return str(found_vmid)

    def get_first_network_mac(self, vmid: str) -> str:
        config = self.provider().get_machine_configuration(int(vmid))
        return config.networks[0].mac.lower()

    def get_guest_ip_address(self, vmid: str) -> str:
        return self.provider().get_guest_ip_address(int(vmid))

    def get_machine_name(self, vmid: str) -> str:
        return self.provider().get_machine_info(int(vmid)).name or ''

    def remove_and_free_machine(self, vmid: str) -> str:
        try:
            self._save_assigned_machines(self._get_assigned_machines() - {str(vmid)})  # Remove from assigned
            return types.states.State.FINISHED
        except Exception as e:
            logger.warning('Cound not save assigned machines on fixed pool: %s', e)
            raise
