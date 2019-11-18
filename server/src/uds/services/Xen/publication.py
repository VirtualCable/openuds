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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
from datetime import datetime
import logging
import typing

from django.utils.translation import ugettext as _
from uds.core.services import Publication
from uds.core.util.state import State

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import XenLinkedService

logger = logging.getLogger(__name__)


class XenPublication(Publication):
    suggestedTime = 20  # : Suggested recheck time if publication is unfinished in seconds

    _name: str = ''
    _reason: str = ''
    _destroyAfter: str = 'f'
    _templateId: str = ''
    _state: str = ''
    _task: str = ''

    def service(self) -> 'XenLinkedService':
        return typing.cast('XenLinkedService', super().service())

    def marshal(self) -> bytes:
        """
        returns data from an instance of Sample Publication serialized
        """
        return '\t'.join(['v1', self._name, self._reason, self._destroyAfter, self._templateId, self._state, self._task]).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        #logger.debug('Data: {0}'.format(data))
        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            self._name, self._reason, self._destroyAfter, self._templateId, self._state, self._task = vals[1:]

    def publish(self) -> str:
        """
        Realizes the publication of the service
        """
        self._name = self.service().sanitizeVmName('UDS Pub ' + self.dsName() + "-" + str(self.revision()))
        comments = _('UDS pub for {0} at {1}').format(self.dsName(), str(datetime.now()).split('.')[0])
        self._reason = ''  # No error, no reason for it
        self._destroyAfter = 'f'
        self._state = 'ok'

        try:
            self._task = self.service().startDeployTemplate(self._name, comments)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        return State.RUNNING

    def checkState(self) -> str:
        """
        Checks state of publication creation
        """
        if self._state == 'finished':
            return State.FINISHED

        if self._state == 'error':
            return State.ERROR

        try:
            state, result = self.service().checkTaskFinished(self._task)
            if state:  # Finished
                self._state = 'finished'
                self._templateId = result
                if self._destroyAfter == 't':
                    return self.destroy()

                self.service().convertToTemplate(self._templateId)
                return State.FINISHED
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        return State.RUNNING

    def reasonOfError(self) -> str:
        return self._reason

    def destroy(self) -> str:
        # We do not do anything else to destroy this instance of publication
        if self._state == 'ok':
            self._destroyAfter = 't'
            return State.RUNNING

        try:
            self.service().removeTemplate(self._templateId)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        return State.FINISHED

    def cancel(self) -> str:
        return self.destroy()

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication type
    # and will be used by user deployments that uses this kind of publication

    def getTemplateId(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._templateId
