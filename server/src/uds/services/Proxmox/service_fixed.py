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
import re
import typing
import collections.abc

from django.utils.translation import gettext_noop as _, gettext
from uds.core import services, types, consts, exceptions
from uds.core.ui import gui
from uds.core.util import validators, log
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached
from uds.core.workers import initialize

from . import helpers
from .deployment import ProxmoxDeployment
from .publication import ProxmoxPublication

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds import models

    from . import client
    from .provider import ProxmoxProvider

logger = logging.getLogger(__name__)


class ProxmoxFixedService(services.Service):  # pylint: disable=too-many-public-methods
    """
    Proxmox Linked clones service. This is based on creating a template from selected vm, and then use it to
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Proxmox Fixed Machines')
    # : Type used internally to identify this provider
    type_type = 'ProxmoxFixedService'
    # : Description shown at administration interface for this provider
    type_description = _('Proxmox Services based on fixed machines')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'service.png'

    # Functional related data

    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is uses_cache is True, you will need also
    # : set publication_type, do take care about that!
    uses_cache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cache_tooltip = _('Number of desired machines to keep running waiting for a user')
    # : If we need to generate a "Level 2" cache for this service (i.e., L1
    # : could be running machines and L2 suspended machines)
    uses_cache_l2 = True
    # : Tooltip shown to user when this item is pointed at admin interface, None
    # : also because we don't use it
    cache_tooltip_l2 = _('Number of desired VMs to keep stopped waiting for use')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needs_manager = True
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    must_assign_manually = False
    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = ProxmoxPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = ProxmoxDeployment

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI

    # Gui
    token = gui.TextField(
        order=1,
        label=_('Service Token'),
        length=16,
        tooltip=_(
            'Service token that will be used by actors to communicate with service. Leave empty for persistent assignation.'
        ),
        default='',
        required=False,
        readonly=False,
    )

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

    def _get_assigned_machines(self) -> typing.Set[int]:
        vals = self.storage.get_unpickle('vms')
        logger.debug('Got storage VMS: %s', vals)
        return vals or set()

    def _save_assigned_machines(self, vals: typing.Set[int]) -> None:
        logger.debug('Saving storage VMS: %s', vals)
        self.storage.put_pickle('vms', vals)

    def initialize(self, values: 'Module.ValuesType') -> None:
        """
        Loads the assigned machines from storage
        """
        if values:
            if not self.machines.value:
                raise exceptions.ui.ValidationError(gettext('We need at least a machine'))

            self.storage.put_pickle('maxDeployed', len(self.machines.as_list()))

            # Remove machines not in values from "assigned" set
            self._save_assigned_machines(self._get_assigned_machines() & set(self.machines.as_list()))
            self.token.value = self.token.value.strip()
        self.userservices_limit = self.storage.get_unpickle('maxDeployed')

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

    def sanitized_name(self, name: str) -> str:
        """
        Proxmox only allows machine names with [a-zA-Z0-9_-]
        """
        return re.sub("[^a-zA-Z0-9_-]", "-", name)

    def get_machine_info(self, vmId: int) -> 'client.types.VMInfo':
        return self.parent().get_machine_info(vmId, self.pool.value.strip())

    def get_nic_mac(self, vmid: int) -> str:
        config = self.parent().get_machine_configuration(vmid)
        return config.networks[0].mac.lower()

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

    def get_machine_from_pool(self) -> int:
        found_vmid: typing.Optional[int] = None
        try:
            assignedVmsSet = self._get_assigned_machines()
            for k in self.machines.as_list():
                checking_vmid = int(k)
                if found_vmid not in assignedVmsSet:  # Not assigned
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
                            'The service has machines that cannot be checked on vmware (connection error or machine has been deleted): %s',
                            found_vmid,
                        )

            if found_vmid:
                assignedVmsSet.add(found_vmid)
                self._save_assigned_machines(assignedVmsSet)
        except Exception:  #
            raise Exception('No machine available')

        if not found_vmid:
            raise Exception('All machines from list already assigned.')

        return found_vmid

    def release_machine_from_pool(self, vmid: int) -> None:
        try:
            self._save_assigned_machines(self._get_assigned_machines() - {vmid})  # Sets operation
        except Exception as e:
            logger.warn('Cound not save assigned machines on vmware fixed pool: %s', e)

    def enumerate_assignables(self) -> list[tuple[str, str]]:
        # Obtain machines names and ids for asignables
        vms: dict[int, str] = {}

        for member in self.parent().get_pool_info(self.pool.value.strip()).members:
            vms[member.vmid] = member.vmname

        assignedVmsSet = self._get_assigned_machines()
        k: str
        return [
            (k, vms.get(int(k), 'Unknown!')) for k in self.machines.as_list() if int(k) not in assignedVmsSet
        ]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', user_deployment: 'services.UserService'
    ) -> str:
        userservice_instance: ProxmoxDeployment = typing.cast(ProxmoxDeployment, user_deployment)
        assignedVmsSet = self._get_assigned_machines()
        if assignable_id not in assignedVmsSet:
            assignedVmsSet.add(int(assignable_id))
            self._save_assigned_machines(assignedVmsSet)
            return userservice_instance.assign(assignable_id)

        return userservice_instance.error('VM not available!')

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_avaliable(self) -> bool:
        return self.parent().is_available()
