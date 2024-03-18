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

from uds.core.services import Publication
from uds.core import types
from uds.core.util import autoserializable

from .openstack import types as openstack_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OpenStackLiveService

logger = logging.getLogger(__name__)


class OpenStackLivePublication(Publication, autoserializable.AutoSerializable):
    """
    This class provides the publication of a oVirtLinkedService
    """

    _name = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _template_id = autoserializable.StringField(default='')
    _status = autoserializable.StringField(default='r')
    _destroy_after = autoserializable.BoolField(default=False)

    # _name: str = ''
    # _reason: str = ''
    # _template_id: str = ''
    # _state: str = 'r'
    # _destroyAfter: str = 'n'

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
            (self._name, self._reason, self._template_id, self._status, destroy_after) = vals[1:]
        else:
            raise Exception('Invalid data')

        self._destroy_after = destroy_after == 'y'

        self.mark_for_upgrade()  # This will force remarshalling

    def publish(self) -> types.states.TaskState:
        """
        Realizes the publication of the service
        """
        self._name = self.service().sanitized_name(
            'UDS-P-' + self.servicepool_name() + "-" + str(self.revision())
        )
        self._reason = ''  # No error, no reason for it
        self._destroy_after = False

        try:
            res = self.service().make_template(self._name)
            logger.debug('Publication result: %s', res)
            self._template_id = res.id
            self._status = res.status
        except Exception as e:
            logger.exception('Got exception')
            self._status = 'error'
            self._reason = 'Got error {}'.format(e)
            return types.states.TaskState.ERROR

        return types.states.TaskState.RUNNING

    def check_state(self) -> types.states.TaskState:
        """
        Checks state of publication creation
        """
        if self._status == openstack_types.SnapshotStatus.ERROR:
            return types.states.TaskState.ERROR

        if self._status ==  openstack_types.SnapshotStatus.AVAILABLE:
            return types.states.TaskState.FINISHED

        try:
            self._status = self.service().get_template(self._template_id).status  # For next check

            if self._destroy_after and self._status == openstack_types.SnapshotStatus.AVAILABLE:
                self._destroy_after = False
                return self.destroy()

            return types.states.TaskState.RUNNING
        except Exception as e:
            self._status = 'error'
            self._reason = str(e)
            return types.states.TaskState.ERROR

    def error_reason(self) -> str:
        return self._reason

    def destroy(self) -> types.states.TaskState:
        # We do not do anything else to destroy this instance of publication
        if self._status == 'error':
            return types.states.TaskState.ERROR  # Nothing to cancel

        if self._status == 'creating':
            self._destroy_after = True
            return types.states.TaskState.RUNNING

        try:
            self.service().remove_template(self._template_id)
        except Exception as e:
            self._status = 'error'
            self._reason = str(e)
            return types.states.TaskState.ERROR

        return types.states.TaskState.FINISHED

    def cancel(self) -> types.states.TaskState:
        return self.destroy()

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def get_template_id(self) -> str:
        """
        Returns the template id associated with the publication
        """
        return self._template_id
