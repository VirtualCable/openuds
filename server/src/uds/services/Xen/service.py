# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import collections.abc
import typing

from django.utils.translation import gettext_noop as _
from uds.core import exceptions, types
from uds.core.services.generics.dynamic.service import DynamicService
from uds.core.util import validators
from uds.core.ui import gui

from .publication import XenPublication
from .deployment import XenLinkedUserService

from .xen import exceptions as xen_exceptions

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import XenProvider
    from uds.core.services.generics.dynamic.publication import DynamicPublication
    from uds.core.services.generics.dynamic.userservice import DynamicUserService

logger = logging.getLogger(__name__)


class XenLinkedService(DynamicService):  # pylint: disable=too-many-public-methods
    """
    Xen Linked clones service. This is based on creating a template from selected vm, and then use it to
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Xen Linked Clone')
    # : Type used internally to identify this provider
    type_type = 'XenLinkedService'
    # : Description shown at administration interface for this provider
    type_description = _('Xen Services based on templates')
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
    cache_tooltip_l2 = _('Number of desired machines to keep suspended waiting for use')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needs_osmanager = True
    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = XenPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = XenLinkedUserService

    services_type_provided = types.services.ServiceType.VDI

    # Now the form part
    datastore = gui.ChoiceField(
        label=_("Storage SR"),
        readonly=False,
        order=100,
        tooltip=_('Storage where to publish and put incrementals (only shared storages are supported)'),
        required=True,
    )

    min_space_gb = gui.NumericField(
        length=3,
        label=_('Reserved Space'),
        default=32,
        order=101,
        tooltip=_('Minimal free space in GB'),
        required=True,
        old_field_name='minSpaceGB',
    )

    machine = gui.ChoiceField(
        label=_("Base Machine"),
        order=110,
        tooltip=_('Service base machine'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    network = gui.ChoiceField(
        label=_("Network"),
        readonly=False,
        order=111,
        tooltip=_('Network used for virtual machines'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    memory = gui.NumericField(
        label=_("Memory (Mb)"),
        length=4,
        default=512,
        readonly=False,
        order=112,
        tooltip=_('Memory assigned to machines'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    shadow = gui.NumericField(
        label=_("Shadow"),
        length=1,
        default=1,
        readonly=False,
        order=113,
        tooltip=_('Shadow memory multiplier (use with care)'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    remove_duplicates = DynamicService.remove_duplicates
    maintain_on_error = DynamicService.maintain_on_error
    try_soft_shutdown = DynamicService.try_soft_shutdown
    put_back_to_cache = DynamicService.put_back_to_cache

    basename = DynamicService.basename
    lenname = DynamicService.lenname

    def initialize(self, values: types.core.ValuesType) -> None:
        """
        We check here form values to see if they are valid.

        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        """
        if values:
            validators.validate_basename(self.basename.value, self.lenname.as_int())

            if int(self.memory.value) < 256:
                raise exceptions.ui.ValidationError(_('The minimum allowed memory is 256 Mb'))

    def provider(self) -> 'XenProvider':
        return typing.cast('XenProvider', super().provider())

    def init_gui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        GB: typing.Final[int] = 1024**3

        with self.provider().get_connection() as api:
            machines_list = [gui.choice_item(m.opaque_ref, m.name) for m in api.list_vms()]
            storages_list: list[types.ui.ChoiceItem] = [
                gui.choice_item(
                    storage.opaque_ref,
                    f'{storage.name} ({storage.physical_size/GB:.2f} Gb/{storage.free_space/GB:.2f} Gb)',
                )
                for storage in api.list_srs()
            ]
            network_list = [gui.choice_item(net.opaque_ref, net.name) for net in api.list_networks()]

        self.machine.set_choices(machines_list)
        self.datastore.set_choices(storages_list)
        self.network.set_choices(network_list)

    def has_datastore_space(self) -> None:
        with self.provider().get_connection() as api:
            info = api.get_sr_info(self.datastore.value)
            logger.debug('Checking datastore space for %s: %s', self.datastore.value, info)
            availableGB = (info.physical_size - info.physical_utilisation) // 1024
            if availableGB < self.min_space_gb.as_int():
                raise xen_exceptions.XenFatalError(
                    'Not enough free space available: (Needs at least {} GB and there is only {} GB '.format(
                        self.min_space_gb.as_int(), availableGB
                    )
                )

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def sanitized_name(self, name: str) -> str:
        """
        Xen Seems to allow all kind of names, but let's sanitize a bit
        """
        return re.sub(r'([^a-zA-Z0-9_ .-]+)', r'_', name)

    def find_duplicates(self, name: str, mac: str) -> collections.abc.Iterable[str]:
        """
        Checks if a machine with the same name or mac exists
        Returns the list with the vmids of the duplicated machines

        Args:
            name: Name of the machine
            mac: Mac of the machine

        Returns:
            List of duplicated machines

        Note:
            Maybe we can only check name or mac, or both, depending on the service
        """
        with self.provider().get_connection() as api:
            vms = api.list_vms()
            return [
                vm.opaque_ref for vm in vms if vm.name == name
            ]  # Only check for name, mac is harder to get, so by now, we only check for name

    def start_deploy_of_template(self, name: str, comments: str) -> str:
        """
        Invokes makeTemplate from parent provider, completing params

        Args:
            name: Name to assign to template (must be previously "sanitized"
            comments: Comments (UTF-8) to add to template

        Returns:
            template Id of the template created

        Raises an exception if operation fails.
        """

        logger.debug(
            'Starting deploy of template from machine %s on datastore %s',
            self.machine.value,
            self.datastore.value,
        )

        with self.provider().get_connection() as api:
            self.has_datastore_space()

            return api.clone_vm(self.machine.value, name, self.datastore.value)

    def convert_to_template(self, vm_opaque_ref: str) -> None:
        """
        converts machine to template
        """
        with self.provider().get_connection() as api:
            api.convert_to_template(vm_opaque_ref, self.shadow.value)

    def deploy_from_template(self, template_opaque_ref: str, *, name: str, comments: str) -> str:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name (str): Name (sanitized) of the machine
            comments (str): Comments for machine
            template_opaque_ref (str): Opaque reference of the template to deploy from

        Returns:
            str: Id of the task created for this operation
        """
        logger.debug('Deploying from template %s machine %s', template_opaque_ref, name)

        with self.provider().get_connection() as api:
            self.has_datastore_space()

            return api.deploy_from_template(template_opaque_ref, name)

    def delete_template(self, template_opaque_ref: str) -> None:
        """
        invokes removeTemplate from parent provider
        """
        with self.provider().get_connection() as api:
            api.delete_template(template_opaque_ref)

    def configure_vm(self, vm_opaque_ref: str, mac: str) -> None:
        with self.provider().get_connection() as api:
            api.configure_vm(
                vm_opaque_ref, mac_info={'network': self.network.value, 'mac': mac}, memory=self.memory.value
            )

    def get_ip(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> str:
        """
        Returns the ip of the machine
        If cannot be obtained, MUST raise an exception
        """
        return ''  # No ip will be get, UDS will assign one (from actor)

    def get_mac(
        self,
        caller_instance: typing.Optional['DynamicUserService | DynamicPublication'],
        vmid: str,
        *,
        force_new: bool = False,
    ) -> str:
        return self.mac_generator().get(self.provider().get_macs_range())

    def is_running(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> bool:
        """
        Returns if the machine is ready and running
        """
        with self.provider().get_connection() as api:
            vminfo = api.get_vm_info(vmid)
            if vminfo.power_state.is_running():
                return True
            return False

    def start(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> None:
        """
        Starts the machine
        Can return a task, or None if no task is returned
        """
        with self.provider().get_connection() as api:
            api.start_vm(vmid)

    def stop(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> None:
        """
        Stops the machine
        Can return a task, or None if no task is returned
        """
        with self.provider().get_connection() as api:
            api.stop_vm(vmid)

    def shutdown(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> None:
        with self.provider().get_connection() as api:
            api.shutdown_vm(vmid)

    def execute_delete(self, vmid: str) -> None:
        """
        Removes the machine, or queues it for removal, or whatever :)
        """
        with self.provider().get_connection() as api:
            api.delete_vm(vmid)

    # default is_deleted is enough for us, returns always True
