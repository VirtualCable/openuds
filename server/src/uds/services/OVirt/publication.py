# -*- coding: utf-8 -*-

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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from datetime import datetime
import logging
import typing

from django.utils.translation import gettext as _
from uds.core.services import Publication
from uds.core.util.state import State

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OVirtLinkedService

logger = logging.getLogger(__name__)


class OVirtPublication(Publication):
    """
    This class provides the publication of a oVirtLinkedService
    """

    suggestedTime = (
        20  # : Suggested recheck time if publication is unfinished in seconds
    )
    _name: str
    _reason: str
    _destroyAfter: str
    _templateId: str
    _state: str

    def service(self) -> 'OVirtLinkedService':
        return typing.cast('OVirtLinkedService', super().service())

    def initialize(self) -> None:
        """
        This method will be invoked by default __init__ of base class, so it gives
        us the oportunity to initialize whataver we need here.

        In our case, we setup a few attributes..
        """

        # We do not check anything at marshal method, so we ensure that
        # default values are correctly handled by marshal.
        self._name = ''
        self._reason = ''
        self._destroyAfter = 'f'
        self._templateId = ''
        self._state = 'r'

    def marshal(self) -> bytes:
        """
        returns data from an instance of Sample Publication serialized
        """
        return '\t'.join(
            [
                'v1',
                self._name,
                self._reason,
                self._destroyAfter,
                self._templateId,
                self._state,
            ]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        logger.debug('Data: %s', data)
        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            (
                self._name,
                self._reason,
                self._destroyAfter,
                self._templateId,
                self._state,
            ) = vals[1:]

    def publish(self) -> str:
        """
        Realizes the publication of the service
        """
        self._name = self.service().sanitizeVmName(
            'UDSP ' + self.dsName() + "-" + str(self.revision())
        )
        comments = _('UDS pub for {0} at {1}').format(
            self.dsName(), str(datetime.now()).split('.')[0]
        )
        self._reason = ''  # No error, no reason for it
        self._destroyAfter = 'f'
        self._state = 'locked'

        try:
            self._templateId = self.service().makeTemplate(self._name, comments)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        return State.RUNNING

    def checkState(self) -> str:
        """
        Checks state of publication creation
        """
        if self._state == 'ok':
            return State.FINISHED

        if self._state == 'error':
            return State.ERROR

        try:
            self._state = self.service().getTemplateState(self._templateId)
            if self._state == 'removed':
                raise Exception('Template has been removed!')
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        # If publication os done (template is ready), and cancel was requested, do it just after template becomes ready
        if self._state == 'ok':
            if self._destroyAfter == 't':
                return self.destroy()
            return State.FINISHED

        return State.RUNNING

    def reasonOfError(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why
        it happened. This will be called just after publish or checkState
        if they return State.ERROR

        Returns an string, in our case, set at checkState
        """
        return self._reason

    def destroy(self) -> str:
        """
        This is called once a publication is no more needed.

        This method do whatever needed to clean up things, such as
        removing created "external" data (environment gets cleaned by core),
        etc..

        The retunred value is the same as when publishing, State.RUNNING,
        State.FINISHED or State.ERROR.
        """
        # We do not do anything else to destroy this instance of publication
        if self._state == 'locked':
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
        """
        Do same thing as destroy
        """
        return self.destroy()

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def getTemplateId(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._templateId
