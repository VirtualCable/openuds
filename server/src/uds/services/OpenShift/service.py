# -*- coding: utf-8 -*-

#
# Copyright (c) 2018-2019 Virtual Cable S.L.
# All rights reserved.
#

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import collections.abc
import typing

from django.utils.translation import gettext_lazy as _

from uds.core import types
from uds.core.services.generics.dynamic.publication import DynamicPublication
from uds.core.services.generics.dynamic.service import DynamicService
from uds.core.services.generics.dynamic.userservice import DynamicUserService
from uds.core.ui import gui
from uds.core.util import validators, fields

from .publication import OpenshiftTemplatePublication

from .deployment import OpenshiftUserService
from .openshift import exceptions as morph_exceptions

logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OpenshiftProvider
    from .openshift.client import OpenshiftClient


class OpenshiftService(DynamicService):
    type_name = _('VM clone')
    type_type = 'OpenshiftFullService'
    type_description = _('This service provides access to cloned VMs on Openshift')
    icon_file = 'service.png'

    uses_cache = True  # Cache are running machine awaiting to be assigned
    cache_tooltip = _('Number of desired VMs to keep running waiting for an user')
    uses_cache_l2 = True  # L2 Cache are running machines in suspended state
    cache_tooltip_l2 = _('Number of desired VMs to keep stopped waiting for use')
    needs_osmanager = True  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    can_reset = True

    must_stop_before_deletion = False

    # Deployments & deploys
    publication_type = OpenshiftTemplatePublication
    user_service_type = OpenshiftUserService

    services_type_provided = types.services.ServiceType.VDI

    template = gui.ChoiceField(
        order=3,
        label=_('Template VM'),
        tooltip=_('Template to use for VMs'),
        required=True,
    )

    basename = fields.basename_field(order=4)
    lenname = fields.lenname_field(order=5)

    try_soft_shutdown = DynamicService.try_soft_shutdown  # Before deleting, try a soft shutdown
    maintain_on_error = DynamicService.maintain_on_error  # If an error occurs, maintain the service
    put_back_to_cache = DynamicService.put_back_to_cache
    
    publication_timeout = gui.NumericField(
        order=6,
        label=_('Publication Timeout'),
        tooltip=_('Timeout in seconds to wait for the publication to be visible'),
        default=120,
        required=True,
        length=5,
        tab=types.ui.Tab.ADVANCED,
    )

    prov_uuid = gui.HiddenField(value=None)


    _cached_api: typing.Optional['OpenshiftClient'] = None #! DUDA

    @property
    def api(self) -> 'OpenshiftClient':
        if self._cached_api is None:
            self._cached_api = self.provider().api
        return self._cached_api

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        Initialize the service with the given values.
        """
        if not values:
            return

        self.basename.value = validators.validate_basename(self.basename.value, length=self.lenname.as_int())

    def init_gui(self) -> None:
        """
        Initialize the GUI elements for the service.
        """
        self.prov_uuid.value = self.provider().get_uuid()

        self.template.set_choices(
            [
                gui.choice_item(str(template.name), f'{template.name} ({template.namespace})')
                for template in self.provider().api.list_vms()
                if template.is_usable() and not template.name.startswith('UDS-')
            ]
        )

    def provider(self) -> 'OpenshiftProvider':
        """
        Get the Openshift provider.
        """
        return typing.cast('OpenshiftProvider', super().provider())

    def get_basename(self) -> str:
        """Returns configured basename for machines"""
        return self.basename.value

    def get_lenname(self) -> int:
        """Returns configured length for machine names"""
        return self.lenname.as_int()
    
    # Utility
    def sanitized_name(self, name: str) -> str:
        """Sanitizes a name for Azure (only allowed chars)

        Args:
            name (str): Name to sanitize

        Returns:
            str: Sanitized name
        """
        return self.provider().sanitized_name(name)

    def find_duplicates(self, name: str, mac: str) -> collections.abc.Iterable[str]:
        """
        Finds duplicate VMs by name.
        """
        for vm in self.api.list_vms():
            if vm.name == name:
                yield vm.name

    def is_available(self) -> bool:
        """
        Checks if provider is available
        """
        return self.provider().is_available()

    def get_ip(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str #! DUDA
    ) -> str:
        """
        Returns the ip of the machine
        If cannot be obtained, MUST raise an exception
        """
        logger.debug('Getting IP for VM ID: %s', vmid)

        vmi_info = self.api.get_vm_instance_info(vmid)
        if not vmi_info or not vmi_info.interfaces:
            raise morph_exceptions.OpenshiftNotFoundError(f'No interfaces found for VM {vmid}')
        return vmi_info.interfaces[0].ip_address

    def get_mac(
        self,
        caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], #! DUDA
        vmid: str,
        *,
        for_unique_id: bool = False,
    ) -> str:
        """
        Returns the mac of the machine
        If cannot be obtained, MUST raise an exception
        Note:
           vmid can be '' if we are requesting a new mac (on some services, where UDS generate the machines MAC)
           If the service does not support this, it can raise an exception
        """
        if vmid == '':
            return ''
        logger.debug('Getting MAC for VM ID: %s', vmid)
        vmi_info = self.api.get_vm_instance_info(vmid)
        if not vmi_info or not vmi_info.interfaces:
            logger.warning(f'No interfaces found for VM {vmid}. Detalles: {vmi_info}')
            # Opcional: retornar None o string vacía según la lógica de negocio
            # return None
            raise morph_exceptions.OpenshiftNotFoundError(f'No interfaces found for VM {vmid}')
        return vmi_info.interfaces[0].mac_address

    def is_running(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str #! DUDA
    ) -> bool:
        """
        Checks if the VM instance is currently running.
        """
        vmi_info = self.api.get_vm_instance_info(vmid)
        if not vmi_info:
            return False
        # Use both status and phase to determine if running
        return (
            getattr(vmi_info.status, "name", "").lower() == "running"
            or getattr(vmi_info.phase, "name", "").lower() == "running"
        )

    def start(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str #! DUDA
    ) -> None:
        """
        Starts the machine
        Can return a task, or None if no task is returned
        """
        self.api.start_vm_instance(vmid)

    def stop(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str #! DUDA
    ) -> None:
        """
        Stops the machine
        Can return a task, or None if no task is returned
        """
        self.api.stop_vm_instance(vmid)

    def shutdown(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str #! DUDA
    ) -> None:
        """
        Shutdowns the machine, same as stop (both tries soft shutdown, it's a openshift thing)
        """
        self.api.stop_vm_instance(vmid)

    def execute_delete(self, vmid: str) -> None:
        """
        Deletes the VM
        """
        logger.debug('Deleting Openshift VM %s', vmid)
        self.api.delete_vm_instance(vmid)  # Force deletion, as we are not using soft delete

    def is_deleted(self, vmid: str) -> bool:
        """
        Checks if the VM is deleted.
        """
        try:
            self.api.get_vm_info(vmid)
        except morph_exceptions.OpenshiftNotFoundError:
            return True
        return False
