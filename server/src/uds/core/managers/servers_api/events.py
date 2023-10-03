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

from uds import models
from uds.core import consts, osmanagers, types
from uds.core.util import log
from uds.core.util.model import getSqlDatetime, getSqlStamp
from uds.REST.utils import rest_result

logger = logging.getLogger(__name__)


def process_log(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    # Log level is an string, as in log.LogLevel
    if 'userservice_uuid' in data:  # Log for an user service
        userService = models.UserService.objects.get(uuid=data['userservice_uuid'])
        log.doLog(
            userService, log.LogLevel.fromStr(data['level']), data['message'], source=log.LogSource.SERVER
        )
    else:
        log.doLog(server, log.LogLevel.fromStr(data['level']), data['message'], source=log.LogSource.SERVER)

    return rest_result(consts.OK)


def process_login(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    """Processes the REST login event from a server

    data: {
        'userservice_uuid': 'uuid of user service',
        'username': 'username',
        'ticket': 'ticket if any' # optional
    }

    Returns a dict with the following keys:

    {
        'ip': 'ip of connection origin',
        'hostname': 'hostname of connection origin',
        'dead_line': 'dead line of service',  # The point in time when the service will be automatically removed, optional (None if not set)
        'max_idle': 'max idle time of service',  # The max time the service can be idle before being removed, optional (None if not set)
        'session_id': 'session id',  # The session id assigned to this login
        'ticket': 'ticket if any' # optional

    }


    """
    ticket: typing.Any = None
    if 'ticket' in data:
        ticket = models.TicketStore.get(data['ticket'], invalidate=True)
        # If ticket is included, user_service can be inside ticket or in data
        data['userservice_uuid'] = data.get('userservice_uuid', ticket['userservice_uuid'])
    
    userService = models.UserService.objects.get(uuid=data['userservice_uuid'])
    server.setActorVersion(userService)

    if not userService.in_use:  # If already logged in, do not add a second login (windows does this i.e.)
        osmanagers.OSManager.loggedIn(userService, data['username'])

    # Get the source of the connection and a new session id
    src = userService.getConnectionSource()
    session_id = userService.initSession()  # creates a session for every login requested

    osManager: typing.Optional[osmanagers.OSManager] = userService.getOsManagerInstance()
    maxIdle = osManager.maxIdle() if osManager else None

    logger.debug('Max idle: %s', maxIdle)

    deadLine = (
        userService.deployed_service.getDeadline() if not osManager or osManager.ignoreDeadLine() else None
    )
    result = {
        'ip': src.ip,
        'hostname': src.hostname,
        'session_id': session_id,
        'dead_line': deadLine,  # Can be None
        'max_idle': maxIdle,  # Can be None
    }
    # If ticket is included, add it to result (the content of the ticket, not the ticket id itself)
    if ticket:
        result['ticket'] = ticket

    return rest_result(result)


def process_logout(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    """Processes the REST logout event from a server

    data: {
        'userservice_uuid': 'uuid of user service',
        'session_id': 'session id',
    }

    Returns 'OK' if all went ok ({'result': 'OK', 'stamp': 'stamp'}), or an error if not ({'result': 'error', 'error': 'error description'}})
    """
    userService = models.UserService.objects.get(uuid=data['userservice_uuid'])

    session_id = data['userservice_uuid']
    userService.closeSession(session_id)

    if userService.in_use:  # If already logged out, do not add a second logout (windows does this i.e.)
        osmanagers.OSManager.loggedOut(userService, data['username'])
        osManager: typing.Optional[osmanagers.OSManager] = userService.getOsManagerInstance()
        if not osManager or osManager.isRemovableOnLogout(userService):
            logger.debug('Removable on logout: %s', osManager)
            userService.remove()

    return rest_result(consts.OK)


def process_ping(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    if 'stats' in data:
        server.stats = types.servers.ServerStats.fromDict(data['stats'])
        # Set stats on server
    server.last_ping = getSqlDatetime()

    return rest_result(consts.OK)


def process_ticket(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    return rest_result(models.TicketStore.get(data['ticket'], invalidate=True))


def process_init(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    # Init like on actor to allow "userServices" to initialize inside server
    # Currently unimplemented (just an idea, anotated here for future reference)
    return rest_result(consts.OK)

PROCESSORS: typing.Final[
    typing.Mapping[str, typing.Callable[['models.Server', typing.Dict[str, typing.Any]], typing.Any]]
] = {
    'log': process_log,
    'login': process_login,
    'logout': process_logout,
    'ping': process_ping,
    'ticket': process_ticket,
    'init': process_init,
}


def process(server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
    """Processes the event data
    Valid events are (in key 'type'):
    * log: A log message (to server or userService)
    * login: A login has been made (to an userService)
    * logout: A logout has been made (to an userService)
    * ping: A ping request (can include stats, etc...)
    * ticket: A ticket to obtain it's data
    """
    try:
        fnc = PROCESSORS[data['type']]
    except KeyError:
        logger.error('Invalid event type: %s', data.get('type', 'not_found'))
        return rest_result('error', error=f'Invalid event type {data.get("type", "not_found")}')

    try:
        return fnc(server, data)
    except Exception as e:
        logger.error('Exception processing event %s: %s', data, e)
        return rest_result('error', error=str(e))
