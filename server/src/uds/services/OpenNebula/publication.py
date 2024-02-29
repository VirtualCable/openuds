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

from uds.core.services import Publication
from uds.core import types
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OpenNebulaLiveService

logger = logging.getLogger(__name__)


class OpenNebulaLivePublication(Publication, autoserializable.AutoSerializable):
    """
    This class provides the publication of a oVirtLinkedService
    """

    suggested_delay = 2  # : Suggested recheck time if publication is unfinished in seconds

    _name = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _template_id = autoserializable.StringField(default='')
    _state = autoserializable.StringField(default='r')
    _destroy_after = autoserializable.BoolField(default=False)

    # _name: str = ''
    # _reason: str = ''
    # _templateId: str = ''
    # _state: str = 'r'

    def service(self) -> 'OpenNebulaLiveService':
        return typing.cast('OpenNebulaLiveService', super().service())

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            self._name, self._reason, self._template_id, self._state = vals[1:]

        self._destroy_after = False

        self.mark_for_upgrade()  # Flag so manager can save it again with new format

    def publish(self) -> types.states.State:
        """
        Realizes the publication of the service
        """
        self._name = self.service().sanitized_name(
            'UDSP ' + self.servicepool_name() + "-" + str(self.revision())
        )
        self._reason = ''  # No error, no reason for it
        self._state = 'running'

        try:
            self._template_id = self.service().make_template(self._name)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return types.states.State.ERROR

        return types.states.State.RUNNING

    def check_state(self) -> types.states.State:
        """
        Checks state of publication creation
        """
        if self._state == 'running':
            try:
                if self.service().check_template_published(self._template_id) is False:
                    return types.states.State.RUNNING
                self._state = 'ok'
            except Exception as e:
                self._state = 'error'
                self._reason = str(e)

        if self._state == 'error':
            return types.states.State.ERROR

        if self._state == 'ok':
            if self._destroy_after:  # If we must destroy after publication, do it now
                self._destroy_after = False
                return self.destroy()

            return types.states.State.FINISHED

        self._state = 'ok'
        return types.states.State.FINISHED

    def error_reason(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why
        it happened. This will be called just after publish or check_state
        if they return types.states.State.ERROR

        Returns an string, in our case, set at check_state
        """
        return self._reason

    def destroy(self) -> types.states.State:
        """
        This is called once a publication is no more needed.

        This method do whatever needed to clean up things, such as
        removing created "external" data (environment gets cleaned by core),
        etc..

        The retunred value is the same as when publishing, types.states.State.RUNNING,
        types.states.State.FINISHED or types.states.State.ERROR.
        """
        if self._state == 'error':
            return types.states.State.ERROR

        if self._state == 'running':
            self._destroy_after = True
            return types.states.State.RUNNING

        # We do not do anything else to destroy this instance of publication
        try:
            self.service().remove_template(self._template_id)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return types.states.State.ERROR

        return types.states.State.FINISHED

    def cancel(self) -> types.states.State:
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
        return self._template_id
