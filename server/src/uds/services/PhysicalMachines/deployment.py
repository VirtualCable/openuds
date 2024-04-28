# -*- coding: utf-8 -*-

#
# Copyright (c) 2016 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core import services, types
from uds.core.util import autoserializable, auto_attributes

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service_single import IPSingleMachineService

logger = logging.getLogger(__name__)


# This class is used for serialization of old data
class OldIPSerialData(auto_attributes.AutoAttributes):
    _ip: str
    _reason: str
    _state: str

    def __init__(self) -> None:
        auto_attributes.AutoAttributes.__init__(self, ip=str, reason=str, state=str)
        self._ip = ''
        self._reason = ''
        self._state = types.states.TaskState.FINISHED


class IPMachineUserService(services.UserService, autoserializable.AutoSerializable):
    suggested_delay = 10

    _ip = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _name = autoserializable.StringField(default='')

    # Utility overrides for type checking...
    def service(self) -> 'IPSingleMachineService':
        return typing.cast('IPSingleMachineService', super().service())

    def set_ip(self, ip: str) -> None:
        logger.debug('Setting IP to %s (ignored)', ip)

    def get_ip(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        return self.service().get_host_mac()[0]

    def get_name(self) -> str:
        if not self._name:
            # Generate a name with the IP + simple counter
            self._name = f'{self.get_ip()}:{self.service().get_counter_and_inc()}'
        return self._name

    def get_unique_id(self) -> str:
        return self.get_name()

    def set_ready(self) -> types.states.TaskState:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        self.service().wakeup()
        return types.states.TaskState.FINISHED

    def _deploy(self) -> types.states.TaskState:
        # If not to be managed by a token, autologin user
        userService = self.db_obj()
        if userService:
            userService.set_in_use(True)

        return types.states.TaskState.FINISHED

    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        logger.debug("Starting deploy of %s for user %s", self._ip, user)
        return self._deploy()

    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        return self._error('Cache deploy not supported')

    def _error(self, reason: str) -> types.states.TaskState:
        self._ip = ''
        self._reason = reason or 'Unknown error'
        return types.states.TaskState.ERROR

    def check_state(self) -> types.states.TaskState:
        if self._reason:
            return types.states.TaskState.ERROR
        return types.states.TaskState.FINISHED

    def error_reason(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why it happened. This will be called just after
        publish or checkPublishingState if they return types.states.DeployState.ERROR
        """
        return self._reason

    def destroy(self) -> types.states.TaskState:
        self._ip = ''
        self._reason = ''
        return types.states.TaskState.FINISHED

    def cancel(self) -> types.states.TaskState:
        return self.destroy()

    def unmarshal(self, data: bytes) -> None:
        if autoserializable.is_autoserializable_data(data):
            return super().unmarshal(data)

        _auto_data = OldIPSerialData()
        _auto_data.unmarshal(data)

        # Fill own data from restored data
        self._ip = _auto_data._ip
        self._name = self.db_obj().name or ''  # If has a name, use it, else, use the generated one
        self._reason = _auto_data._reason
        if _auto_data._state == types.states.TaskState.ERROR:
            self._reason = self._reason or 'Unknown error'

        # Flag for upgrade
        self.mark_for_upgrade(True)
