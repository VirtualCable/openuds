# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
import logging
import typing

from uds.core.services.generics.dynamic.publication import DynamicPublication
from uds.core import types
from uds.core.util import autoserializable

from .openstack import types as openstack_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OpenStackLiveService

logger = logging.getLogger(__name__)


class OpenStackLivePublication(DynamicPublication, autoserializable.AutoSerializable):
    """
    This class provides the publication of a oVirtLinkedService
    """
    suggested_delay = 20  # : Suggested recheck time if publication is unfinished in seconds

    def service(self) -> 'OpenStackLiveService':
        return typing.cast('OpenStackLiveService', super().service())

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            (self._name, self._reason, self._vmid, status, destroy_after) = vals[1:]
        else:
            raise Exception('Invalid data')
        
        if status == openstack_types.SnapshotStatus.ERROR:
            self._queue = [types.services.Operation.ERROR]
        elif status == openstack_types.SnapshotStatus.AVAILABLE:
            self._queue = [types.services.Operation.FINISH]
        else:
            self._queue = [types.services.Operation.CREATE, types.services.Operation.FINISH]

        self._is_flagged_for_destroy = destroy_after == 'y'

        self.mark_for_upgrade()  # This will force remarshalling

    def op_create(self) -> None:
        """
        Realizes the publication of the service
        """
        # Name is generated on op_initialize by DynamicPublication
        volume_snapshot_info = self.service().make_template(self._name)
        logger.debug('Publication result: %s', volume_snapshot_info)
        self._vmid = volume_snapshot_info.id  # In fact is not an vmid, but the volume snapshot id, but this way we can use the same method for all publications
        if volume_snapshot_info.status == openstack_types.SnapshotStatus.ERROR:
            raise Exception('Error creating snapshot')

    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks state of publication creation
        """
        status = self.service().get_template(self._vmid).status  # For next check
        if status == openstack_types.SnapshotStatus.AVAILABLE:
            return types.states.TaskState.FINISHED
        
        if status == openstack_types.SnapshotStatus.ERROR:
            raise Exception('Error creating snapshot')
        
        return types.states.TaskState.RUNNING

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._vmid
