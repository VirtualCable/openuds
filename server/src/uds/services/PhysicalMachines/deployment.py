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
import collections.abc

import dns.resolver

from uds.core import services
from uds.core.types.states import State
from uds.core.util import net
from uds.core.util import log, autoserializable, auto_attributes

from .types import HostInfo

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service_base import IPServiceBase

logger = logging.getLogger(__name__)

# This class is used for serialization of old data
class OldIPSerialData(auto_attributes.AutoAttributes):
    _ip: str
    _reason: str
    _state: str
    
    def __init__(self):
        auto_attributes.AutoAttributes.__init__(self, ip=str, reason=str, state=str)
        self._ip = ''
        self._reason = ''
        self._state = State.FINISHED

class IPMachineUserService(services.UserService, autoserializable.AutoSerializable):
    suggested_delay = 10

    _ip = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')
    _state = autoserializable.StringField(default=State.FINISHED)

    # Utility overrides for type checking...
    def service(self) -> 'IPServiceBase':
        return typing.cast('IPServiceBase', super().service())

    def set_ip(self, ip: str) -> None:
        logger.debug('Setting IP to %s (ignored)', ip)

    def get_ip(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        ip = self._ip.split('~')[0].split(';')[0]
        # If ip is in fact a hostname...
        if not net.ip_to_long(ip).version:
            # Try to resolve name...
            try:
                # Prefer ipv4 first
                res = dns.resolver.resolve(ip)
                ip = typing.cast(str, res[0].address)  # type: ignore  # If no address, it will raise an exception
            except Exception:
                # If not found, try ipv6
                try:
                    res = dns.resolver.resolve(ip, 'AAAA')
                    ip = typing.cast(str, res[0].address)  # type: ignore  # If no address, it will raise an exception
                except Exception as e:
                    self.service().parent().do_log(
                        log.LogLevel.WARNING, f'User service could not resolve Name {ip} ({e}).'
                    )

        return ip

    def get_name(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        return self._ip.replace('~', ':')

    def get_unique_id(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        return self._ip.replace('~', ':').split(';')[0]

    def set_ready(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        host = HostInfo.from_str(self._ip)
        if host.mac:
            self.service().wakeup(host)
        self._state = State.FINISHED
        return self._state

    def _deploy(self) -> str:
        ip = self.service().get_unassigned_host()
        if ip is None:
            self._reason = 'No machines left'
            self._state = State.ERROR
        else:
            self._ip = ip.as_identifier()
            self._state = State.FINISHED

        # If not to be managed by a token, autologin user
        if not self.service().get_token():
            userService = self.db_obj()
            if userService:
                userService.set_in_use(True)

        return self._state

    def deploy_for_user(self, user: 'models.User') -> str:
        logger.debug("Starting deploy of %s for user %s", self._ip, user)
        return self._deploy()

    def assign(self, ip: str) -> str:
        logger.debug('Assigning from assignable with ip %s', ip)
        self._ip = ip
        self._state = State.FINISHED
        if not self.service().get_token():
            dbService = self.db_obj()
            if dbService:
                dbService.set_in_use(True)
                dbService.save()
        return self._state

    def error(self, reason: str) -> str:
        self._state = State.ERROR
        self._ip = ''
        self._reason = reason
        return self._state

    def check_state(self) -> str:
        return self._state

    def error_reason(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why it happened. This will be called just after
        publish or checkPublishingState if they return State.ERROR
        """
        return self._reason

    def destroy(self) -> str:
        host = HostInfo.from_str(self._ip)
        if host.host:
            self.service().unassign_host(host)
        self._state = State.FINISHED
        return self._state

    def cancel(self) -> str:
        return self.destroy()

    def unmarshal(self, data: bytes) -> None:
        if autoserializable.is_autoserializable_data(data):
            return super().unmarshal(data)

        _auto_data = OldIPSerialData()
        _auto_data.unmarshal(data)

        # Fill own data from restored data
        self._ip = _auto_data._ip
        self._reason = _auto_data._reason
        self._state = _auto_data._state

        # Flag for upgrade
        self.mark_for_upgrade(True)
