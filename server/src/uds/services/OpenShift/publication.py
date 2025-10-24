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
import re

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
        return typing.cast('OpenshiftService', super().service())

    def sanitize_name(self, name: str) -> str:
        # Sanitize the name to comply with RFC 1123: lowercase, alphanumeric, '-', '.', start/end with alphanumeric
        name = name.lower()
        name = re.sub(r'[^a-z0-9.-]', '-', name)
        name = re.sub(r'-+', '-', name)
        name = re.sub(r'^[^a-z0-9]+', '', name)
        name = re.sub(r'[^a-z0-9]+$', '', name)
        return name[:63]  # Max length for DNS subdomain names

    def op_create(self) -> None:
        logger.info("Starting publication process: template cloning.")
        self._waiting_name = True
        api = self.service().api
        template_vm_uuid = self.service().template.value
        namespace = api.namespace
        api_url = api.api_url
        storage_class = getattr(self.service(), 'storage_class', 'default')  # Ajusta si tienes un campo real

        # Buscar el nombre real de la máquina a partir del UUID
        template_vm_name = None
        for vm in api.list_vms():
            if str(getattr(vm, 'uid', getattr(vm, 'uuid', None))) == template_vm_uuid:
                template_vm_name = vm.name
                break
        if not template_vm_name:
            logger.error(f"VM name not found for UUID {template_vm_uuid}")
            self._error(f"VM name not found for UUID {template_vm_uuid}")
            return

        logger.info(f"Getting template PVC/DataVolume '{template_vm_name}'.")
        source_pvc_name, vol_type = api.get_vm_pvc_or_dv_name(api_url, namespace, template_vm_name)  # type: ignore
        logger.info(f"Source PVC/DataVolume: {source_pvc_name}, type: {vol_type}.")

        logger.info(f"Getting PVC size '{source_pvc_name}'.")
        size = api.get_pvc_size(api_url, namespace, source_pvc_name)
        logger.info(f"PVC size: {size}.")

        new_pvc_name = self.sanitize_name(f"{self._name}-disk")
        logger.info(f"Cloning PVC '{source_pvc_name}' to '{new_pvc_name}' using DataVolume.")
        ok = api.clone_pvc_with_datavolume(api_url, namespace, source_pvc_name, new_pvc_name, storage_class, size)
        if not ok:
            logger.error(f"Error cloning PVC {source_pvc_name}.")
            self._error(f"Error cloning PVC {source_pvc_name}")
            return
        
        logger.info(f"Creating new VM '{self._name}' from cloned PVC '{new_pvc_name}'.")
        ok = api.create_vm_from_pvc(
            api_url=api_url,
            namespace=namespace,
            source_vm_name=template_vm_name,
            new_vm_name=self.sanitize_name(self._name),
            new_dv_name=new_pvc_name,
            source_pvc_name=new_pvc_name,
        )
        if not ok:
            logger.error(f"Error creating VM {self._name} from cloned PVC.")
            self._error(f"Error creating VM {self._name} from cloned PVC")
            return
        else:
            logger.info(f"VM '{self._name}' creation initiated successfully.")

        # logger.info(f"Waiting for DataVolume '{new_pvc_name}' to be ready.")
        # if not api.wait_for_datavolume_clone_progress(api_url, namespace, new_pvc_name):
        #     logger.error(f"Timeout waiting for DataVolume clone {new_pvc_name}.")
        #     self._error(f"Timeout waiting for DataVolume clone {new_pvc_name}")
        #     return

        logger.info(f"VM '{self._name}' created successfully.")
        self._vmid = self._name
        self._waiting_name = False

    def op_create_checker(self) -> types.states.TaskState:
        # Si aún estamos esperando, intentamos obtener la VM por nombre
        if self._waiting_name:
            logger.info(f"Waiting for VM '{self._name}' to be available.")
            instance = self.service().api.get_vm_info(self._name)
            if instance is None:
                logger.info(f"VM '{self._name}' does not exist yet.")
                return types.states.TaskState.RUNNING
            logger.info(f"VM '{self._name}' already exists.")
            self._vmid = self._name
            self._waiting_name = False

        instance = self.service().api.get_vm_info(self._vmid)
        if instance is None:
            logger.info(f"VM '{self._vmid}' not found when checking state.")
            return types.states.TaskState.RUNNING
        # Consideramos que la publicación termina cuando la VM existe y no está en fase de provisión
        status = getattr(instance, 'status', None)
        if status is None:
            logger.info(f"Status of VM '{self._vmid}' not available.")
            return types.states.TaskState.RUNNING
        # Si existe un método is_ready o similar, úsalo. Si no, simplemente finaliza si la VM existe.
        logger.info(f"VM '{self._vmid}' is ready.")
        return types.states.TaskState.FINISHED

    def op_create_completed(self) -> None:
        logger.info(f"Checking if VM '{self._vmid}' is running to stop it.")
        instance = self.service().api.get_vm_info(self._vmid, force=True)
        if instance is not None:
            status = getattr(instance, 'status', None)
            if status and hasattr(status, 'is_running') and status.is_running():
                logger.info(f"Stopping VM '{self._vmid}'.")
                self.service().api.stop_instance(self._vmid)
            else:
                logger.info(f"VM '{self._vmid}' is not running.")
        else:
            logger.info(f"VM '{self._vmid}' not found when trying to stop it.")

    def op_create_completed_checker(self) -> TaskState:
        """
        Checks if the create operation has been completed successfully.
        If the instance is stopped, we can consider the publication as completed.
        """
        logger.info(f"Checking if VM '{self._vmid}' is stopped after publication.")
        instance = self.service().api.get_vm_info(self._vmid, force=True)
        if instance is None:
            logger.info(f"VM '{self._vmid}' does not exist, publication finished.")
            return TaskState.FINISHED
        status = getattr(instance, 'status', None)
        if status and hasattr(status, 'is_running') and not status.is_running():
            logger.info(f"VM '{self._vmid}' is stopped, publication finished.")
            return TaskState.FINISHED
        logger.info(f"VM '{self._vmid}' still running, waiting.")
        return TaskState.RUNNING

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._vmid
