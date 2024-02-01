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

from django.utils.translation import gettext_noop as _
from uds.core import services, types, consts
from uds.core.ui import gui
from uds.core.util import validators, log, fields
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached

from . import helpers
from .deployment import ProxmoxDeployment
from .publication import ProxmoxPublication

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module

    from . import client
    from .provider import ProxmoxProvider

logger = logging.getLogger(__name__)


class ProxmoxLinkedService(services.Service):  # pylint: disable=too-many-public-methods
    """
    Proxmox Linked clones service. This is based on creating a template from selected vm, and then use it to
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Proxmox Linked Clone')
    # : Type used internally to identify this provider
    type_type = 'ProxmoxLinkedService'
    # : Description shown at administration interface for this provider
    type_description = _('Proxmox Services based on templates and COW')
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
    needs_osmanager = True
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

    pool = gui.ChoiceField(
        label=_("Pool"),
        order=1,
        tooltip=_('Pool that will contain UDS created vms'),
        # tab=_('Machine'),
        # required=True,
        default='',
    )

    ha = gui.ChoiceField(
        label=_('HA'),
        order=2,
        tooltip=_('Select if HA is enabled and HA group for machines of this service'),
        readonly=True,
    )

    
    soft_shutdown_field = fields.soft_shutdown_field()
    
    machine = gui.ChoiceField(
        label=_("Base Machine"),
        order=110,
        fills={
            'callback_name': 'pmFillResourcesFromMachine',
            'function': helpers.get_storage,
            'parameters': ['machine', 'prov_uuid'],
        },
        tooltip=_('Service base machine'),
        tab=_('Machine'),
        required=True,
    )

    datastore = gui.ChoiceField(
        label=_("Storage"),
        readonly=False,
        order=111,
        tooltip=_('Storage for publications & machines.'),
        tab=_('Machine'),
        required=True,
    )

    gpu = gui.ChoiceField(
        label=_("GPU Availability"),
        readonly=False,
        order=112,
        choices={
            '0': _('Do not check'),
            '1': _('Only if available'),
            '2': _('Only if NOT available'),
        },
        tooltip=_('Storage for publications & machines.'),
        tab=_('Machine'),
        required=True,
    )
    
    basename = fields.basename_field(order=115)
    lenname = fields.lenname_field(order=116)

    prov_uuid = gui.HiddenField(value=None)
    
    def initialize(self, values: 'Module.ValuesType') -> None:
        if values:
            self.basename.value = validators.validate_basename(
                self.basename.value, length=self.lenname.as_int()
            )
            # if int(self.memory.value) < 128:
            #     raise exceptions.ValidationException(_('The minimum allowed memory is 128 Mb'))

    def init_gui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.prov_uuid.value = self.parent().db_obj().uuid

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.machine.set_choices(
            [
                gui.choice_item(str(m.vmid), f'{m.node}\\{m.name or m.vmid} ({m.vmid})')
                for m in self.parent().list_machines()
                if m.name and m.name[:3] != 'UDS'
            ]
        )
        self.pool.set_choices(
            [gui.choice_item('', _('None'))]
            + [gui.choice_item(p.poolid, p.poolid) for p in self.parent().list_pools()]
        )
        self.ha.set_choices(
            [gui.choice_item('', _('Enabled')), gui.choice_item('__', _('Disabled'))]
            + [gui.choice_item(group, group) for group in self.parent().list_ha_groups()]
        )

    def parent(self) -> 'ProxmoxProvider':
        return typing.cast('ProxmoxProvider', super().parent())

    def sanitized_name(self, name: str) -> str:
        """
        Proxmox only allows machine names with [a-zA-Z0-9_-]
        """
        return re.sub("[^a-zA-Z0-9_-]", "-", name)

    def make_template(self, vmId: int) -> None:
        self.parent().create_template(vmId)

    def clone_machine(self, name: str, description: str, vmId: int = -1) -> 'client.types.VmCreationResult':
        name = self.sanitized_name(name)
        pool = self.pool.value or None
        if vmId == -1:  # vmId == -1 if cloning for template
            return self.parent().clone_machine(
                self.machine.value,
                name,
                description,
                as_linked_clone=False,
                target_storage=self.datastore.value,
                target_pool=pool,
            )

        return self.parent().clone_machine(
            vmId,
            name,
            description,
            as_linked_clone=True,
            target_storage=self.datastore.value,
            target_pool=pool,
            must_have_vgpus={'1': True, '2': False}.get(self.gpu.value, None),
        )

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

    def remove_machine(self, vmId: int) -> 'client.types.UPID':
        # First, remove from HA if needed
        try:
            self.disable_ha(vmId)
        except Exception as e:
            logger.warning('Exception disabling HA for vm %s: %s', vmId, e)
            self.do_log(level=log.LogLevel.WARNING, message=f'Exception disabling HA for vm {vmId}: {e}')

        # And remove it
        return self.parent().remove_machine(vmId)

    def enable_ha(self, vmId: int, started: bool = False) -> None:
        if self.ha.value == '__':
            return
        self.parent().enable_ha(vmId, started, self.ha.value or None)

    def disable_ha(self, vmId: int) -> None:
        if self.ha.value == '__':
            return
        self.parent().disable_ha(vmId)

    def set_protection(self, vmId: int, node: typing.Optional[str] = None, protection: bool = False) -> None:
        self.parent().set_protection(vmId, node, protection)

    def set_machine_mac(self, vmId: int, mac: str) -> None:
        self.parent().set_machine_mac(vmId, mac)

    def get_basename(self) -> str:
        return self.basename.value

    def get_lenname(self) -> int:
        return int(self.lenname.value)

    def get_macs_range(self) -> str:
        """
        Returns de selected mac range
        """
        return self.parent().get_macs_range()

    def enable_ha_for_machines(self) -> bool:
        return self.ha.value != '__'

    def try_graceful_shutdown(self) -> bool:
        return self.soft_shutdown_field.as_bool()

    def get_console_connection(
        self, machineId: str
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
        return self.parent().get_console_connection(machineId)

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_avaliable(self) -> bool:
        return self.parent().is_available()
