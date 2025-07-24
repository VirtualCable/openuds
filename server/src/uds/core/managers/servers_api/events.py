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
import collections.abc


from django.conf import settings

from uds import models
from uds.core import consts, osmanagers, types
from uds.core.util import log
from uds.core.util.model import sql_now
from uds.REST.utils import rest_result

logger = logging.getLogger(__name__)


def process_log(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
    # Log level is an string, as in types.log.LogLevel
    if data.get('userservice_uuid', None):  # Log for an user service
        try:
            userservice = models.UserService.objects.get(uuid=data['userservice_uuid'])
            log.log(
                userservice,
                types.log.LogLevel.from_str(data['level']),
                data['message'],
                source=types.log.LogSource.SERVER,
            )
            return rest_result(consts.OK)
        except models.UserService.DoesNotExist:
            pass  # If not found, log on server

    log.log(
        server, types.log.LogLevel.from_str(data['level']), data['message'], source=types.log.LogSource.SERVER
    )

    return rest_result(consts.OK)


def process_login(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
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
        'deadline': 'dead line of service',  # The point in time when the service will be automatically removed, optional (None if not set)
        'max_idle': 'max idle time of service',  # The max time the service can be idle before being removed, optional (None if not set)
        'session_id': 'session id',  # The session id assigned to this login
        'ticket': 'ticket if any' # optional

    }
    """
    ticket: typing.Any = None
    if 'ticket' in data:
        # Do not invalidate tickets on debug mode, the will last for 1000 hours (41 days and 16 hours)
        ticket = models.TicketStore.get(data['ticket'], invalidate=not getattr(settings, 'DEBUG', False))
        # If ticket is included, user_service can be inside ticket or in data
        data['userservice_uuid'] = data.get('userservice_uuid', ticket['userservice_uuid'])

    userservice = models.UserService.objects.get(uuid=data['userservice_uuid'])
    server.set_actor_version(userservice)

    if not userservice.in_use:  # If already logged in, do not add a second login (windows does this i.e.)
        osmanagers.OSManager.logged_in(userservice, data['username'])

    # Get the source of the connection and a new session id
    src = userservice.get_connection_source()
    session_id = userservice.start_session()  # creates a session for every login requested

    osmanager: typing.Optional[osmanagers.OSManager] = userservice.get_osmanager_instance()
    max_idle = osmanager.max_idle() if osmanager else None

    logger.debug('Max idle: %s', max_idle)

    deadline = (
        userservice.deployed_service.get_deadline() if not osmanager or osmanager.ignore_deadline() else None
    )
    result = {
        'ip': src.ip,
        'hostname': src.hostname,
        'session_id': session_id,
        'deadline': deadline,  # For compatibility with old clients
        'max_idle': max_idle,  # Can be None
    }
    # If ticket is included, add it to result (the content of the ticket, not the ticket id itself)
    if ticket:
        result['ticket'] = ticket

    return rest_result(result)


def process_logout(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
    """Processes the REST logout event from a server

    data: {
        'userservice_uuid': 'uuid of user service',
        'session_id': 'session id',
    }

    Returns 'OK' if all went ok ({'result': 'OK', 'stamp': 'stamp'}), or an error if not ({'result': 'error', 'error': 'error description'}})
    """
    userservice = models.UserService.objects.get(uuid=data['userservice_uuid'])

    session_id = data['userservice_uuid']
    userservice.end_session(session_id)

    if userservice.in_use:  # If already logged out, do not add a second logout (windows does this i.e.)
        osmanagers.OSManager.logged_out(userservice, data['username'])
        osmanager: typing.Optional[osmanagers.OSManager] = userservice.get_osmanager_instance()
        if not osmanager or osmanager.is_removable_on_logout(userservice):
            logger.debug('Removable on logout: %s', osmanager)
            userservice.release()

    return rest_result(consts.OK)


def process_ping(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
    if 'stats' in data:
        server.stats = types.servers.ServerStats.from_dict(data['stats'])
        # Set stats on server
    server.last_ping = sql_now()

    return rest_result(consts.OK)


def process_ticket(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
    return rest_result(models.TicketStore.get(data['ticket'], invalidate=False))


def process_init(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
    # Init like on actor to allow "userServices" to initialize inside server
    # Currently unimplemented (just an idea, anotated here for future reference)
    return rest_result(consts.OK)


# Dictionary of processors by type
PROCESSORS: typing.Final[
    collections.abc.Mapping[str, collections.abc.Callable[['models.Server', dict[str, typing.Any]], typing.Any]]
] = {
    'log': process_log,
    'login': process_login,
    'logout': process_logout,
    'ping': process_ping,
    'ticket': process_ticket,
    'init': process_init,
}


def process(server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
    """Processes the event data
    Valid events are (in key 'type'):
    * log: A log message (to server or userservice)
    * login: A login has been made (to an userservice)
    * logout: A logout has been made (to an userservice)
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
        logger.exception('Exception processing event %s: %s', data, e)
        return rest_result('error', error=str(e))
