# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.U.
# All rights reserved.
#
'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

from uds.core import types
from uds.core.services.generics.dynamic.userservice import DynamicUserService
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OpenshiftService
    from .publication import OpenshiftTemplatePublication

logger = logging.getLogger(__name__)


class OpenshiftUserService(DynamicUserService, autoserializable.AutoSerializable):
    '''
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing vmware deployments (user machines in this case) is here.

    '''

    # Due to Openshift not providing on early stage the id of the instance, we need to wait until the name is created
    # before destroying it, so we can find the instance by name.
    wait_until_finish_to_destroy: typing.ClassVar[bool] = True

    _waiting_name = autoserializable.BoolField(default=False)

    # Custom queue
    _create_queue = [
        types.services.Operation.INITIALIZE,  # Used in base class to remove duplicates
        types.services.Operation.CREATE,  # Creating already starts the instance
        # Starts the instance. If we include this, we will force to wait for the instance to be running
        # Note that while deploying, the instance is IN FACT already running, so we must not include this
        # becoase the actor could call us before we are "ready"
        # types.services.Operation.START,
        types.services.Operation.FINISH,
    ]
    _create_queue_l1_cache = [
        types.services.Operation.INITIALIZE,
        types.services.Operation.CREATE,
        # types.services.Operation.START,
        types.services.Operation.FINISH,
    ]
    _create_queue_l2_cache = [
        types.services.Operation.INITIALIZE,
        types.services.Operation.CREATE,
        types.services.Operation.WAIT,
        types.services.Operation.SUSPEND,
        types.services.Operation.FINISH,
    ]

    def _vm_name(self) -> str:
        """
        Returns the name of the VM, which is the same as the user service name
        """
        return f'UDS-Instance-{self._name}'

    def service(self) -> 'OpenshiftService':
        return typing.cast('OpenshiftService', super().service())

    def publication(self) -> 'OpenshiftTemplatePublication':
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OpenshiftTemplatePublication', pub)

    def op_create(self) -> None:
        """
        Deploys a machine from template for user/cache
        """
        # We need to wait for the name te be created, but don't want to loose the _name
        self._waiting_name = True
        instance_info = self.service().api.get_vm_info(self.publication().get_template_id())
        if instance_info.status.is_cloning():
            self.retry_later()
        elif not instance_info.status.is_cloneable():
            self.error(
                f'Instance {self.service().template.value} is not cloneable, status: {instance_info.status}'
            )
        else:
            # Note that name was created by DynamicPublication on "Initialize" operation
            self.service().api.clone_instance(
                instance_info.id,
                self._vm_name(),
            )

    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for a user or cache, robust and delegando a OpenshiftClient.
        """
        if self._waiting_name:
            # Buscar la VM clonada por nombre usando enumerate_instances
            vms = self.service().api.enumerate_instances()
            found = [vm for vm in vms if vm.get('metadata', {}).get('name') == self._vm_name()]
            if not found:
                return types.states.TaskState.RUNNING
            self._vmid = found[0].get('metadata', {}).get('uid', '')
            self._waiting_name = False

        instance = self.service().api.get_vm_info(self._vmid)
        if not instance.interfaces or getattr(instance.interfaces[0], 'mac_address', '') == '':
            return types.states.TaskState.RUNNING
        return types.states.TaskState.FINISHED

    # In fact, we probably don't need to check task status, but this way we can include the error
    def op_start_checker(self) -> types.states.TaskState:
        """
        Checks if machine has started
        """
        if self.service().api.get_vm_info(self._vmid).status.is_running():
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

    def op_stop_checker(self) -> types.states.TaskState:
        """
        Checks if machine has stopped
        """
        instance = self.service().api.get_vm_info(self._vmid)
        if (
            instance.status.is_stopped() or instance.status.is_provisioning()
        ):  # Provisioning means it's not running
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING
