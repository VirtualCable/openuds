# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
import re
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import services, exceptions, types
from uds.core.util import validators, fields
from uds.core.ui import gui

from .publication import OVirtPublication
from .deployment_linked import OVirtLinkedUserService
from . import helpers

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OVirtProvider


from .ovirt import types as ov_types

logger = logging.getLogger(__name__)


class OVirtLinkedService(services.Service):  # pylint: disable=too-many-public-methods
    """
    oVirt Linked clones service. This is based on creating a template from selected vm, and then use it to
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('oVirt/RHEV Linked Clone')
    # : Type used internally to identify this provider
    type_type = 'oVirtLinkedService'
    # : Description shown at administration interface for this provider
    type_description = _('oVirt Services based on templates and COW (experimental)')
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
    publication_type = OVirtPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OVirtLinkedUserService

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI

    # Now the form part
    cluster = gui.ChoiceField(
        label=_("Cluster"),
        order=100,
        fills={
            'callback_name': 'ovFillResourcesFromCluster',
            'function': helpers.get_resources,
            'parameters': ['cluster', 'prov_uuid'],
        },
        tooltip=_("Cluster to contain services"),
        required=True,
    )

    datastore = gui.ChoiceField(
        label=_("Datastore Domain"),
        readonly=False,
        order=101,
        tooltip=_('Datastore domain where to publish and put incrementals'),
        required=True,
    )

    reserved_storage_gb = gui.NumericField(
        length=3,
        label=_('Reserved Space'),
        default=32,
        min_value=0,
        order=102,
        tooltip=_('Minimal free space in GB'),
        required=True,
        old_field_name='minSpaceGB',
    )

    try_soft_shutdown = fields.soft_shutdown_field()
    
    machine = gui.ChoiceField(
        label=_("Base Machine"),
        order=110,
        tooltip=_('Service base machine'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    memory = gui.NumericField(
        label=_("Memory (Mb)"),
        length=4,
        default=512,
        min_value=0,
        readonly=False,
        order=111,
        tooltip=_('Memory assigned to machines'),
        tab=types.ui.Tab.MACHINE,
        required=True,
    )

    guaranteed_memory = gui.NumericField(
        label=_("Memory Guaranteed (Mb)"),
        length=4,
        default=256,
        min_value=0,
        readonly=False,
        order=112,
        tooltip=_('Physical memory guaranteed to machines'),
        tab=types.ui.Tab.MACHINE,
        required=True,
        old_field_name='memoryGuaranteed',
    )

    usb = gui.ChoiceField(
        label=_('USB'),
        readonly=False,
        order=113,
        tooltip=_('Enable usb redirection for SPICE'),
        choices=[
            gui.choice_item('disabled', 'disabled'),
            gui.choice_item('native', 'native'),
        ],
        tab=types.ui.Tab.MACHINE,
        default='1',  # Default value is the ID of the choicefield
    )

    display = gui.ChoiceField(
        label=_('Display'),
        readonly=False,
        order=114,
        tooltip=_('Display type (only for administration purposes)'),
        choices=[gui.choice_item('spice', 'Spice'), gui.choice_item('vnc', 'Vnc')],
        tab=types.ui.Tab.MACHINE,
        default='1',  # Default value is the ID of the choicefield
    )
    basename = fields.basename_field(order=115, tab=types.ui.Tab.MACHINE)
    lenname = fields.lenname_field(order=116, tab=types.ui.Tab.MACHINE)

    prov_uuid = gui.HiddenField()

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We check here form values to see if they are valid.

        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        """
        if values:
            validators.validate_basename(self.basename.value, self.lenname.as_int())
            if int(self.memory.value) < 256 or int(self.guaranteed_memory.value) < 256:
                raise exceptions.ui.ValidationError(_('The minimum allowed memory is 256 Mb'))
            if int(self.guaranteed_memory.value) > int(self.memory.value):
                self.guaranteed_memory.value = self.memory.value

    def init_gui(self) -> None:
        """
        Loads required values inside
        """

        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.prov_uuid.value = self.provider().get_uuid()

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.machine.set_choices(gui.choice_item(m.id, m.name) for m in self.provider().api.list_machines())

        self.cluster.set_choices(gui.choice_item(c.id, c.name) for c in self.provider().api.list_clusters())

    def provider(self) -> 'OVirtProvider':
        return typing.cast('OVirtProvider', super().provider())

    def verify_free_storage(self) -> None:
        """Checks if datastore has enough space

        Raises:
            Exception: Raises an Exception if not enough space

        Returns:
            None -- [description]
        """
        # Get storages for that datacenter
        logger.debug('Checking datastore space for %s', self.datastore.value)
        info = self.provider().api.get_storage_info(self.datastore.value)
        logger.debug('Datastore Info: %s', info)
        free_storage_gb = info.available / (1024 * 1024 * 1024)
        if free_storage_gb < self.reserved_storage_gb.value:
            raise Exception(
                f'Not enough free space available: Needs at least {self.reserved_storage_gb.value} GB but only {free_storage_gb} GB is available.'
            )

    def sanitized_name(self, name: str) -> str:
        """
        Ovirt only allows machine names with [a-zA-Z0-9_-]
        """
        return re.sub("[^a-zA-Z0-9_-]", "_", name)

    def make_template(self, name: str, comments: str) -> ov_types.TemplateInfo:
        """
        Invokes makeTemplate from parent provider, completing params

        Args:
            name: Name to assign to template (must be previously "sanitized"
            comments: Comments (UTF-8) to add to template

        Returns:
            template Id of the template created

        Raises an exception if operation fails.
        """

        # Checks datastore size
        # Get storages for that datacenter

        self.verify_free_storage()
        return self.provider().api.create_template(
            name,
            comments,
            self.machine.value,
            self.cluster.value,
            self.datastore.value,
            self.display.value,
        )

    def deploy_from_template(self, name: str, comments: str, template_id: str) -> ov_types.VMInfo:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            template_id: Id of the template to deploy from

        Returns:
            Info of the deployed machine
        """
        logger.debug('Deploying from template %s machine %s', template_id, name)
        self.verify_free_storage()
        return self.provider().api.deploy_from_template(
            name,
            comments,
            template_id,
            self.cluster.value,
            self.display.value,
            self.usb.value,
            int(self.memory.value),
            int(self.guaranteed_memory.value),
        )

    def fix_usb(self, vmid: str) -> None:
        # If has usb, upgrade vm to add it now
        if self.usb.value in ('native',):
            self.provider().api.fix_usb(vmid)

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

    def get_display(self) -> str:
        """
        Returns the selected display type (for created machines, for administration
        """
        return self.display.value

    def get_console_connection(self, vmid: str) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        return self.provider().api.get_console_connection_info(vmid)

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def try_graceful_shutdown(self) -> bool:
        return self.try_soft_shutdown.as_bool()
