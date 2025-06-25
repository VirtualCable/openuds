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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core import services, types
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service_multi import IPMachinesService

logger = logging.getLogger(__name__)


class IPMachinesUserService(services.UserService, autoserializable.AutoSerializable):
    suggested_delay = 10

    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')  # If != '', this is the error message and state is ERROR

    # Utility overrides for type checking...
    def service(self) -> 'IPMachinesService':
        return typing.cast('IPMachinesService', super().service())

    def _set_in_use(self) -> None:
        if not self.service().get_token():
            userservice = self.db_obj()
            if userservice:
                userservice.set_in_use(True)

    def set_ip(self, ip: str) -> None:
        logger.debug('Setting IP to %s (ignored)', ip)

    def get_ip(self) -> str:
        return self._ip

    def get_name(self) -> str:
        return self.get_ip()

    def get_unique_id(self) -> str:
        # Generate a 16 chars string mixing up all _vmid chars
        return self.get_ip()

    def set_ready(self) -> types.states.TaskState:
        self.service().wakeup(self._ip, self._mac)
        return types.states.TaskState.FINISHED

    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        logger.debug("Starting deploy of %s for user %s", self._ip, user)
        self._vmid = self.service().get_unassigned()

        self._ip, self._mac = self.service().get_host_mac(self._vmid)

        self._set_in_use()

        return types.states.TaskState.FINISHED

    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        return self._error('Cache deploy not supported')

    def assign(self, vmid: str) -> types.states.TaskState:
        logger.debug('Assigning from assignable with id %s', vmid)
        self._vmid = vmid
        # Update ip & mac
        self._ip, self._mac = self.service().get_host_mac(vmid)

        self._set_in_use()

        return types.states.TaskState.FINISHED

    def _error(self, reason: str) -> types.states.TaskState:
        if self._vmid:
            self.service().unlock_server(self._vmid)
        self._vmid = ''
        self._ip = ''
        self._mac = ''
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
        if self._vmid:
            self.service().unlock_server(self._vmid)
        self._vmid = ''
        self._ip = ''
        self._mac = ''
        return types.states.TaskState.FINISHED

    def cancel(self) -> types.states.TaskState:
        return self.destroy()

    # Data is migrated on migration 0046, so no unmarshall is needed
