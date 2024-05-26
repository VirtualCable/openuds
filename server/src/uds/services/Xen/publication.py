# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
from datetime import datetime
import logging
import typing

from django.utils.translation import gettext as _
from uds.core import types
from uds.core.services.generics.dynamic.publication import DynamicPublication
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import XenLinkedService

logger = logging.getLogger(__name__)


class XenPublication(DynamicPublication, autoserializable.AutoSerializable):
    suggested_delay = (
        20  # : Suggested recheck time if publication is unfinished in seconds
    )

    _task = autoserializable.StringField(default='')

    def service(self) -> 'XenLinkedService':
        return typing.cast('XenLinkedService', super().service())

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)
            
        # logger.debug('Data: {0}'.format(data))
        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            (
                self._name,
                self._reason,
                destroy_after,
                self._vmid,
                state,
                self._task,
            ) = vals[1:]
        else:
            raise ValueError('Invalid data format')
            
        self._is_flagged_for_destroy = destroy_after == 't'
        if state == 'finished':
            self._set_queue([types.services.Operation.FINISH])
        elif state == 'error':
            self._set_queue([types.services.Operation.ERROR])
        else:  # Running
            self._set_queue([types.services.Operation.CREATE, types.services.Operation.FINISH])
        self._queue
        
        self.mark_for_upgrade()   # Force upgrade asap
        
    def op_create(self) -> None:
        # Name created by DynamicPublication
        comments = _('UDS pub for {0} at {1}').format(
            self.servicepool_name(), str(datetime.now()).split('.')[0]
        )

        self._task = self.service().start_deploy_of_template(self._name, comments)
        
    def op_create_checker(self) -> types.states.TaskState:
        """
        Checks state of publication creation
        """
        with  self.service().provider().get_connection() as api:
            task_info = api.get_task_info(self._task)
            if task_info.is_success():
                self._vmid = task_info.result
                self.service().convert_to_template(self._vmid)
                return types.states.TaskState.FINISHED
            elif task_info.is_failure():
                return self._error(task_info.result)

        return types.states.TaskState.RUNNING

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication type
    # and will be used by user deployments that uses this kind of publication

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._vmid
