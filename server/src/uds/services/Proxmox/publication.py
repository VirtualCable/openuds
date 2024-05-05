#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import datetime
import time
import logging
import typing

from django.utils.translation import gettext as _
from uds.core import types
from uds.core.services.generics.dynamic.publication import DynamicPublication
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service_linked import ProxmoxServiceLinked

logger = logging.getLogger(__name__)


class ProxmoxPublication(DynamicPublication, autoserializable.AutoSerializable):

    suggested_delay = 20

    # Some customization fields
    # If must wait untill finish queue for destroying the machine
    wait_until_finish_to_destroy = True

    _task = autoserializable.StringField(default='')

    # Utility overrides for type checking...
    def service(self) -> 'ProxmoxServiceLinked':
        return typing.cast('ProxmoxServiceLinked', super().service())

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        logger.debug('Data: %s', data)
        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            (
                self._name,
                self._vmid,
                self._task,
                _state,
                _operation,
                destroy_after,
                self._reason,
            ) = vals[1:]
        else:
            raise ValueError('Invalid data format')

        self._queue = (
            # If removing
            [
                types.services.Operation.DELETE,
                types.services.Operation.DELETE_COMPLETED,
                types.services.Operation.FINISH,
            ]
            if _operation == 'd'
            # If publishing, must have finished for sure
            else [types.services.Operation.FINISH]
        )
        self._is_flagged_for_destroy = destroy_after != ''

        self.mark_for_upgrade()  # Flag so manager can save it again with new format
        
    def op_create(self) -> None:
        # First we should create a full clone, so base machine do not get fullfilled with "garbage" delta disks...
        comments = _('UDS Publication for {0} created at {1}').format(
            self.servicepool_name(), str(datetime.datetime.now()).split('.')[0]
        )
        task = self.service().clone_machine(self._name, comments)
        self._vmid = str(task.vmid)
        self._task = ','.join((task.upid.node, task.upid.upid))

    def op_create_checker(self) -> types.states.TaskState:
        node, upid = self._task.split(',')
        task = self.service().provider().get_task_info(node, upid)
        if task.is_running():
            return types.states.TaskState.RUNNING

        if task.is_errored():
            return self._error(task.exitstatus)

        return types.states.TaskState.FINISHED

    def op_create_completed(self) -> None:
        # Complete the creation, disabling ha protection and adding to HA and marking as template
        self.service().provider().set_protection(int(self._vmid), protection=False)
        time.sleep(0.5)  # Give some tome to proxmox. We have observed some concurrency issues
        # And add it to HA if needed (decided by service configuration)
        self.service().enable_machine_ha(int(self._vmid))
        # Wait a bit, if too fast, proxmox fails.. (Have not tested on 8.x, but previous versions failed if too fast..)
        time.sleep(0.5)
        # Mark vm as template
        self.service().provider().create_template(int(self._vmid))
        
    def op_remove(self) -> None:
        self.service().delete(self, self._vmid)
        
    def machine(self) -> int:
        return int(self._vmid)
