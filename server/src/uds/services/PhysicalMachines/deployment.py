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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

import dns.resolver

from uds.core import services
from uds.core.util.state import State
from uds.core.util.auto_attributes import AutoAttributes
from uds.core.util import net
from uds.core.util import log

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service_base import IPServiceBase

logger = logging.getLogger(__name__)


class IPMachineDeployed(services.UserDeployment, AutoAttributes):
    suggestedTime = 10

    _ip: str
    _reason: str
    _state: str

    def __init__(self, environment, **kwargs):
        AutoAttributes.__init__(self, ip=str, reason=str, state=str)
        services.UserDeployment.__init__(self, environment, **kwargs)
        self._state = State.FINISHED

    # Utility overrides for type checking...
    def service(self) -> 'IPServiceBase':
        return typing.cast('IPServiceBase', super().service())

    def setIp(self, ip: str) -> None:
        logger.debug('Setting IP to %s (ignored)', ip)

    def getIp(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        ip = self._ip.split('~')[0].split(';')[0]
        # If ip is in fact a hostname...
        if not net.ipToLong(ip).version:
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
                    self.service().parent().doLog(
                        log.LogLevel.WARNING, f'User service could not resolve Name {ip} ({e}).'
                    )

        return ip

    def getName(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        return self._ip.replace('~', ':')

    def getUniqueId(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        return self._ip.replace('~', ':').split(';')[0]

    def setReady(self) -> str:
        # If single machine, ip is IP~counter,
        # If multiple and has a ';' on IP, the values is IP;MAC
        if ';' in self._ip:  # Only try wakeup if mac is present
            ip, mac = self._ip.split('~')[0].split(';')[0:2]
            self.service().wakeup(ip, mac)
        self._state = State.FINISHED
        return self._state

    def __deploy(self) -> str:
        ip = self.service().getUnassignedMachine()
        if ip is None:
            self._reason = 'No machines left'
            self._state = State.ERROR
        else:
            self._ip = ip
            self._state = State.FINISHED

        # If not to be managed by a token, autologin user
        if not self.service().getToken():
            userService = self.dbservice()
            if userService:
                userService.setInUse(True)

        return self._state

    def deployForUser(self, user: 'models.User') -> str:
        logger.debug("Starting deploy of %s for user %s", self._ip, user)
        return self.__deploy()

    def assign(self, ip: str) -> str:
        logger.debug('Assigning from assignable with ip %s', ip)
        self._ip = ip
        self._state = State.FINISHED
        if not self.service().getToken():
            dbService = self.dbservice()
            if dbService:
                dbService.setInUse(True)
                dbService.save()
        return self._state

    def error(self, reason: str) -> str:
        self._state = State.ERROR
        self._ip = ''
        self._reason = reason
        return self._state

    def checkState(self) -> str:
        return self._state

    def reasonOfError(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why it happened. This will be called just after
        publish or checkPublishingState if they return State.ERROR
        """
        return self._reason

    def destroy(self) -> str:
        if self._ip != '':
            self.service().unassignMachine(self._ip)
        self._state = State.FINISHED
        return self._state

    def cancel(self) -> str:
        return self.destroy()
