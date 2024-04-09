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

from django.utils.translation import gettext_noop as _

from uds.core import types
from uds.core.services.generics.fixed.service import FixedService
from uds.core.ui import gui
from uds.core.util import log

from . import helpers
from .deployment_fixed import OpenStackUserServiceFixed

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .openstack import openstack_client

    from .provider import OpenStackProvider
    from .provider_legacy import OpenStackProviderLegacy

    AnyOpenStackProvider: typing.TypeAlias = typing.Union[OpenStackProvider, OpenStackProviderLegacy]

logger = logging.getLogger(__name__)


class OpenStackServiceFixed(FixedService):  # pylint: disable=too-many-public-methods
    """
    OpenStack fixed machines service.
    """

    type_name = _('OpenStack Fixed Machines')
    type_type = 'OpenStackFixedService'
    type_description = _('OpenStack Services based on fixed machines.')
    icon_file = 'openstack.png'

    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = None
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OpenStackUserServiceFixed

    allowed_protocols = types.transports.Protocol.generic_vdi()
    services_type_provided = types.services.ServiceType.VDI

    # Gui
    token = FixedService.token

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
            'callback_name': 'osGetMachines',
            'function': helpers.get_machines,
            'parameters': ['prov_uuid', 'project', 'region'],
        },
        tooltip=_('Project for this service'),
        required=True,
        readonly=True,
    )

    machines = FixedService.machines
    randomize = FixedService.randomize

    prov_uuid = gui.HiddenField()

    _api: typing.Optional['openstack_client.OpenstackClient'] = None

    @property
    def api(self) -> 'openstack_client.OpenstackClient':
        if not self._api:
            self._api = self.provider().api(projectid=self.project.value, region=self.region.value)

        return self._api

    # Uses default FixedService.initialize

    def init_gui(self) -> None:
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

    def provider(self) -> 'AnyOpenStackProvider':
        return typing.cast('AnyOpenStackProvider', super().provider())

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        # Obtain machines names and ids for asignables
        servers = {
            server.id: server.name for server in self.api.list_servers() if not server.name.startswith('UDS-')
        }

        with self._assigned_access() as assigned_servers:
            return [
                gui.choice_item(k, servers[k])
                for k in self.machines.as_list()
                if k not in assigned_servers
                and k in servers  # Only machines not assigned, and that exists on provider will be available
            ]

    def get_and_assign(self) -> str:
        found_vmid: typing.Optional[str] = None
        try:
            with self._assigned_access() as assigned:
                for checking_vmid in self.sorted_assignables_list():
                    if checking_vmid not in assigned:  # Not already assigned
                        try:
                            # Invoke to check it exists, do not need to store the result
                            if self.api.get_server(checking_vmid).status.is_lost():
                                raise Exception('Machine not found')  # Simply translate is_lost to an exception
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
                    assigned.add(found_vmid)
        except Exception as e:  #
            logger.debug('Error getting machine: %s', e)
            raise Exception('No machine available')

        if not found_vmid:
            raise Exception('All machines from list already assigned.')

        return found_vmid

    def get_first_network_mac(self, vmid: str) -> str:
        return self.api.get_server(vmid).addresses[0].mac

    def get_guest_ip_address(self, vmid: str) -> str:
        return self.api.get_server(vmid).addresses[0].ip

    def get_name(self, vmid: str) -> str:
        return self.api.get_server(vmid).name

    def remove_and_free(self, vmid: str) -> types.states.TaskState:
        try:
            with self._assigned_access() as assigned:
                assigned.remove(vmid)
            return types.states.TaskState.FINISHED
        except Exception as e:
            logger.warning('Cound not save assigned machines on fixed pool: %s', e)
            raise
