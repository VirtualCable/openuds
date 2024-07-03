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
import random  # Not for cryptographic purposes, just to randomize the assignation of machines
import abc
import contextlib
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _, gettext
from uds.core import services, types, exceptions
from uds.core.ui import gui
from uds.core.util import fields

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .userservice import FixedUserService

logger = logging.getLogger(__name__)


class FixedService(services.Service, abc.ABC):  # pylint: disable=too-many-public-methods
    """
    Proxmox fixed machines service.
    """

    is_base: typing.ClassVar[bool] = True  # This is a base service, not a final one

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_osmanager = False  # If the service needs a s.o. manager (managers are related to agents provided by services, i.e. virtual machines with agent)
    # can_reset = True
    
    # If machines has an alternate field with it, it will be used instead of "machines" field
    alternate_machines_field: typing.Optional[str] = None

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    # publication_type = None
    # : Types of deploys (services in cache and/or assigned to users)
    # Every service must have overrided FixedUserService with it's own implementation
    # so this needs to be overrided
    # user_service_type = FixedUserService

    # allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    # services_type_provided = types.services.ServiceType.VDI

    # Gui remplates, to be "incorporated" by inherited classes if needed
    token = gui.TextField(
        order=1,
        label=_('Service Token'),
        length=16,
        tooltip=_(
            'Service token that will be used by actors to communicate with service. Leave empty for persistent assignation.'
        ),
        default='',
        required=False,
        readonly=False,
    )

    machines = gui.MultiChoiceField(
        label=_("Machines"),
        order=30,
        tooltip=_('Machines for this service'),
        required=True,
        tab=types.ui.Tab.MACHINE,
        rows=10,
    )

    use_snapshots = gui.CheckBoxField(
        label=_('Use snapshots'),
        default=False,
        order=33,
        tooltip=_(
            'If active, UDS will try to create an snapshot (if one already does not exists) before accessing a machine, and restore it after usage.'
        ),
        tab=types.ui.Tab.MACHINE,
        old_field_name='useSnapshots',
    )

    # This one replaces use_snapshots, and is used to select the snapshot type (No snapshot, recover snapshot and stop machine, recover snapshot and start machine)
    snapshot_type = gui.ChoiceField(
        label=_('Snapshot type'),
        order=36,
        default='0',
        tooltip=_(
            'If active, UDS will try to create an snapshot (if one already does not exists) before accessing a machine, and restore it after usage.'
        ),
        tab=types.ui.Tab.MACHINE,
        choices=[
            gui.choice_item('no', _('No snapshot')),
            gui.choice_item('stop', _('Recover snapshot and stop machine')),
            gui.choice_item('start', _('Recover snapshot and start machine')),
        ],
    )

    # Randomize machine assignation isntead of linear
    randomize = gui.CheckBoxField(
        label=_('Randomize machine assignation'),
        order=100,
        default=True,
        tooltip=_('If active, UDS will assign machines in a random way, instead of linear'),
        tab=types.ui.Tab.ADVANCED,
    )
    maintain_on_error = fields.maintain_on_error_field(
        order=103,
        tab=types.ui.Tab.ADVANCED,
    )

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        Fixed token value, ensure we have at least one machine,
        ensure assigned machines stored values are updated acording to the machines list
        and recover userservice_limit from machines list length
        If overriden, can be called to avoid redundant code
        """
        if values:
            if not self.machines.value:
                raise exceptions.ui.ValidationError(gettext('We need at least a machine'))

            # Remove machines not in values from "assigned" set
            with self._assigned_access() as assigned_vms:
                assigned_vms &= set(self.machines.as_list())
            self.token.value = self.token.value.strip()
        # Recover userservice
        self.userservices_limit = len(self.machines.as_list())

    @contextlib.contextmanager
    def _assigned_access(self) -> typing.Iterator[set[str]]:
        with self.storage.as_dict(atomic=True) as d:
            machines: set[str] = d.get('vms', set())
            initial_machines = machines.copy()  # for comparison later
            yield machines
            # If has changed, save it
            if machines != initial_machines:
                d['vms'] = machines  # Store it

    def snapshot_creation(self, userservice_instance: 'FixedUserService') -> None:
        """
        Creates a snapshot for the machine
        """
        return

    def snapshot_recovery(self, userservice_instance: 'FixedUserService') -> None:
        """
        Removes the snapshot for the machine
        """
        return

    @abc.abstractmethod
    def get_name(self, vmid: str) -> str:
        """
        Returns the machine name for the given vmid
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_and_assign(self) -> str:
        """
        Gets automatically an assigns a machine
        Returns the id of the assigned machine, or raises an exception if no machine is available

        Note:
            This is used when deploying a machine for an user
        """
        raise NotImplementedError()

    # default implementation, should be sufficient for most cases
    def remove_and_free(self, vmid: str) -> types.states.TaskState:
        try:
            with self._assigned_access() as assigned:
                # In error situations, due to the "recover_snapshot" post runasign, the element could be already removed
                # So we need to check if it's there
                if vmid in assigned:
                    assigned.remove(vmid)
            return types.states.TaskState.FINISHED
        except Exception as e:
            logger.error('Error processing remove and free: %s', e)
            raise Exception(f'Error processing remove and free: {e} on {vmid}') from e

    def is_ready(self, vmid: str) -> bool:
        """
        Returns if the machine is ready for usage
        Defaults to True
        """
        return True
    
    def is_running(self, vmid: str) -> bool:
        """
        Returns if the machine is running
        Defaults to self.is_ready() 
        """
        return self.is_ready(vmid)

    @abc.abstractmethod
    def get_mac(self, vmid: str) -> str:
        """If no mac, return empty string
        Returns the first network mac of the machine
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_ip(self, vmid: str) -> str:
        """Returns the guest ip address of the machine"""
        raise NotImplementedError()

    @abc.abstractmethod
    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        """
        Returns a list of tuples with the id and the name of the assignables
        """
        raise NotImplementedError()

    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> types.states.TaskState:
        """
        Assigns a machine from the assignables
        Default implementation NEEDS machines field to be present!!
        """
        fixed_instance = typing.cast('FixedUserService', userservice_instance)
        machines = typing.cast(gui.MultiChoiceField, getattr(self, self.alternate_machines_field or 'machines' ))
        with self._assigned_access() as assigned_vms:
            if assignable_id not in assigned_vms and assignable_id in machines.as_list():
                assigned_vms.add(assignable_id)
                return fixed_instance.assign(assignable_id)

        return fixed_instance.error(f'{assignable_id} not available!')

    def sorted_assignables_list(self) -> list[str]:
        """
        Randomizes the assignation of machines if needed
        """
        fld_name = self.alternate_machines_field or 'machines'
        if self.has_field(fld_name) is False:
            raise ValueError(f'machines field {fld_name} not found')
        machines = typing.cast(gui.MultiChoiceField, getattr(self, fld_name))

        if hasattr(self, 'randomize') and self.randomize.value is True:
            return random.sample(machines.as_list(), len(machines.as_list()))

        return machines.as_list()

    def allows_errored_userservice_cleanup(self) -> bool:
        """
        Returns if this service can clean errored services. This is used to check if a service can be cleaned
        from the stuck cleaner job, for example.
        """
        return not self.should_maintain_on_error()

    def should_maintain_on_error(self) -> bool:
        if self.has_field('maintain_on_error'):  # If has been defined on own class...
            return self.maintain_on_error.value
        return False

    def get_token(self) -> str | None:
        if self.has_field('token') and self.token.value:
            return self.token.value
        return None