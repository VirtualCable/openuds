# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import dataclasses
import typing

from uds.core import services
from uds.core.util.state import State

from . import service

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import TestServiceNoCache, TestServiceCache
    from .publication import TestPublication

logger = logging.getLogger(__name__)


class TestUserDeployment(services.UserDeployment):
    """
    Simple testing deployment, no cache
    """

    @dataclasses.dataclass
    class Data:
        """
        This is the data we will store in the storage
        """
        count: int = -1
        ready: bool = False
        name: str = ''
        ip: str = ''
        mac: str = ''

    data: Data

    def initialize(self) -> None:
        super().initialize()
        self.data = TestUserDeployment.Data()

    # : Recheck every five seconds by default (for task methods)
    suggestedTime = 5

    def service(self) -> typing.Union['TestServiceNoCache', 'TestServiceCache']:
        return typing.cast('TestServiceNoCache', super().service())

    def getName(self) -> str:
        if not self.data.name:
            self.data.name = self.nameGenerator().get(self.service().getBaseName(), 3)

        logger.info('Getting name of deployment %s', self.data)

        return self.data.name

    def setIp(self, ip: str) -> None:
        logger.info('Setting ip of deployment %s to %s', self.data, ip)
        self.data.ip = ip

    def getUniqueId(self) -> str:
        logger.info('Getting unique id of deployment %s', self.data)
        if not self.data.mac:
            self.data.mac = self.macGenerator().get(
                '00:00:00:00:00:00-00:FF:FF:FF:FF:FF'
            )
        return self.data.mac

    def getIp(self) -> str:
        logger.info('Getting ip of deployment %s', self.data)
        ip = typing.cast(str, self.storage.readData('ip'))
        if ip is None:
            ip = '8.6.4.2'  # Sample IP for testing purposses only
        return ip

    def setReady(self) -> str:
        logger.info('Setting ready %s', self.data)
        self.data.ready = True
        return State.FINISHED

    def deployForUser(self, user: 'models.User') -> str:
        logger.info('Deploying for user %s %s', user, self.data)
        self.data.count = 3
        return State.RUNNING

    def checkState(self) -> str:
        logger.info('Checking state of deployment %s', self.data)
        if self.data.count <= 0:
            return State.FINISHED

        self.data.count -= 1
        return State.RUNNING

    def finish(self) -> None:
        logger.info('Finishing deployment %s', self.data)
        self.data.count = -1

    def userLoggedIn(self, username: str) -> None:
        logger.info('User %s has logged in', username)

    def userLoggedOut(self, username) -> None:
        logger.info('User %s has logged out', username)

    def reasonOfError(self) -> str:
        return 'No error'

    def destroy(self) -> str:
        logger.info('Destroying deployment %s', self.data)
        self.data.count = -1
        return State.FINISHED

    def cancel(self) -> str:
        return self.destroy()

