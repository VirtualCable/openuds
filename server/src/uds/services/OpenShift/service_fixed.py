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

from .deployment_fixed import OpenshiftUserServiceFixed

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .openshift import client
    from .provider import OpenshiftProvider
    from uds.core.services.generics.fixed.userservice import FixedUserService


logger = logging.getLogger(__name__)


class OpenshiftServiceFixed(FixedService):  # pylint: disable=too-many-public-methods
    """
    OpenStack fixed machines service.
    """

    type_name = _('Fixed Instances Pool')
    type_type = 'OpenshiftFixedService'
    type_description = _('This service provides access to a fixed group of selected instances on Openshift')
    icon_file = 'service.png'

    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = None
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OpenshiftUserServiceFixed

    allowed_protocols = types.transports.Protocol.generic_vdi()
    services_type_provided = types.services.ServiceType.VDI

    # Gui
    token = FixedService.token

    on_logout = gui.ChoiceField(
        label=_('After logout'),
        order=40,
        default='0',
        tooltip=_('Select the action to be performed after the user logs out.'),
        tab=types.ui.Tab.MACHINE,
        choices=[
            gui.choice_item('no', _('Do Nothing')),
            gui.choice_item('stop', _('Stop Machine')),
        ],
    )

    machines = FixedService.machines
    randomize = FixedService.randomize

    maintain_on_error = FixedService.maintain_on_error

    prov_uuid = gui.HiddenField()

    @property
    def api(self) -> 'client.OpenshiftClient':
        return self.provider().api

    # Uses default FixedService.initialize

    
    def init_gui(self) -> None:
        self.prov_uuid.value = self.provider().get_uuid()

        self.machines.set_choices(
            [
                gui.choice_item(str(machine.metadata.uid), f'{machine.metadata.name} ({machine.metadata.namespace})')
                for machine in self.provider().api.list_vms()
                if not machine.metadata.name.startswith('UDS-')
            ]
        )

    def provider(self) -> 'OpenshiftProvider':
        return typing.cast('OpenshiftProvider', super().provider())

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        # Obtain machines names and ids for asignables
        servers = {}
        vm_items = self.api.enumerate_instances()
        for vm in vm_items:
            name = vm.get('metadata', {}).get('name', 'UNKNOWN')
            namespace = vm.get('metadata', {}).get('namespace', '')
            # Exclude templates whose name starts with 'UDS-'
            if name.startswith('UDS-'):
                continue
            # Show namespace if not default
            label = f"{name} ({namespace})" if namespace and namespace != 'default' else name
            servers[name] = label

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
                            self.api.get_vm_info(
                                int(checking_vmid)
                            )  # Will raise OpenshiftDoesNotExists if not found
                            found_vmid = checking_vmid
                            break
                        except Exception:  # Notifies on log, but skipt it
                            self.provider().do_log(
                                types.log.LogLevel.WARNING, 'Machine {} not accesible'.format(found_vmid)
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

    def snapshot_recovery(self, userservice_instance: 'FixedUserService') -> None:
        """
        In fact, we do not support snaphots, but will use this to stop machine after logout if requested
        """
        if self.on_logout.value == 'stop':
            vmid = userservice_instance._vmid
            if self.api.get_vm_info(vmid).status.is_running():
                userservice_instance._queue.insert(0, types.services.Operation.NOP)
                userservice_instance._queue.insert(1, types.services.Operation.SHUTDOWN)
                self.do_log(types.log.LogLevel.INFO, f'Stopping machine {vmid} after logout')

    def get_mac(self, vmid: str) -> str:
        # No mac on openshift instances, return ip instead
        return self.api.get_vm_info(vmid).validate().interfaces[0].mac_address if vmid else ''

    def get_ip(self, vmid: str) -> str:
        return self.api.get_vm_info(vmid).validate().interfaces[0].ip_address if vmid else ''

    def get_name(self, vmid: str) -> str:
        return self.api.get_vm_info(vmid).validate().name

    def remove_and_free(self, vmid: str) -> types.states.TaskState:
        try:
            with self._assigned_access() as assigned:
                assigned.remove(vmid)
            return types.states.TaskState.FINISHED
        except Exception as e:
            logger.warning('Cound not save assigned machines on fixed pool: %s', e)
            raise
