# -*- coding: utf-8 -*-
#
# Copyright (c) 2019-2024 Virtual Cable S.L.U.
# All rights reserved.
#
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core.types.states import TaskState
from uds.core.util import autoserializable
from uds.core import types

from uds.core.services.generics.dynamic.publication import DynamicPublication
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OpenshiftService

logger = logging.getLogger(__name__)

class OpenshiftTemplatePublication(DynamicPublication, autoserializable.AutoSerializable):
    """
    This class provides the publication of a OpenshiftService
    """

    # Openshift, due to the way a machine is created (we have to search for the name of the machine
    # after the clone operation), needs to wait until the machine is created before destroying it.
    wait_until_finish_to_destroy: typing.ClassVar[bool] = True

    _waiting_name = autoserializable.BoolField(default=False)

    def service(self) -> 'OpenshiftService':
        """
        Get the Openshift service.
        """
        return typing.cast('OpenshiftService', super().service())

    def op_create(self) -> None:
        """
        Starts the deployment process for a user or cache, cloning the template publication.
        """
        logger.info("Starting publication process: template cloning.")
        self._waiting_name = True
        api = self.service().api
        template_vm_name = self.service().template.value
        namespace = api.namespace
        api_url = api.api_url

        logger.info(f"Getting template PVC/DataVolume '{template_vm_name}'.")
        source_pvc_name, vol_type = api.get_vm_pvc_or_dv_name(api_url, namespace, template_vm_name)  # type: ignore
        logger.info(f"Source PVC/DataVolume: {source_pvc_name}, type: {vol_type}.")

        logger.info(f"Getting PVC size '{source_pvc_name}'.")
        size = api.get_pvc_size(api_url, namespace, source_pvc_name)
        logger.info(f"PVC size: {size}.")

        self._name = self.service().sanitized_name(self._name)
        self._waiting_name = False

        new_pvc_name = f"{self._name}-disk"
        
        logger.info(f"Creating new VM '{self._name}' from cloned PVC '{new_pvc_name}'.")
        ok = api.create_vm_from_pvc(
            api_url=api_url,
            namespace=namespace,
            source_vm_name=template_vm_name,
            new_vm_name=self._name,
            new_dv_name=new_pvc_name,
            source_pvc_name=source_pvc_name,
        )
        if not ok:
            logger.error(f"Error creating VM {self._name} from cloned PVC.")
            self._error(f"Error creating VM {self._name} from cloned PVC")
            return
        else:
            logger.info(f"VM '{self._name}' creation initiated successfully.")

        logger.info(f"Waiting for DataVolume '{new_pvc_name}' to be ready.")
        if not api.wait_for_datavolume_clone_progress(api_url, namespace, new_pvc_name):
            logger.error(f"Timeout waiting for DataVolume clone {new_pvc_name}.")
            self._error(f"Timeout waiting for DataVolume clone {new_pvc_name}")
            return

        logger.info(f"VM '{self._name}' created successfully.")
        self._vmid = self._name  # Assign the VM identifier for future operations (deletion, etc.)
        api.stop_vm_instance(self._name)

    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks if the create operation has been completed successfully.
        The publication is considered finished when the VM is available.
        """
        # If we are still waiting, we try to get the VM by name
        if self._waiting_name:
            logger.info(f"Waiting for VM '{self._name}' to be available.")
            vmi = self.service().api.get_vm_info(self._name)
            if vmi is None:
                logger.info(f"VM '{self._name}' does not exist yet.")
                return types.states.TaskState.RUNNING
            logger.info(f"VM '{self._name}' already exists.")
            self._waiting_name = False

        vmi = self.service().api.get_vm_info(self._name)
        if vmi is None:
            logger.info(f"VM '{self._name}' not found when checking state.")
            return types.states.TaskState.RUNNING
        # We consider the publication finished when the VM exists and is not in provisioning phase
        status = getattr(vmi, 'status', None)
        if status is None:
            logger.info(f"Status of VM '{self._name}' not available.")
            return types.states.TaskState.RUNNING
        # If there is a is_ready method or similar, use it. If not, just finish if the VM exists.
        logger.info(f"VM '{self._name}' is ready.")
        return types.states.TaskState.FINISHED

    def op_create_completed(self) -> None:
        """
        Actions to perform once the create operation is completed.
        In this case, we ensure the VM is stopped.
        """
        logger.info(f"Checking if VM '{self._name}' is running to stop it.")
        vmi = self.service().api.get_vm_info(self._name, force=True)
        if vmi is not None:
            status = getattr(vmi, 'status', None)
            if status and hasattr(status, 'is_running') and status.is_running():
                logger.info(f"Stopping VM '{self._name}'.")
                self.service().api.stop_vm_instance(self._name)
            else:
                logger.info(f"VM '{self._name}' is not running.")
        else:
            logger.info(f"VM '{self._name}' not found when trying to stop it.")

    def op_create_completed_checker(self) -> TaskState:
        """
        Checks if the create operation has been completed successfully.
        If the VM is stopped, we can consider the publication as completed.
        """
        logger.info(f"Checking if VM '{self._name}' is stopped after publication.")
        vmi = self.service().api.get_vm_info(self._name, force=True)
        if vmi is None:
            logger.info(f"VM '{self._name}' does not exist, publication finished.")
            return TaskState.FINISHED
        status = getattr(vmi, 'status', None)
        if status and hasattr(status, 'is_running') and not status.is_running():
            logger.info(f"VM '{self._name}' is stopped, publication finished.")
            return TaskState.FINISHED
        logger.info(f"VM '{self._name}' still running, waiting.")
        return TaskState.RUNNING

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._name
