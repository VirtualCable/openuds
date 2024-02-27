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
import abc
import logging
import re
import typing
import collections.abc

from django.utils.translation import gettext_noop as _, gettext
from uds.core import services, types, consts, exceptions
from uds.core.ui import gui
from uds.core.util import validators, log
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached
from uds.core.workers import initialize

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds import models
    from .fixed_userservice import FixedUserService

logger = logging.getLogger(__name__)


class FixedService(services.Service, abc.ABC):  # pylint: disable=too-many-public-methods
    """
    Proxmox fixed machines service.
    """

    is_base: typing.ClassVar[bool] = True  # This is a base service, not a final one

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_osmanager = False  # If the service needs a s.o. manager (managers are related to agents provided by services, i.e. virtual machines with agent)
    must_assign_manually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service
    # can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    # publication_type = None
    # : Types of deploys (services in cache and/or assigned to users)
    # Ensure to provide this on inherited classes
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

    use_snapshots = gui.CheckBoxField(
        label=_('Use snapshots'),
        default=False,
        order=22,
        tooltip=_('If active, UDS will try to create an snapshot (if one already does not exists) before accessing a machine, and restore it after usage.'),
        tab=_('Machines'),
        old_field_name='useSnapshots',
    )
    
    # This one replaces use_snapshots, and is used to select the snapshot type (No snapshot, recover snapshot and stop machine, recover snapshot and start machine)
    snapshot_type = gui.ChoiceField(
        label=_('Snapshot type'),
        order=22,
        default='0',
        tooltip=_('If active, UDS will try to create an snapshot (if one already does not exists) before accessing a machine, and restore it after usage.'),
        tab=_('Machines'),
        choices=[
            gui.choice_item('no', _('No snapshot')),
            gui.choice_item('stop', _('Recover snapshot and stop machine')),
            gui.choice_item('start', _('Recover snapshot and start machine')),
        ],
    )   

    # Keep name as "machine" so we can use VCHelpers.getMachines
    machines = gui.MultiChoiceField(
        label=_("Machines"),
        order=21,
        tooltip=_('Machines for this service'),
        required=True,
        tab=_('Machines'),
        rows=10,
    )

    def _get_assigned_machines(self) -> typing.Set[str]:
        vals = self.storage.get_unpickle('vms')
        logger.debug('Got storage VMS: %s', vals)
        return vals or set()

    def _save_assigned_machines(self, vals: typing.Set[str]) -> None:
        logger.debug('Saving storage VMS: %s', vals)
        self.storage.put_pickle('vms', vals)

    def process_snapshot(self, remove: bool, userservice_instance: 'FixedUserService') -> None:
        """
        Processes snapshot creation if needed for this service
        Defaults to do nothing

        Args:
            remove (bool): If True, called from "remove" action, else called from "create" action

        returns:
            None
            If needs to notify an error, raise an exception
        """
        return

    @abc.abstractmethod
    def get_machine_name(self, vmid: str) -> str:
        """
        Returns the machine name for the given vmid
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_and_assign_machine(self) -> str:
        """
        Gets automatically an assigns a machine
        Returns the id of the assigned machine
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def remove_and_free_machine(self, vmid: str) -> str:
        """
        Removes and frees a machine
        Returns an state (State.FINISHED is nothing to do left)
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_first_network_mac(self, vmid: str) -> str:
        """If no mac, return empty string
        Returns the first network mac of the machine
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_guest_ip_address(self, vmid: str) -> str:
        """Returns the guest ip address of the machine
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        """
        Returns a list of tuples with the id and the name of the assignables
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def assign_from_assignables(
        self, assignable_id: str, user: 'models.User', userservice_instance: 'services.UserService'
    ) -> types.states.TaskState:
        """
        Assigns a machine from the assignables
        """
        raise NotImplementedError()
