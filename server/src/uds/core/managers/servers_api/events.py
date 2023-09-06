# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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

from uds.core.util.model import getSqlDatetime
from uds.core import types, consts

from uds.REST.utils import rest_result
from uds import models
from uds.core.util import log

logger = logging.getLogger(__name__)


def process_log(data: typing.Dict[str, typing.Any]) -> typing.Any:
    if 'user_service' in data:  # Log for an user service
        userService = models.UserService.objects.get(uuid=data['user_service'])
        log.doLog(
            userService, log.LogLevel.fromStr(data['level']), data['message'], source=log.LogSource.SERVER
        )
    else:
        server = models.Server.objects.get(token=data['token'])
        log.doLog(server, log.LogLevel.fromStr(data['level']), data['message'], source=log.LogSource.SERVER)

    return rest_result(consts.OK)


def process_login(data: typing.Dict[str, typing.Any]) -> typing.Any:
    userService = models.UserService.objects.get(uuid=data['user_service'])
    userService.setInUse(True)

    return rest_result(consts.OK)


def process_logout(data: typing.Dict[str, typing.Any]) -> typing.Any:
    userService = models.UserService.objects.get(uuid=data['user_service'])
    userService.setInUse(False)

    return rest_result(consts.OK)


def process_ping(data: typing.Dict[str, typing.Any]) -> typing.Any:
    server = models.Server.objects.get(token=data['token'])
    if 'stats' in data:
        # Load anc check stats
        stats = types.servers.ServerStatsType.fromDict(data['stats'])
        # Set stats on server
        server.properties['stats'] = stats.asDict()
    server.properties['last_ping'] = getSqlDatetime()

    return rest_result(consts.OK)


PROCESSORS: typing.Final[typing.Mapping[str, typing.Callable[[typing.Dict[str, typing.Any]], typing.Any]]] = {
    'log': process_log,
    'login': process_login,
    'logout': process_logout,
    'ping': process_ping,
}


def process(data: typing.Dict[str, typing.Any]) -> typing.Any:
    """Processes the event data
    Valid events are (in key 'type'):
    * log: A log message (to server or userService)
    * login: A login has been made (to an userService)
    * logout: A logout has been made (to an userService)
    * ping: A ping request (can include stats, etc...)
    """
    try:
        fnc = PROCESSORS[data['type']]
    except KeyError:
        logger.error('Invalid event type: %s', data.get('type', 'not_found'))
        return rest_result('error', error=f'Invalid event type {data.get("type", "not_found")}')

    try:
        fnc(data)
    except Exception as e:
        logger.error('Exception processing event %s: %s', data, e)
        return rest_result('error', error=str(e))
