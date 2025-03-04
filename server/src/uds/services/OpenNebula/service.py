# -*- coding: utf-8 -*-

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
from uds.core import services, types
from uds.core.util import validators
from uds.core.ui import gui

from .publication import OpenNebulaLivePublication
from .deployment import OpenNebulaLiveDeployment

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import on
    from .provider import OpenNebulaProvider

logger = logging.getLogger(__name__)


class OpenNebulaLiveService(services.Service):
    """
    Opennebula Live Service
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenNebula Live Images')
    # : Type used internally to identify this provider
    type_type = 'openNebulaLiveService'
    # : Description shown at administration interface for this provider
    type_description = _('OpenNebula live images based service')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'provider.png'

    # Functional related data

    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is uses_cache is True, you will need also
    # : set publication_type, do take care about that!
    uses_cache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cache_tooltip = _('Number of desired machines to keep running waiting for an user')
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
    publication_type = OpenNebulaLivePublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OpenNebulaLiveDeployment

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI



    # Now the form part
    datastore = gui.ChoiceField(
        label=_("Datastore"),
        order=100,
        tooltip=_('Service clones datastore'),
        required=True,
    )

    template = gui.ChoiceField(
        label=_("Base Template"),
        order=110,
        tooltip=_('Service base template'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    baseName = gui.TextField(
        label=_('Machine Names'),
        readonly=False,
        order=111,
        tooltip=_('Base name for clones from this machine'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    lenName = gui.NumericField(
        length=1,
        label=_('Name Length'),
        default=5,
        order=112,
        tooltip=_('Size of numeric part for the names of these machines'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We check here form values to see if they are valid.

        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        """
        if not values:
            return

        self.baseName.value = validators.validate_basename(
            self.baseName.value, length=self.lenName.as_int()
        )

    def provider(self) -> 'OpenNebulaProvider':
        return typing.cast('OpenNebulaProvider', super().provider())

    def init_gui(self) -> None:
        """
        Loads required values inside
        """

        self.template.set_choices(
            [gui.choice_item(t.id, t.name) for t in self.provider().get_templates()]
        )

        self.datastore.set_choices(
            [gui.choice_item(d.id, d.name) for d in self.provider().get_datastores()]
        )

    def sanitized_name(self, name: str) -> str:
        return self.provider().sanitized_name(name)

    def make_template(self, name: str) -> str:
        return self.provider().make_template(
            self.template.value, name, self.datastore.value
        )

    def check_template_published(self, template_id: str) -> bool:
        return self.provider().check_template_published(template_id)

    def deploy_from_template(self, name: str, template_id: str) -> str:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            template_id: Id of the template to deploy from

        Returns:
            Id of the machine being created form template
        """
        logger.debug('Deploying from template %s machine %s', template_id, name)
        # self.datastoreHasSpace()
        return self.provider().deply_from_template(name, template_id)

    def remove_template(self, template_id: str) -> None:
        """
        invokes template_id from parent provider
        """
        self.provider().remove_template(template_id)

    def get_machine_state(self, machine_id: str) -> 'on.types.VmState':
        """
        Invokes getMachineState from parent provider
        (returns if machine is "active" or "inactive"

        Args:
            machine_id: If of the machine to get state

        Returns:
            one of this values:
             unassigned, down, up, powering_up, powered_down,
             paused, migrating_from, migrating_to, unknown, not_responding,
             wait_for_launch, reboot_in_progress, saving_state, restoring_state,
             suspended, image_illegal, image_locked or powering_down
             Also can return'unknown' if Machine is not known
        """
        return self.provider().get_machine_state(machine_id)

    def get_machine_substate(self, machine_id: str) -> int:
        """
        On OpenNebula, the machine can be "active" but not "running".
        Any active machine will have a LCM_STATE, that is what we get here
        """
        return self.provider().get_machine_substate(machine_id)

    def start_machine(self, machine_id: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to OpenNebula.

        This start also "resume" suspended/paused machines

        Args:
            machine_id: Id of the machine

        Returns:
        """
        self.provider().start_machine(machine_id)

    def stop_machine(self, machine_id: str) -> None:
        """
        Tries to stop a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machine_id: Id of the machine

        Returns:
        """
        self.provider().stop_machine(machine_id)

    def suspend_machine(self, machine_id: str) -> None:
        """
        Tries to suspend machine. No check is done, it is simply requested to OpenNebula

        Args:
            machine_id: Id of the machine

        Returns:
        """
        self.provider().suspend_machine(machine_id)

    def shutdown_machine(self, machine_id: str) -> None:
        """
        Tries to "gracefully" shutdown machine. No check is done, it is simply requested to OpenNebula

        Args:
            machine_id: Id of the machine

        Returns:
        """
        self.provider().shutdown_machine(machine_id)

    def reset_machine(self, machine_id: str) -> None:
        self.provider().reset_machine(machine_id)

    def remove_machine(self, machine_id: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machine_id: Id of the machine

        Returns:
        """
        self.provider().remove_machine(machine_id)

    def get_network_info(
        self, machine_id: str, network_id: typing.Optional[str] = None
    ) -> tuple[str, str]:
        """
        Gets the network info for a machine
        """
        return self.provider().get_network_info(machine_id, network_id=None)

    def get_basename(self) -> str:
        """
        Returns the base name
        """
        return self.baseName.value

    def get_lenname(self) -> int:
        """
        Returns the length of numbers part
        """
        return self.lenName.as_int()

    def get_console_connection(self, vmid: str) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.provider().get_console_connection(vmid)

    def desktop_login(
        self, vmid: str, username: str, password: str, domain: str
    ) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.provider().desktop_login(vmid, username, password, domain)

    def is_avaliable(self) -> bool:
        return self.provider().is_available()
