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
import typing

from django.utils.translation import gettext_noop as _
from uds.core import services, exceptions, types
from uds.core.util import fields, validators
from uds.core.ui import gui

from .publication import XenPublication
from .deployment import XenLinkedDeployment

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import XenProvider

logger = logging.getLogger(__name__)


class XenLinkedService(services.Service):  # pylint: disable=too-many-public-methods
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
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    must_assign_manually = False
    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = XenPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = XenLinkedDeployment

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
        tab=_('Machine'),
        required=True,
    )

    network = gui.ChoiceField(
        label=_("Network"),
        readonly=False,
        order=111,
        tooltip=_('Network used for virtual machines'),
        tab=_('Machine'),
        required=True,
    )

    memory = gui.NumericField(
        label=_("Memory (Mb)"),
        length=4,
        default=512,
        readonly=False,
        order=112,
        tooltip=_('Memory assigned to machines'),
        tab=_('Machine'),
        required=True,
    )

    shadow = gui.NumericField(
        label=_("Shadow"),
        length=1,
        default=1,
        readonly=False,
        order=113,
        tooltip=_('Shadow memory multiplier (use with care)'),
        tab=_('Machine'),
        required=True,
    )

    basename = fields.basename_field(order=114)
    lenname = fields.lenname_field(order=115)

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

        machines_list = [gui.choice_item(m['id'], m['name']) for m in self.provider().list_machines()]

        storages_list: list[types.ui.ChoiceItem] = []
        for storage in self.provider().list_storages():
            space, free = (
                storage['size'] / 1024,
                (storage['size'] - storage['used']) / 1024,
            )
            storages_list.append(
                gui.choice_item(
                    storage['id'],
                    "%s (%4.2f Gb/%4.2f Gb)" % (storage['name'], space, free),
                )
            )

        network_list = [gui.choice_item(net['id'], net['name']) for net in self.provider().get_networks()]

        self.machine.set_choices(machines_list)
        self.datastore.set_choices(storages_list)
        self.network.set_choices(network_list)

    def check_task_finished(self, task: str) -> tuple[bool, str]:
        return self.provider().check_task_finished(task)

    def has_datastore_space(self) -> None:
        # Get storages for that datacenter
        info = self.provider().get_storage_info(self.datastore.value)
        logger.debug('Checking datastore space for %s: %s', self.datastore.value, info)
        availableGB = (info['size'] - info['used']) / 1024
        if availableGB < self.min_space_gb.as_int():
            raise Exception(
                'Not enough free space available: (Needs at least {} GB and there is only {} GB '.format(
                    self.min_space_gb.as_int(), availableGB
                )
            )

    def sanitized_name(self, name: str) -> str:
        """
        Xen Seems to allow all kind of names
        """
        return name

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

        # Checks datastore available space, raises exeception in no min available
        self.has_datastore_space()

        return self.provider().clone_for_template(name, comments, self.machine.value, self.datastore.value)

    def convert_to_template(self, machineId: str) -> None:
        """
        converts machine to template
        """
        self.provider().convert_to_template(machineId, self.shadow.value)

    def start_deploy_from_template(self, name: str, comments: str, templateId: str) -> str:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            displayType: 'vnc' or 'spice'. Display to use ad Xen admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        """
        logger.debug('Deploying from template %s machine %s', templateId, name)
        self.has_datastore_space()

        return self.provider().start_deploy_from_template(name, comments, templateId)

    def remove_template(self, templateId: str) -> None:
        """
        invokes removeTemplate from parent provider
        """
        self.provider().remove_template(templateId)

    def get_machine_power_state(self, machineId: str) -> str:
        """
        Invokes getMachineState from parent provider

        Args:
            machineId: If of the machine to get state

        Returns:
            one of this values:
        """
        return self.provider().get_machine_power_state(machineId)

    def start_machine(self, machineId: str, asnc: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to Xen.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self.provider().start_machine(machineId, asnc)

    def stop_machine(self, machineId: str, asnc: bool = True) -> typing.Optional[str]:
        """
        Tries to stop a machine. No check is done, it is simply requested to Xen

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self.provider().stop_machine(machineId, asnc)

    def reset_machine(self, machine_id: str, asnc: bool = True) -> typing.Optional[str]:
        """
        Tries to stop a machine. No check is done, it is simply requested to Xen

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self.provider().reset_machine(machine_id, asnc)

    def can_suspend_machine(self, machineId: str) -> bool:
        """
        The machine can be suspended only when "suspend" is in their operations list (mush have xentools installed)

        Args:
            machineId: Id of the machine

        Returns:
            True if the machien can be suspended
        """
        return self.provider().can_suspend_machine(machineId)

    def suspend_machine(self, machineId: str, asnc: bool = True) -> typing.Optional[str]:
        """
        Tries to suspend a machine. No check is done, it is simply requested to Xen

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self.provider().suspend_machine(machineId, asnc)

    def resume_machine(self, machineId: str, asnc: bool = True) -> typing.Optional[str]:
        """
        Tries to resume a machine. No check is done, it is simply requested to Xen

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self.provider().suspend_machine(machineId, asnc)

    def remove_machine(self, machineId: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to Xen

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.provider().remove_machine(machineId)

    def configure_machine(self, machine_id: str, mac: str) -> None:
        self.provider().configure_machine(machine_id, self.network.value, mac, self.memory.value)

    def provision_machine(self, machine_id: str, as_async: bool = True) -> str:
        return self.provider().provision_machine(machine_id, as_async)

    def get_macs_range(self) -> str:
        """
        Returns de selected mac range
        """
        return self.provider().get_macs_range()

    def get_basename(self) -> str:
        """
        Returns the base name
        """
        return self.basename.value

    def get_lenname(self) -> int:
        """
        Returns the length of numbers part
        """
        return int(self.lenname.value)
