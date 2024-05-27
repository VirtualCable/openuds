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
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import services, types
from uds.core.services.generics.fixed.service import FixedService
from uds.core.services.generics.fixed.userservice import FixedUserService
from uds.core.ui import gui

from . import helpers
from .deployment_fixed import XenFixedUserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

    from .provider import XenProvider

logger = logging.getLogger(__name__)


class XenFixedService(FixedService):  # pylint: disable=too-many-public-methods
    """
    Represents a Xen service based on fixed machines.
    This service requires the qemu agent to be installed on the machines.
    """

    type_name = _('Xen Fixed Machines')
    type_type = 'XenFixedService'
    type_description = _('Xen Services based on fixed machines. Needs xen agent installed on machines.')
    icon_file = 'service.png'

    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = None
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = XenFixedUserService

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI

    # Gui
    token = FixedService.token

    folder = gui.ChoiceField(
        label=_("Folder"),
        readonly=False,
        order=20,
        fills={
            'callback_name': 'xmFillMachinesFromFolder',
            'function': helpers.get_machines,
            'parameters': ['prov_uuid', 'folder'],
        },
        tooltip=_('Folder containing base machines'),
        required=True,
        tab=types.ui.Tab.MACHINE,
        old_field_name='resourcePool',
    )
    machines = FixedService.machines
    use_snapshots = FixedService.use_snapshots
    randomize = FixedService.randomize

    prov_uuid = gui.HiddenField(value=None)

    # Uses default FixedService.initialize

    def init_gui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.prov_uuid.value = self.provider().get_uuid()
        with self.provider().get_connection() as api:
            self.folder.set_choices([gui.choice_item(folder, folder) for folder in api.list_folders()])

    def provider(self) -> 'XenProvider':
        return typing.cast('XenProvider', super().provider())

    def start_vm(self, vmid: str) -> str:
        """
        Tries to start a machine. No check is done, it is simply requested to Xen.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        with self.provider().get_connection() as api:
            if api.get_vm_info(vmid).power_state.is_running():
                return ''  # Already running
            return api.start_vm(vmid)

    def stop_vm(self, vmid: str) -> str:
        """
        Tries to stop a machine. No check is done, it is simply requested to Xen

        Args:
            machineId: Id of the machine

        Returns:
        """
        with self.provider().get_connection() as api:
            if api.get_vm_info(vmid).power_state.is_running():
                return api.stop_vm(vmid)

        return ''  # Already stopped

    def reset_vm(self, vmid: str) -> str:
        """
        Tries to stop a machine. No check is done, it is simply requested to Xen

        Args:
            vmid: Id of the machine

        Returns:
        """
        with self.provider().get_connection() as api:
            if api.get_vm_info(vmid).power_state.is_running():
                return api.reset_vm(vmid)

        return ''  # Already stopped, no reset needed

    def shutdown_vm(self, vmid: str) -> str:
        with self.provider().get_connection() as api:
            if api.get_vm_info(vmid).power_state.is_running():
                return api.shutdown_vm(vmid)

        return ''  # Already stopped

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        # Obtain machines names and ids for asignables
        with self.provider().get_connection() as api:
            vms: dict[str, str] = {
                machine.opaque_ref: machine.name for machine in api.list_vms_in_folder(self.folder.value)
            }

            with self._assigned_access() as assigned_vms:
                return [
                    gui.choice_item(k, vms[k])
                    for k in self.machines.as_list()
                    if k not in assigned_vms
                    and k in vms  # Only machines not assigned, and that exists on provider will be available
                ]

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> types.states.TaskState:
        xen_userservice_instance = typing.cast(XenFixedUserService, userservice_instance)
        with self._assigned_access() as assigned_vms:
            if assignable_id not in assigned_vms:
                assigned_vms.add(assignable_id)
                return xen_userservice_instance.assign(assignable_id)

        return xen_userservice_instance.error('VM not available!')

    def snapshot_creation(self, userservice_instance: FixedUserService) -> None:
        userservice_instance = typing.cast(XenFixedUserService, userservice_instance)
        with self.provider().get_connection() as api:
            if self.use_snapshots.as_bool():
                vmid = userservice_instance._vmid

                snapshots = api.list_snapshots(
                    vmid, full_info=False
                )  # Only need ids, to check if there is any snapshot

                logger.debug('Using snapshots')
                # If no snapshot exists for this vm, try to create one for it on background
                # Lauch an snapshot. We will not wait for it to finish, but instead let it run "as is"
                try:
                    if not snapshots:  # No snapshot, try to create one
                        logger.debug('Not current snapshot')
                        # We don't need the snapshot nor the task, will simply restore to newer snapshot on remove
                        api.create_snapshot(
                            vmid,
                            name='UDS Snapshot',
                        )
                except Exception as e:
                    self.do_log(
                        types.log.LogLevel.WARNING, 'Could not create SNAPSHOT for this VM. ({})'.format(e)
                    )

    def snapshot_recovery(self, userservice_instance: FixedUserService) -> None:
        userservice_instance = typing.cast(XenFixedUserService, userservice_instance)
        with self.provider().get_connection() as api:
            if self.use_snapshots.as_bool():
                vmid = userservice_instance._vmid

                snapshots = api.list_snapshots(vmid, full_info=True)  # We need full info to restore it

                if snapshots:
                    try:
                        # 0 is most recent snapshot
                        userservice_instance._task = api.restore_snapshot(snapshots[0].opaque_ref)
                    except Exception as e:
                        self.do_log(
                            types.log.LogLevel.WARNING, 'Could not restore SNAPSHOT for this VM. ({})'.format(e)
                        )

    def get_and_assign(self) -> str:
        found_vmid: typing.Optional[str] = None
        with self.provider().get_connection() as api:
            with self._assigned_access() as assigned_vms:
                try:
                    for checking_vmid in self.sorted_assignables_list():
                        if checking_vmid not in assigned_vms:  # Not assigned
                            # Check that the machine exists...
                            try:
                                api.get_vm_info(checking_vmid)  # Will raise an exception if not exists
                                found_vmid = checking_vmid
                                break
                            except Exception:  # Notifies on log, but skipt it
                                self.provider().do_log(
                                    types.log.LogLevel.WARNING, 'Machine {} not accesible'.format(found_vmid)
                                )
                                logger.warning(
                                    'The service has machines that cannot be checked on xen (connection error or machine has been deleted): %s',
                                    found_vmid,
                                )

                    if found_vmid:
                        assigned_vms.add(str(found_vmid))
                except Exception:  #
                    raise Exception('No machine available')

        if not found_vmid:
            raise Exception('All machines from list already assigned.')

        return str(found_vmid)

    def get_mac(self, vmid: str) -> str:
        with self.provider().get_connection() as conn:
            return conn.get_first_mac(vmid)

    def get_ip(self, vmid: str) -> str:
        with self.provider().get_connection() as conn:
            return conn.get_first_ip(vmid)

    def get_name(self, vmid: str) -> str:
        with self.provider().get_connection() as conn:
            return conn.get_vm_info(vmid).name

    # default remove_and_free is ok

    def is_ready(self, vmid: str) -> bool:
        with self.provider().get_connection() as conn:
            return conn.get_vm_info(vmid).power_state.is_running()
