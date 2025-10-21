#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# Copyright (c) 2021 Virtual Cable S.L.U.
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

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import asyncio
import aiohttp
import enum
import argparse
import json

REST_URL: str = 'http://172.27.0.1:8000/uds/rest/'


class RESTException(Exception):
    pass


class AuthException(RESTException):
    pass


class LogoutException(RESTException):
    pass


class CalendarActions(enum.StrEnum):
    PUBLISH = 'PUBLISH'
    CACHEL1 = 'CACHEL1'
    CACHEL2 = 'CACHEL2'
    INITIAL = 'INITIAL'
    MAX = 'MAX'
    ADD_TRANSPORT = 'ADD_TRANSPORT'
    REMOVE_TRANSPORT = 'REMOVE_TRANSPORT'
    REMOVE_ALL_TRANSPORTS = 'REMOVE_ALL_TRANSPORTS'
    ADD_GROUP = 'ADD_GROUP'
    REMOVE_GROUP = 'REMOVE_GROUP'
    REMOVE_ALL_GROUPS = 'REMOVE_ALL_GROUPS'
    IGNORE_UNUSED = 'IGNORE_UNUSED'
    REMOVE_USERSERVICES = 'REMOVE_USERSERVICES'
    STUCK_USERSERVICES = 'STUCK_USERSERVICES'
    CLEAN_CACHE_L1 = 'CLEAN_CACHE_L1'
    CLEAN_CACHE_L2 = 'CLEAN_CACHE_L2'


# Hace login con el root, puede usarse cualquier autenticador y cualquier usuario, pero en la 1.5 solo está implementado poder hacer
# este tipo de login con el usuario "root"
async def login(session: aiohttp.ClientSession, auth: str, username: str, password: str) -> None:
    # parameters = '{ "auth": "admin", "username": "root", "password": "temporal" }'
    # parameters = '{ "auth": "interna", "username": "admin", "password": "temporal" }'
    # parameters = {'auth': 'interna', 'username': 'admin', 'password': 'temporal'}
    parameters = {'auth': auth, 'username': username, 'password': password}

    response = await session.post(REST_URL + 'auth/login', json=parameters)

    if not response.ok:
        raise AuthException('Error logging in')

    # resp contiene las cabeceras, content el contenido de la respuesta (que es json), pero aún está en formato texto
    res = await response.json()
    print(res)

    if res['result'] != 'ok':  # Authentication error
        raise AuthException('Authentication error')

    session.headers.update({'X-Auth-Token': res['token']})
    session.headers.update({'Scrambler': res['scrambler']})

    # Fix user agent, so we indicate we are on Linux
    session.headers.update({'User-Agent': 'SampleClient/1.0 (Linux)'})


async def logout(session: aiohttp.ClientSession) -> None:
    response = await session.get(REST_URL + 'auth/logout')

    if not response.ok:
        raise LogoutException('Error logging out')


async def add_calendar_action(
    session: aiohttp.ClientSession,
    service_pool_id: str,
    action: str,
    calendar_id: str,
    at_start: bool = True,
    events_offset: int = 0,
    params: typing.Optional[dict[str, typing.Any]] = None,
) -> None:
    data = {
        'action': action,
        'calendar': '',
        'calendar_id': calendar_id,
        'at_start': at_start,
        'events_offset': events_offset,
        'params': params or {},
    }

    # Headers are already set in session, so we only need to set the parameters
    response = await session.put(REST_URL + f'/servicespools/{service_pool_id}/actions', json=data)

    if not response.ok:
        raise RESTException(f'Error adding calendar action: {response.status} {response.reason}')


async def main():
    args = argparse.ArgumentParser()
    args.add_argument('--url', type=str, required=True)
    args.add_argument('--auth', type=str, required=True)
    args.add_argument('--username', type=str, required=True)
    args.add_argument('--password', type=str, required=True)
    args.add_argument('--service-pool-id', type=str, required=True)
    # Actions is one of the values of CalendarActions
    args.add_argument('--action', type=str, choices=list(CalendarActions), required=True)
    args.add_argument('--calendar-id', type=str, required=True)
    args.add_argument('--at-end', action='store_true', default=False)
    args.add_argument('--events-offset', type=int, default=0)
    args.add_argument('--params', type=str, default=None)  # Must be a json string
    
    options = args.parse_args()
    
    if options.params is not None:
        options.params = json.loads(options.params)
        
    async with aiohttp.ClientSession() as session:
        # request_pools()  # Not logged in, this will generate an error
        await login(session, options.auth, options.username, options.password)

        # {"action":"PUBLISH","calendar":"","calendar_id":"370b5b59-687e-5a94-8c30-1c9eda6ac005","at_start":true,"events_offset":222,"params":{}}
        await add_calendar_action(
            session,
            service_pool_id=options.service_pool_id,
            action=options.action,
            calendar_id=options.calendar_id,
            at_start=not options.at_end,
            events_offset=options.events_offset,
            params=options.params,
        )
        # await add_calendar_action(
        #     session,
        #     service_pool_id='4f416484-711c-5faf-93b2-eb4a2eb3458e',
        #     action='PUBLISH',
        #     calendar_id='c1221a6d-3848-5fa3-ae98-172662c0f554',
        #     at_start=True,
        #     events_offset=222,
        # )

        await logout(session)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
