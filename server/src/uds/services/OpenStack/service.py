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

from uds.core import types
from uds.core.services.generics.dynamic.service import DynamicService
from uds.core.util import validators
from uds.core.ui import gui

from .publication import OpenStackLivePublication
from .deployment import OpenStackLiveUserService
from .openstack import client, types as openstack_types
from . import helpers


logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OpenStackProvider
    from .provider_legacy import OpenStackProviderLegacy

    AnyOpenStackProvider: typing.TypeAlias = typing.Union[OpenStackProvider, OpenStackProviderLegacy]

    from uds.core.services.generics.dynamic.userservice import DynamicUserService
    from uds.core.services.generics.dynamic.publication import DynamicPublication


class OpenStackLiveService(DynamicService):
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
    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = OpenStackLivePublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OpenStackLiveUserService

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
        tab=types.ui.Tab.MACHINE,
    )
    # volumeType = gui.ChoiceField(label=_('Volume Type'), order=5, tooltip=_('Volume type for service'), required=True)
    network = gui.ChoiceField(
        label=_('Network'),
        order=6,
        tooltip=_('Network to attach to this service'),
        required=True,
        tab=types.ui.Tab.MACHINE,
    )
    flavor = gui.ChoiceField(
        label=_('Flavor'),
        order=7,
        tooltip=_('Flavor for service'),
        required=True,
        tab=types.ui.Tab.MACHINE,
    )

    security_groups = gui.MultiChoiceField(
        label=_('Security Groups'),
        order=8,
        tooltip=_('Service security groups'),
        required=True,
        tab=types.ui.Tab.MACHINE,
        old_field_name='securityGroups',
    )

    basename = DynamicService.basename
    lenname = DynamicService.lenname

    maintain_on_error = DynamicService.maintain_on_error

    prov_uuid = gui.HiddenField()

    cached_api: typing.Optional['client.OpenStackClient'] = None

    # Note: currently, Openstack does not provides a way of specifying how to stop the server
    # At least, i have not found it on the documentation

    def initialize(self, values: types.core.ValuesType) -> None:
        """
        We check here form values to see if they are valid.

        Note that we check them through FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        """
        if values:
            validators.validate_basename(self.basename.value, self.lenname.as_int())

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

        self.prov_uuid.value = self.provider().get_uuid()

    @property
    def api(self) -> 'client.OpenStackClient':
        if not self.cached_api:
            self.cached_api = self.provider().api(projectid=self.project.value, region=self.region.value)

        return self.cached_api

    def sanitized_name(self, name: str) -> str:
        return self.provider().sanitized_name(name)

    def get_ip(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> str:
        return self.api.get_server_info(vmid).validated().addresses[0].ip

    def get_mac(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> str:
        return self.api.get_server_info(vmid).validated().addresses[0].mac

    def is_running(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> bool:
        return self.api.get_server_info(vmid).validated().power_state.is_running()

    def start(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        if self.api.get_server_info(vmid).validated().power_state.is_running():
            return
        self.api.start_server(vmid)

    def stop(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        if self.api.get_server_info(vmid).validated().power_state.is_stopped():
            return
        self.api.stop_server(vmid)

    # Default shutdown is stop
    # Note that on openstack, stop is "soft", but may fail to stop if no agent is installed or not responding
    # We can anyway delete de machine even if it is not stopped

    def reset(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        # Default is to stop "hard"
        return self.stop(caller_instance, vmid)
    
    def delete(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        """
        Removes the machine, or queues it for removal, or whatever :)
        """
        if isinstance(caller_instance, OpenStackLiveUserService):
            vmid = f'VM:{vmid}'
            super().delete(caller_instance, vmid)
        else:
            vmid = f'SS:{vmid}'
            super().delete(caller_instance, vmid)
            
    def execute_delete(self, vmid: str) -> None:
        kind, vmid = vmid.split(':')
        if kind == 'VM':
            self.api.delete_server(vmid)
        else:
            self.api.delete_snapshot(vmid)
            
    # default is_deleted is fine, returns True always

    def make_template(
        self, template_name: str, description: typing.Optional[str] = None
    ) -> openstack_types.SnapshotInfo:
        # First, ensures that volume has not any running instances
        # if self.api.getVolume(self.volume.value)['status'] != 'available':
        #    raise Exception('The Volume is in use right now. Ensure that there is no machine running before publishing')

        description = description or 'UDS Template snapshot'
        return self.api.create_snapshot(self.volume.value, template_name, description)

    def get_template(self, snapshot_id: str) -> openstack_types.SnapshotInfo:
        """
        Checks current state of a template (an snapshot)
        """
        return self.api.get_snapshot_info(snapshot_id)

    def deploy_from_template(self, name: str, snapshot_id: str) -> openstack_types.ServerInfo:
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
            security_groups_names=self.security_groups.value,
        )

    def is_avaliable(self) -> bool:
        return self.provider().is_available()
