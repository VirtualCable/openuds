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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import collections.abc
import asyncio
import aiohttp
import collections.abc


REST_URL: typing.Final[str] = 'http://172.27.0.1:8000/uds/rest/'

class RESTException(Exception):
    pass


class AuthException(RESTException):
    pass


class LogoutException(RESTException):
    pass


# Hace login con el root, puede usarse cualquier autenticador y cualquier usuario, pero en la 1.5 solo está implementado poder hacer
# este tipo de login con el usuario "root"
async def login(session: aiohttp.ClientSession) -> None:
    # parameters = '{ "auth": "admin", "username": "root", "password": "temporal" }'
    # parameters = '{ "auth": "interna", "username": "admin", "password": "temporal" }'
    parameters = {'auth': 'interna', 'username': 'admin', 'password': 'temporal'}

    response = await session.post(REST_URL + 'auth/login', json=parameters)

    if not response.ok:
        raise AuthException('Error logging in')

    # resp contiene las cabeceras, content el contenido de la respuesta (que es json), pero aún está en formato texto
    res = await response.json()
    print(res)

    if res['result'] != 'ok':  # Authentication error
        raise AuthException('Authentication error')

    session.headers.update({'X-Auth-Token': res['token']})


async def logout(session: aiohttp.ClientSession) -> None:
    response = await session.get(REST_URL + 'auth/logout')

    if not response.ok:
        raise LogoutException('Error logging out')


# Sample response from request_pools
# [
#     {
#        u'initial_srvs': 0,
#        u'name': u'WinAdolfo',
#        u'max_srvs': 0,
#        u'comments': u'',
#        u'id': 6,
#        u'state': u'A',
#        u'user_services_count': 3,
#        u'cache_l2_srvs': 0,
#        u'service_id': 9,
#        u'provider_id': 2,
#        u'cache_l1_srvs': 0,
#        u'restrained': False}
# ]


async def request_pools(session: aiohttp.ClientSession) -> list[collections.abc.MutableMapping[str, typing.Any]]:
    response = await session.get(REST_URL + 'servicespools/overview')
    if not response.ok:
        raise RESTException('Error requesting pools')

    return await response.json()

async def request_ticket(
    session: aiohttp.ClientSession,
    username: str,
    authSmallName: str,
    groups: typing.Union[list[str], str],
    servicePool: str,
    realName: typing.Optional[str] = None,
    transport: typing.Optional[str] = None,
    force: bool = False
) -> collections.abc.MutableMapping[str, typing.Any]:
    data = {
        'username': username,
        'authSmallName': authSmallName,
        'groups': groups,
        'servicePool': servicePool,
        'force': 'true' if force else 'false'
    }
    if realName:
        data['realname'] = realName
    if transport:
        data['transport'] = transport
    response = await session.put(
        REST_URL + 'tickets/create',
        json=data
    )
    if not response.ok:
        raise RESTException('Error requesting ticket: %s (%s)' % (response.status, response.reason))
    
    return await response.json()


async def main():
    async with aiohttp.ClientSession() as session:
        # request_pools()  # Not logged in, this will generate an error
        await login(session)  # Will raise an exception if error
        #pools = request_pools()
        #for i in pools:
        #    print(i['id'], i['name'])
        ticket = await request_ticket(
            session=session,
            username='adolfo',
            authSmallName='172.27.0.1:8000',
            groups=['adolfo', 'dkmaster'],
            servicePool='6201b357-c4cd-5463-891e-71441a25faee',
            realName='Adolfo Gómez',
            force=True
        )
        print(ticket)

        await logout(session)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
