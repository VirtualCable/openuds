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
from uds.core.util import fields, validators
from uds.core.ui import gui

from .publication import OpenStackLivePublication
from .deployment import OpenStackLiveDeployment
from .openstack import types as openstack_types, openstack_client
from . import helpers


logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OpenStackProvider
    from .provider_legacy import OpenStackProviderLegacy

    AnyOpenStackProvider = typing.Union[OpenStackProvider, OpenStackProviderLegacy]


class OpenStackLiveService(services.Service):
    """
    OpenStack Live Service
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenStack Live Volume')
    # : Type used internally to identify this provider
    type_type = 'openStackLiveService'
    # : Description shown at administration interface for this provider
    type_description = _('OpenStack live images based service')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'openstack.png'

    # Functional related data

    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is uses_cache is True, you will need also
    # : set publication_type, do take care about that!
    uses_cache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cache_tooltip = _('Number of desired machines to keep running waiting for an user')

    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
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
    publication_type = OpenStackLivePublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OpenStackLiveDeployment

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI

    # Now the form part
    region = gui.ChoiceField(
        label=_('Region'),
        order=1,
        tooltip=_('Service region'),
        required=True,
        readonly=True,
    )
    project = gui.ChoiceField(
        label=_('Project'),
        order=2,
        fills={
            'callback_name': 'osFillResources',
            'function': helpers.get_resources,
            'parameters': ['prov_uuid', 'project', 'region'],
        },
        tooltip=_('Project for this service'),
        required=True,
        readonly=True,
    )
    availability_zone = gui.ChoiceField(
        label=_('Availability Zones'),
        order=3,
        fills={
            'callback_name': 'osFillVolumees',
            'function': helpers.get_volumes,
            'parameters': [
                'prov_uuid',
                'project',
                'region',
                'availability_zone',
            ],
        },
        tooltip=_('Service availability zones'),
        required=True,
        readonly=True,
        old_field_name='availabilityZone',
    )
    volume = gui.ChoiceField(
        label=_('Volume'),
        order=4,
        tooltip=_('Base volume for service (restricted by availability zone)'),
        required=True,
        tab=_('Machine'),
    )
    # volumeType = gui.ChoiceField(label=_('Volume Type'), order=5, tooltip=_('Volume type for service'), required=True)
    network = gui.ChoiceField(
        label=_('Network'),
        order=6,
        tooltip=_('Network to attach to this service'),
        required=True,
        tab=_('Machine'),
    )
    flavor = gui.ChoiceField(
        label=_('Flavor'),
        order=7,
        tooltip=_('Flavor for service'),
        required=True,
        tab=_('Machine'),
    )

    security_groups = gui.MultiChoiceField(
        label=_('Security Groups'),
        order=8,
        tooltip=_('Service security groups'),
        required=True,
        tab=_('Machine'),
        old_field_name='securityGroups',
    )

    basename = fields.basename_field(order=9, tab=_('Machine'))
    lenname = fields.lenname_field(order=10, tab=_('Machine'))

    maintain_on_error = fields.maintain_on_error_field(order=104)

    prov_uuid = gui.HiddenField()

    _api: typing.Optional['openstack_client.OpenstackClient'] = None

    def initialize(self, values: types.core.ValuesType) -> None:
        """
        We check here form values to see if they are valid.

        Note that we check them through FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        """
        if values:
            validators.validate_basename(self.basename.value, self.lenname.as_int())

        # self.ov.value = self.provider().serialize()
        # self.ev.value = self.provider().env.key

    def provider(self) -> 'AnyOpenStackProvider':
        return typing.cast('AnyOpenStackProvider', super().provider())

    def init_gui(self) -> None:
        """
        Loads required values inside
        """
        api = self.provider().api()

        # Checks if legacy or current openstack provider
        parent = typing.cast('OpenStackProvider', self.provider()) if not self.provider().legacy else None

        if parent and parent.region.value:
            regions = [gui.choice_item(parent.region.value, parent.region.value)]
        else:
            regions = [gui.choice_item(r.id, r.name) for r in api.list_regions()]

        self.region.set_choices(regions)

        if parent and parent.tenant.value:
            tenants = [gui.choice_item(parent.tenant.value, parent.tenant.value)]
        else:
            tenants = [gui.choice_item(t.id, t.name) for t in api.list_projects()]
        self.project.set_choices(tenants)

        # So we can instantiate parent to get API
        logger.debug(self.provider().serialize())

        self.prov_uuid.value = self.provider().get_uuid()

    @property
    def api(self) -> 'openstack_client.OpenstackClient':
        if not self._api:
            self._api = self.provider().api(projectid=self.project.value, region=self.region.value)

        return self._api

    def sanitized_name(self, name: str) -> str:
        return self.provider().sanitized_name(name)

    def make_template(
        self, template_name: str, description: typing.Optional[str] = None
    ) -> openstack_types.VolumeSnapshotInfo:
        # First, ensures that volume has not any running instances
        # if self.api.getVolume(self.volume.value)['status'] != 'available':
        #    raise Exception('The Volume is in use right now. Ensure that there is no machine running before publishing')

        description = description or 'UDS Template snapshot'
        return self.api.create_volume_snapshot(self.volume.value, template_name, description)

    def get_template(self, snapshot_id: str) -> openstack_types.VolumeSnapshotInfo:
        """
        Checks current state of a template (an snapshot)
        """
        return self.api.get_volume_snapshot(snapshot_id)

    def deploy_from_template(self, name: str, snapshot_id: str) -> str:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            snapshotId: Id of the snapshot to deploy from

        Returns:
            Id of the machine being created form template
        """
        logger.debug('Deploying from template %s machine %s', snapshot_id, name)
        # self.datastoreHasSpace()
        return self.api.create_server_from_snapshot(
            snapshot_id=snapshot_id,
            name=name,
            availability_zone=self.availability_zone.value,
            flavor_id=self.flavor.value,
            network_id=self.network.value,
            security_groups_ids=self.security_groups.value,
        ).id

    def remove_template(self, templateId: str) -> None:
        """
        invokes removeTemplate from parent provider
        """
        self.api.delete_snapshot(templateId)

    def get_machine_state(self, machine_id: str) -> openstack_types.Status:
        vminfo = self.api.get_server(machine_id)
        if vminfo.status in (openstack_types.Status.ERROR, openstack_types.Status.DELETED):
            logger.warning(
                'Got server status %s for %s: %s',
                vminfo.status,
                machine_id,
                vminfo.fault,
            )
        return vminfo.status

    def get_machine_power_state(self, machine_id: str) -> openstack_types.PowerState:
        vminfo = self.api.get_server(machine_id)
        return vminfo.power_state

    def start_machine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to OpenStack.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.api.start_server(machineId)

    def stop_machine(self, machineId: str) -> None:
        """
        Tries to stop a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.api.stop_server(machineId)

    def reset_machine(self, machineId: str) -> None:
        """
        Tries to stop a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.api.reset_server(machineId)

    def suspend_machine(self, machineId: str) -> None:
        """
        Tries to suspend a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.api.suspend_server(machineId)

    def resume_machine(self, machineid: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.api.resume_server(machineid)

    def remove_machine(self, machine_id: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.api.delete_server(machine_id)

    def get_network_info(self, machine_id: str) -> tuple[str, str]:
        """
        Gets the mac address of first nic of the machine
        """
        vminfo = self.api.get_server(machine_id)
        return vminfo.addresses[0].mac, vminfo.addresses[0].addr.upper()

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

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def can_clean_errored_userservices(self) -> bool:
        return not self.maintain_on_error.value

    def keep_on_error(self) -> bool:
        return not self.maintain_on_error.as_bool()
