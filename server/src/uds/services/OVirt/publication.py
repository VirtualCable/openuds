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
import collections.abc
import logging
from re import T
import typing
from datetime import datetime

from django.utils.translation import gettext as _

from uds.core.services import Publication
from uds.core.types.states import State
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OVirtLinkedService

logger = logging.getLogger(__name__)


class OVirtPublication(Publication, autoserializable.AutoSerializable):
    """
    This class provides the publication of a oVirtLinkedService
    """

    suggested_delay = 20  # : Suggested recheck time if publication is unfinished in seconds

    _name = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _destroy_after = autoserializable.BoolField(default=False)
    _template_id = autoserializable.StringField(default='')
    _state = autoserializable.StringField(default='r')

    def service(self) -> 'OVirtLinkedService':
        return typing.cast('OVirtLinkedService', super().service())

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
                self._reason,
                destroy_after,
                self._template_id,
                self._state,
            ) = vals[1:]
        else:
            raise ValueError('Invalid data format')

        self._destroy_after = destroy_after == 't'
        self.mark_for_upgrade()  # Mark so manager knows it has to be saved again

    def publish(self) -> str:
        """
        Realizes the publication of the service
        """
        self._name = self.service().sanitized_name(
            'UDSP ' + self.servicepool_name() + "-" + str(self.revision())
        )
        comments = _('UDS pub for {0} at {1}').format(
            self.servicepool_name(), str(datetime.now()).split('.')[0]
        )
        self._reason = ''  # No error, no reason for it
        self._destroy_after = False
        self._state = 'locked'

        try:
            self._template_id = self.service().make_template(self._name, comments)
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        return State.RUNNING

    def check_state(self) -> str:
        """
        Checks state of publication creation
        """
        if self._state == 'ok':
            return State.FINISHED

        if self._state == 'error':
            return State.ERROR

        try:
            self._state = self.service().get_template_state(self._template_id)
            if self._state == 'removed':
                raise Exception('Template has been removed!')
        except Exception as e:
            self._state = 'error'
            self._reason = str(e)
            return State.ERROR

        # If publication os done (template is ready), and cancel was requested, do it just after template becomes ready
        if self._state == 'ok':
            if self._destroy_after:
                self._destroy_after = False
                return self.destroy()
            return State.FINISHED

        return State.RUNNING

    def error_reason(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why
        it happened. This will be called just after publish or check_state
        if they return State.ERROR

        Returns an string, in our case, set at check_state
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
            self._destroy_after = True
            return State.RUNNING

        try:
            self.service().removeTemplate(self._template_id)
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

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._template_id
