# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.
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

    # Due to Openshift not providing on early stage the id of the vm, we need to wait until the name is created
    # before destroying it, so we can find the vm by name.
    wait_until_finish_to_destroy: typing.ClassVar[bool] = True

    _waiting_name = autoserializable.BoolField(default=False)

    can_set_ip = False  # We cannot set IP on Openshift, so we disable this option in the UI

    # Custom queue
    _create_queue = [
        types.services.Operation.INITIALIZE,  # Used in base class to remove duplicates
        types.services.Operation.CREATE,  # Creating already starts the vm
        # Starts the vm. If we include this, we will force to wait for the vm to be running
        # Note that while deploying, the vm is IN FACT already running, so we must not include this
        # because the actor could call us before we are "ready"
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

    def service(self) -> 'OpenshiftService':
        """
        Get the Openshift service.
        """
        return typing.cast('OpenshiftService', super().service())

    def publication(self) -> 'OpenshiftTemplatePublication':
        """
        Get the Openshift publication.
        """
        pub = super().publication()
        if pub is None:
            raise Exception('No publication for this element!')
        return typing.cast('OpenshiftTemplatePublication', pub)

    def op_create(self) -> None:
        """
        Starts the deployment process for a user or cache, cloning the template publication.
        """
        logger.info("Starting publication process: template cloning.")
        self._waiting_name = True
        api = self.service().api
        publication_vm_name = self.publication()._name
        namespace = api.namespace
        api_url = api.api_url
        self._name = self.service().sanitized_name(self._name)

        logger.info(f"Getting template PVC/DataVolume '{publication_vm_name}'.")
        source_pvc_name, vol_type = api.get_vm_pvc_or_dv_name(api_url, namespace, publication_vm_name)
        logger.info(f"Source PVC/DataVolume: {source_pvc_name}, type: {vol_type}.")

        logger.info(f"Getting PVC size '{source_pvc_name}'.")
        size = api.get_pvc_size(api_url, namespace, source_pvc_name)
        logger.info(f"PVC size: {size}.")

        new_pvc_name = f"{self._name}-disk"

        logger.info(f"Creating new VM '{self._name}' from cloned PVC '{new_pvc_name}'.")
        ok = api.create_vm_from_pvc(
            api_url=api_url,
            namespace=namespace,
            source_vm_name=publication_vm_name,
            new_vm_name=self._name,
            new_dv_name=new_pvc_name,
            source_pvc_name=source_pvc_name,
        )
        if not ok:
            logger.error(f"Error creating VM {self._name} from cloned PVC.")
            return
        else:
            logger.info(f"VM '{self._name}' creation initiated successfully.")

    # In fact, we probably don't need to check task status, but this way we can include the error
    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks the state of a deploy for a user or cache, correctly waiting for the DataVolume and the VM.
        If the VM is not found, consider it deleted and finish the operation.
        """

        api = self.service().api
        new_pvc_name = f"{self._name}-disk"

        logger.info(f"Waiting for DataVolume '{new_pvc_name}' to be ready.")
        dv_status = api.get_datavolume_phase(new_pvc_name)
        if dv_status == 'Succeeded':
            logger.info(f"DataVolume '{new_pvc_name}' clone completed.")
        elif dv_status == 'Failed':
            logger.error(f"DataVolume clone {new_pvc_name} failed.")
            return types.states.TaskState.ERROR
        else:
            logger.info(f"Waiting for DataVolume clone {new_pvc_name}, status: {dv_status}.")
            return types.states.TaskState.RUNNING

        logger.info(f"VM '{self._name}' created successfully.")
        self._vmid = self._name  # Assign the VM identifier for future operations (deletion, etc.)
        self._waiting_name = False

        api = self.service().api
        new_dv_name = f"{self._name}-disk"

        # Wait for the DataVolume to be Succeeded
        dv_status = api.get_datavolume_phase(new_dv_name)
        if dv_status != 'Succeeded':
            return types.states.TaskState.RUNNING

        # Find the VM by name
        vm = api.get_vm_info(self._name)
        if not vm:
            # VM not found, consider it deleted and finish
            logger.info(f"VM '{self._name}' not found, considering as deleted. Finishing operation.")
            return types.states.TaskState.FINISHED

        # Check that the VM has interfaces and MAC address
        vmi = api.get_vm_info(self._name)
        if (
            not vmi
            or not getattr(vmi, 'interfaces', None)
            or getattr(vmi.interfaces[0], 'mac_address', '') == ''
        ):
            return types.states.TaskState.RUNNING
        return types.states.TaskState.FINISHED

