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
        return typing.cast('OpenshiftService', super().service())

    def op_create(self) -> None:
        # We need to wait for the name te be created, but don't want to loose the _name
        self._waiting_name = True
        instance_info = self.service().api.get_instance_info(self.service().template.value)
        logger.debug('Instance info for cloning: %s', instance_info)
        if instance_info.status.is_cloning():
            self.retry_later()
        elif not instance_info.status.is_cloneable():
            self._error(
                f'Instance {self.service().template.value} is not cloneable, status: {instance_info.status}'
            )
        else:
            # Note that name was created by DynamicPublication on "Initialize" operation
            self.service().api.clone_instance(
                instance_info.id,
                self._name,
            )

    def op_create_checker(self) -> types.states.TaskState:
        # Wait until we have created the vm is _name is not emtpy
        if self._waiting_name:
            found_vms = self.service().api.list_instances(name=self._name, force=True)  # Do not use cache
            if not found_vms:
                return types.states.TaskState.RUNNING
            else:  # We have the instance, clear _waiting_name and set _vmid
                self._vmid = str(found_vms[0].id)
                self._waiting_name = False

        instance = self.service().api.get_instance_info(self._vmid)

        if not instance.status.is_provisioning():
            # If instance is running, we can finish the publication
            return types.states.TaskState.FINISHED

        return types.states.TaskState.RUNNING

    def op_create_completed(self) -> None:
        # Ensure we stop the machine if it is running
        instance = self.service().api.get_instance_info(self._vmid, force=True)
        if instance.status.is_running():
            self.service().api.stop_instance(self._vmid)

    def op_create_completed_checker(self) -> TaskState:
        """
        Checks if the create operation has been completed successfully.
        If the instance is running, we can consider the publication as completed.
        """
        instance = self.service().api.get_instance_info(self._vmid, force=True)
        if not instance.status.is_running():
            return TaskState.FINISHED

        return TaskState.RUNNING

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._vmid
