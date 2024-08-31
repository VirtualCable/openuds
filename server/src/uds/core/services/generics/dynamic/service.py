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
import collections.abc
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core import services, types
from uds.core.ui import gui
from uds.core.util import fields, validators
from uds.workers.deferred_deletion import DeferredDeletionWorker

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .userservice import DynamicUserService
    from .publication import DynamicPublication

logger = logging.getLogger(__name__)


class DynamicService(services.Service, abc.ABC):  # pylint: disable=too-many-public-methods
    """
    Proxmox fixed machines service.
    """

    is_base: typing.ClassVar[bool] = True  # This is a base service, not a final one

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_osmanager = False  # If the service needs a s.o. manager (managers are related to agents provided by services, i.e. virtual machines with agent)

    must_stop_before_deletion = True  # If the service must be stopped before deletion    

    # Gui remplates, to be "incorporated" by inherited classes if needed
    base_machine = gui.ChoiceField(
        label=_('Base Machine'),
        order=30,
        tooltip=_('Base machine for this service'),
        required=True,
        tab=types.ui.Tab.MACHINE,
        old_field_name='machine',
    )

    basename = fields.basename_field(order=38, tab=types.ui.Tab.MACHINE)
    lenname = fields.lenname_field(order=39, tab=types.ui.Tab.MACHINE)

    remove_duplicates = fields.remove_duplicates_field(
        order=102,
        tab=types.ui.Tab.ADVANCED,
    )
    maintain_on_error = fields.maintain_on_error_field(
        order=103,
        tab=types.ui.Tab.ADVANCED,
    )
    try_soft_shutdown = fields.soft_shutdown_field(
        order=104,
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
            validators.validate_basename(self.basename.value, self.lenname.value)

    def get_basename(self) -> str:
        return self.basename.value

    def get_lenname(self) -> int:
        return self.lenname.value

    def sanitized_name(self, name: str) -> str:
        """
        Sanitize machine name
        Override it to provide a custom name sanitizer
        """
        return name

    # overridable, but not needed if no remove_duplicates is used
    def find_duplicates(self, name: str, mac: str) -> collections.abc.Iterable[str]:
        """
        Checks if a machine with the same name or mac exists
        Returns the list with the vmids of the duplicated machines

        Args:
            name: Name of the machine
            mac: Mac of the machine

        Returns:
            List of duplicated machines

        Note:
            Maybe we can only check name or mac, or both, depending on the service
            This method must be be provided if the field remove_duplicates is used
            If not, will raise a NotImplementedError
        """
        raise NotImplementedError(f'{self.__class__}: find_duplicates must be implemented if remove_duplicates is used!')

    @typing.final
    def perform_find_duplicates(self, name: str, mac: str) -> collections.abc.Iterable[str]:
        """
        Checks if a machine with the same name or mac exists
        Returns the list with the vmids of the duplicated machines

        Args:
            name: Name of the machine
            mac: Mac of the machine

        Returns:
            List of duplicated machines

        Note:
            Maybe we can only check name or mac, or both, depending on the service
        """
        if self.has_field('remove_duplicates') and self.remove_duplicates.value:
            return self.find_duplicates(name, mac)

        # Not removing duplicates, so no duplicates
        return []

    @abc.abstractmethod
    def get_ip(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> str:
        """
        Returns the ip of the machine
        If cannot be obtained, MUST raise an exception
        """
        ...

    @abc.abstractmethod
    def get_mac(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> str:
        """
        Returns the mac of the machine
        If cannot be obtained, MUST raise an exception
        Note:
           vmid can be '' if we are requesting a new mac (on some services, where UDS generate the machines MAC)
           If the service does not support this, it can raise an exception
        """
        ...

    @abc.abstractmethod
    def is_running(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> bool:
        """
        Returns if the machine is ready and running
        """
        ...

    @abc.abstractmethod
    def start(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        """
        Starts the machine
        Returns None. If a task is needed for anything, use the caller_instance to notify
        """
        ...

    @abc.abstractmethod
    def stop(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        """
        Stops the machine
        Returns None. If a task is needed for anything, use the caller_instance to notify
        """
        ...

    def shutdown(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        """
        Shutdowns the machine.  Defaults to stop
        Returns None. If a task is needed for anything, use the caller_instance to notify
        """
        return self.stop(caller_instance, vmid)

    def reset(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        """
        Resets the machine
        Returns None. If a task is needed for anything, use the caller_instance to notify
        """
        # Default is to stop "hard"
        return self.stop(caller_instance, vmid)
    
    def delete(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> None:
        """
        Removes the machine, or queues it for removal, or whatever :)
        Use the caller_instance to notify anything if needed, or to identify caller
        """
        # Store the deletion has started for future reference
        self.set_deleting_state(vmid)
            
        DeferredDeletionWorker.add(self, vmid)

    # Method for deferred deletion
    # Note the lack of "caller_instance" parameter, this is because the deletion is deferred and
    # the caller instance could be already deleted
    @abc.abstractmethod
    def execute_delete(self, vmid: str) -> None:
        """
        Executes the deferred deletion of a machine (normally, call the delete method of the api)
        This is make abstract to force the implementation of this method, even if not used because
        you provided a custom delete method, but better to have it implemented
        """
        ...
        
    def is_deleted(self, vmid: str) -> bool:
        """
        Checks if the deferred deletion of a machine is done
        Default implementation is return True always
        """
        return True
    
    def notify_deleted(self, vmid: str) -> None:
        """
        Called when the deferred deletion has been done
        """
        # Remove the deletion started flag
        with self.storage.as_dict() as storage:
            del storage[f'deleting_{vmid}']
            
    def set_deleting_state(self, vmid: str) -> None:
        """
        Marks a machine as deleting
        """
        with self.storage.as_dict() as storage:
            # Store deleting vmid
            storage[f'deleting_{vmid}'] = True
            
    def check_deleting_status(self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str) -> bool:
        """
        Checks if the deferred deletion of a machine is running
        Default implementation is return False always
        """
        with self.storage.as_dict() as storage:
            return f'deleting_{vmid}' in storage

    def should_maintain_on_error(self) -> bool:
        if self.has_field('maintain_on_error'):  # If has been defined on own class...
            return self.maintain_on_error.value
        return False

    def allows_errored_userservice_cleanup(self) -> bool:
        """
        Returns if this service can clean errored services. This is used to check if a service can be cleaned
        from the stuck cleaner job, for example.
        """
        return not self.should_maintain_on_error()

    def should_try_soft_shutdown(self) -> bool:
        if self.has_field('try_soft_shutdown'):
            return self.try_soft_shutdown.value
        return False
