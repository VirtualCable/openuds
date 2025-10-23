# -*- coding: utf-8 -*-

#
# Copyright (c) 2018-2019 Virtual Cable S.L.
# All rights reserved.
#

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
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


class OpenshiftService(DynamicService):  # pylint: disable=too-many-public-methods

    # Description of service
    type_name = _('Instance clone')
    type_type = 'OpenshiftFullService'
    type_description = _('This service provides access to cloned instances on Openshift')
    icon_file = 'service.png'

    uses_cache = True  # Cache are running machine awaiting to be assigned
    cache_tooltip = _('Number of desired Instances to keep running waiting for an user')
    uses_cache_l2 = True  # L2 Cache are running machines in suspended state
    cache_tooltip_l2 = _('Number of desired Instances to keep stopped waiting for use')
    needs_osmanager = True  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    can_reset = True

    must_stop_before_deletion = False

    # Deployments & deploys
    publication_type = OpenshiftTemplatePublication
    user_service_type = OpenshiftUserService

    services_type_provided = types.services.ServiceType.VDI

    template = gui.ChoiceField(
        order=3,
        label=_('Template Instance'),
        tooltip=_('Template to use for instances'),
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


    _cached_api: typing.Optional['OpenshiftClient'] = None

    @property
    def api(self) -> 'OpenshiftClient':
        if self._cached_api is None:
            self._cached_api = self.provider().api
        return self._cached_api

    def initialize(self, values: 'types.core.ValuesType') -> None:
        if not values:
            return

        self.basename.value = validators.validate_basename(self.basename.value, length=self.lenname.as_int())

    def init_gui(self) -> None:
        self.prov_uuid.value = self.provider().get_uuid()

        vm_items = self.api.enumerate_vms()
        choices = []
        logger.debug('VMs found: %s', vm_items)
        for vm in vm_items:
            name = vm.get('metadata', {}).get('name', 'UNKNOWN')
            namespace = vm.get('metadata', {}).get('namespace', '')
            # Exclude templates whose name starts with 'UDS-'
            if name.upper().startswith('UDS-'):
                continue
            # Show namespace if not default
            label = f"{name} ({namespace})" if namespace and namespace != 'default' else name
            choices.append(gui.choice_item(name, label))
        self.template.set_choices(choices)

    def init_gui(self) -> None:
        self.prov_uuid.value = self.provider().get_uuid()

        self.template.set_choices(
            [
                gui.choice_item(str(template.metadata.uid), f'{template.metadata.name} ({template.metadata.namespace})')
                for template in self.provider().api.list_vms()
                if not template.metadata.name.startswith('UDS-')
            ]
        )

    def provider(self) -> 'OpenshiftProvider':
        return typing.cast('OpenshiftProvider', super().provider())

    def get_basename(self) -> str:
        """Returns configured basename for machines"""
        return self.basename.value

    def get_lenname(self) -> int:
        """Returns configured length for machine names"""
        return self.lenname.as_int()

    # Utility
    def sanitized_name(self, name: str) -> str:
        """Sanitizes a name for Openshift (only allowed chars)

        Args:
            name (str): Name to sanitize

        Returns:
            str: Sanitized name
        """
        return ''.join(c for c in name if c.isalnum() or c in ('-', '_', '.', ' ')).strip()

    def is_avaliable(self) -> bool:
        return self.provider().is_available()

    def get_ip(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> str:
        """
        Returns the ip of the machine
        If cannot be obtained, MUST raise an exception
        """
        return self.api.get_instance_info(vmid, force=True).validate().interfaces[0].ip_address if vmid else ''

    def get_mac(
        self,
        caller_instance: typing.Optional['DynamicUserService | DynamicPublication'],
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
        return self.api.get_instance_info(vmid, force=True).validate().interfaces[0].mac_address if vmid else ''

    def is_running(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> bool:
        vm_info = self.api.get_instance_info(vmid).validate()
        return vm_info.status.is_running()

    def start(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> None:
        """
        Starts the machine
        Can return a task, or None if no task is returned
        """
        self.api.start_instance(vmid)

    def stop(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> None:
        """
        Stops the machine
        Can return a task, or None if no task is returned
        """
        self.api.stop_instance(vmid)

    def shutdown(
        self, caller_instance: typing.Optional['DynamicUserService | DynamicPublication'], vmid: str
    ) -> None:
        """
        Shutdowns the machine, same as stop (both tries soft shutdown, it's a openshift thing)
        """
        self.api.stop_instance(vmid)

    def execute_delete(self, vmid: str) -> None:
        """
        Deletes the vm
        """
        logger.debug('Deleting Openshift instance %s', vmid)
        self.api.delete_instance(vmid, force=True)  # Force deletion, as we are not using soft delete

    def is_deleted(self, vmid: str) -> bool:
        try:
            self.api.get_instance_info(vmid)
        except morph_exceptions.OpenshiftNotFoundError:
            return True
        return False
