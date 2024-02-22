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
import collections.abc

from django.utils.translation import gettext as _
from uds.core import types
from uds.core.services import Publication
from uds.core.types.states import State
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import XenLinkedService

logger = logging.getLogger(__name__)


class XenPublication(Publication, autoserializable.AutoSerializable):
    suggested_delay = (
        20  # : Suggested recheck time if publication is unfinished in seconds
    )

    _name = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _destroy_after = autoserializable.BoolField(default=False)
    _template_id = autoserializable.StringField(default='')
    _state = autoserializable.StringField(default='')
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
                self._template_id,
                self._state,
                self._task,
            ) = vals[1:]
        else:
            raise ValueError('Invalid data format')
            
        self._destroy_after = destroy_after == 't'
        
        self.mark_for_upgrade()   # Force upgrade asap

    def publish(self) -> types.states.State:
        """
        Realizes the publication of the service
        """
        self._name = self.service().sanitized_name(
            'UDS Pub ' + self.servicepool_name() + "-" + str(self.revision())
        )
        comments = _('UDS pub for {0} at {1}').format(
            self.servicepool_name(), str(datetime.now()).split('.')[0]
        )
        self._reason = ''  # No error, no reason for it
        self._destroy_after = False
        self._state = 'ok'

        try:
            self._task = self.service().start_deploy_of_template(self._name, comments)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return types.states.State.ERROR

        return types.states.State.RUNNING

    def check_state(self) -> types.states.State:
        """
        Checks state of publication creation
        """
        if self._state == 'finished':
            return types.states.State.FINISHED

        if self._state == 'error':
            return types.states.State.ERROR

        try:
            state, result = self.service().check_task_finished(self._task)
            if state:  # Finished
                self._state = 'finished'
                self._template_id = result
                if self._destroy_after:
                    self._destroy_after = False
                    return self.destroy()

                self.service().convert_to_template(self._template_id)
                return types.states.State.FINISHED
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return types.states.State.ERROR

        return types.states.State.RUNNING

    def error_reason(self) -> str:
        return self._reason

    def destroy(self) -> types.states.State:
        # We do not do anything else to destroy this instance of publication
        if self._state == 'ok':
            self._destroy_after = True
            return types.states.State.RUNNING

        try:
            self.service().remove_template(self._template_id)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return types.states.State.ERROR

        return types.states.State.FINISHED

    def cancel(self) -> types.states.State:
        return self.destroy()

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication type
    # and will be used by user deployments that uses this kind of publication

    def getTemplateId(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._template_id
