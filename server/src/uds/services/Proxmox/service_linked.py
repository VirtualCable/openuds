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

from django.utils.translation import gettext_noop as _

from uds.core import types
from uds.core.services.generics.dynamic.publication import DynamicPublication
from uds.core.services.generics.dynamic.service import DynamicService
from uds.core.services.generics.dynamic.userservice import DynamicUserService
from uds.core.ui import gui
from uds.core.util import validators

from . import helpers
from .deployment_linked import ProxmoxUserserviceLinked
from .publication import ProxmoxPublication

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .proxmox import types as prox_types
    from .provider import ProxmoxProvider
    from uds.core.services.generics.dynamic.publication import DynamicPublication
    from uds.core.services.generics.dynamic.service import DynamicService
    from uds.core.services.generics.dynamic.userservice import DynamicUserService

logger = logging.getLogger(__name__)


class ProxmoxServiceLinked(DynamicService):
    """
    Proxmox Linked clones service. This is based on creating a template from selected vm, and then use it to

    Notes:
      * We do not suspend machines, we try to shutdown them gracefully
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Proxmox Linked Clone')
    # : Type used internally to identify this provider, must not be modified once created
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
    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = ProxmoxPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = ProxmoxUserserviceLinked

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI

    pool = gui.ChoiceField(
        label=_("Pool"),
        order=1,
        tooltip=_('Pool that will contain UDS created vms'),
        # tab=types.ui.Tab.MACHINE,
        # required=True,
        default='',
    )

    ha = gui.ChoiceField(
        label=_('HA'),
        order=2,
        tooltip=_('Select if HA is enabled and HA group for machines of this service'),
        readonly=True,
    )

    try_soft_shutdown = DynamicService.try_soft_shutdown

    machine = gui.ChoiceField(
        label=_("Base Machine"),
        order=110,
        fills={
            'callback_name': 'pmFillResourcesFromMachine',
            'function': helpers.get_storage,
            'parameters': ['machine', 'prov_uuid'],
        },
        tooltip=_('Service base machine'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    datastore = gui.ChoiceField(
        label=_("Storage"),
        readonly=False,
        order=111,
        tooltip=_('Storage for publications & machines.'),
        tab=types.ui.Tab.MACHINE,
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
        tooltip=_('Checking method for GPU availability'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    basename = DynamicService.basename
    lenname = DynamicService.lenname

    prov_uuid = gui.HiddenField(value=None)

    def initialize(self, values: 'types.core.ValuesType') -> None:
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
        self.prov_uuid.value = self.provider().db_obj().uuid

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.machine.set_choices(
            [
                gui.choice_item(str(m.id), f'{m.node}\\{m.name or m.id} ({m.id})')
                for m in self.provider().list_vms()
                if m.name and m.name[:3] != 'UDS'
            ]
        )
        self.pool.set_choices(
            [gui.choice_item('', _('None'))]
            + [gui.choice_item(p.id, p.id) for p in self.provider().list_pools()]
        )
        self.ha.set_choices(
            [gui.choice_item('', _('Enabled')), gui.choice_item('__', _('Disabled'))]
            + [gui.choice_item(group, group) for group in self.provider().list_ha_groups()]
        )

    def provider(self) -> 'ProxmoxProvider':
        return typing.cast('ProxmoxProvider', super().provider())

    def sanitized_name(self, name: str) -> str:
        """
        Proxmox only allows machine names with [a-zA-Z0-9_-]
        """
        return re.sub("[^a-zA-Z0-9_-]", "-", name)

    def clone_vm(self, name: str, description: str, vmid: int = -1) -> 'prox_types.VmCreationResult':
        name = self.sanitized_name(name)
        pool = self.pool.value or None
        if vmid == -1:  # vmId == -1 if cloning for template
            return self.provider().clone_vm(
                self.machine.as_int(),
                name,
                description,
                as_linked_clone=False,
                target_storage=self.datastore.value,
                target_pool=pool,
            )

        return self.provider().clone_vm(
            vmid,
            name,
            description,
            as_linked_clone=True,
            target_storage=self.datastore.value,
            target_pool=pool,
            must_have_vgpus={'1': True, '2': False}.get(self.gpu.value, None),
        )

    def get_vm_info(self, vmid: int) -> 'prox_types.VMInfo':
        return self.provider().get_vm_info(vmid, self.pool.value.strip())

    def get_nic_mac(self, vmid: int) -> str:
        config = self.provider().get_vm_config(vmid)
        return config.networks[0].mac.lower()

    # TODO: Remove this method, kept for reference of old code
    def _xremove_machine(self, vmid: int) -> 'prox_types.UPID':
        # First, remove from HA if needed
        try:
            self.disable_vm_ha(vmid)
        except Exception as e:
            logger.warning('Exception disabling HA for vm %s: %s', vmid, e)
            self.do_log(level=types.log.LogLevel.WARNING, message=f'Exception disabling HA for vm {vmid}: {e}')

        # And remove it
        return self.provider().delete_vm(vmid)

    def enable_vm_ha(self, vmid: int, started: bool = False) -> None:
        if self.ha.value == '__':
            return
        self.provider().enable_machine_ha(vmid, started, self.ha.value or None)

    def disable_vm_ha(self, vmid: int) -> None:
        if self.ha.value == '__':
            return
        self.provider().disable_machine_ha(vmid)

    def get_macs_range(self) -> str:
        """
        Returns de selected mac range
        """
        return self.provider().get_macs_range()

    def is_ha_enabled(self) -> bool:
        return self.ha.value != '__'

    def get_console_connection(self, vmid: str) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.provider().api.get_console_connection(int(vmid))

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def get_ip(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> str:
        return self.provider().get_guest_ip_address(int(vmid))

    def get_mac(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> str:
        # If vmid is empty, we are requesting a new mac
        if not vmid:
            return self.mac_generator().get(self.get_macs_range())
        return self.get_nic_mac(int(vmid))

    def start(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        if isinstance(caller_instance, ProxmoxUserserviceLinked):
            if self.is_running(caller_instance, vmid):  # If running, skip
                caller_instance._task = ''
            else:
                caller_instance._store_task(self.provider().start_machine(int(vmid)))
        else:
            raise Exception('Invalid caller instance (publication) for start_machine()')

    def stop(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        if isinstance(caller_instance, ProxmoxUserserviceLinked):
            if self.is_running(caller_instance, vmid):
                caller_instance._store_task(self.provider().stop_machine(int(vmid)))
            else:
                caller_instance._task = ''
        else:
            raise Exception('Invalid caller instance (publication) for stop_machine()')

    def shutdown(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        if isinstance(caller_instance, ProxmoxUserserviceLinked):
            if self.is_running(caller_instance, vmid):
                caller_instance._store_task(self.provider().shutdown_machine(int(vmid)))
            else:
                caller_instance._task = ''
        else:
            raise Exception('Invalid caller instance (publication) for shutdown_machine()')

    def is_running(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> bool:
        # Raise an exception if fails to get machine info
        vminfo = self.get_vm_info(int(vmid))

        return vminfo.status != 'stopped'

    def execute_delete(self, vmid: str) -> None:
        # All removals are deferred, so we can do it async
        # Try to stop it if already running... Hard stop
        self.provider().delete_vm(int(vmid))
