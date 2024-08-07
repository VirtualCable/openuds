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
import typing

from uds.core import services, types
from uds.core.util import autoserializable

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import TestServiceNoCache, TestServiceCache

logger = logging.getLogger(__name__)


class TestUserService(services.UserService, autoserializable.AutoSerializable):
    """
    Simple testing deployment, no cache
    """
    count = autoserializable.IntegerField(default=-1)
    ready = autoserializable.BoolField(default=False)
    name = autoserializable.StringField(default='')
    ip = autoserializable.StringField(default='')
    mac = autoserializable.StringField(default='')

    def initialize(self) -> None:
        super().initialize()

    # : Recheck every five seconds by default (for task methods)
    suggested_delay = 5

    def service(self) -> typing.Union['TestServiceNoCache', 'TestServiceCache']:
        return typing.cast('TestServiceNoCache', super().service())

    def get_name(self) -> str:
        if not self.name:
            self.name = self.name_generator().get(self.service().get_basename(), 3)

        logger.info('Getting name of deployment %s', self)

        return self.name

    def set_ip(self, ip: str) -> None:
        logger.info('Setting ip of deployment %s to %s', self, ip)
        self.ip = ip

    def get_unique_id(self) -> str:
        logger.info('Getting unique id of deployment %s', self)
        if not self.mac:
            self.mac = self.mac_generator().get('00:00:00:00:00:00-00:FF:FF:FF:FF:FF')
        return self.mac

    def get_ip(self) -> str:
        logger.info('Getting ip of deployment %s', self)
        ip = typing.cast(str, self.storage.read_from_db('ip'))
        if not ip:
            ip = '8.6.4.2'  # Sample IP for testing purposses only
        return ip

    def set_ready(self) -> types.states.TaskState:
        logger.info('Setting ready %s', self)
        self.ready = True
        return types.states.TaskState.FINISHED

    def deploy_for_user(self, user: 'models.User') -> types.states.TaskState:
        logger.info('Deploying for user %s %s', user, self)
        self.count = 3
        return types.states.TaskState.RUNNING
    
    def deploy_for_cache(self, level: types.services.CacheLevel) -> types.states.TaskState:
        logger.info('Deploying for cache %s %s', level, self)
        self.count = 3
        return types.states.TaskState.RUNNING

    def check_state(self) -> types.states.TaskState:
        logger.info('Checking state of deployment %s', self)
        if self.count <= 0:
            return types.states.TaskState.FINISHED

        self.count -= 1
        return types.states.TaskState.RUNNING

    def finish(self) -> None:
        logger.info('Finishing deployment %s', self)
        self.count = -1

    def user_logged_in(self, username: str) -> None:
        logger.info('User %s has logged in', username)

    def user_logged_out(self, username: str) -> None:
        logger.info('User %s has logged out', username)

    def error_reason(self) -> str:
        return 'No error'

    def destroy(self) -> types.states.TaskState:
        logger.info('Destroying deployment %s', self)
        self.count = -1
        return types.states.TaskState.FINISHED

    def cancel(self) -> types.states.TaskState:
        return self.destroy()
