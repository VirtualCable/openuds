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
import asyncio
import aiohttp


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
    session.headers.update({'Scrambler': res['scrambler']})

    # Fix user agent, so we indicate we are on Linux
    session.headers.update({'User-Agent': 'SampleClient/1.0 (Linux)'})


async def logout(session: aiohttp.ClientSession) -> None:
    response = await session.get(REST_URL + 'auth/logout')

    if not response.ok:
        raise LogoutException('Error logging out')


async def list_services(
    session: aiohttp.ClientSession,
) -> typing.List[typing.MutableMapping[str, typing.Any]]:
    response = await session.get(
        REST_URL + 'connection',
    )
    if not response.ok:
        raise RESTException(f'Error requesting ticket: {response.status} {response.reason}')

    return (await response.json())['result']['services']


async def get_uds_link(
    session: aiohttp.ClientSession,
    service_id: str,
    transport_id: str,
) -> str:
    url = f'{REST_URL}connection/{service_id}/{transport_id}/udslink'
    print('Requesting ticket from', url)
    response = await session.get(
        url,
    )
    if not response.ok:
        raise RESTException(f'Error requesting ticket: {response.status} {response.reason}')

    return (await response.json())['result']


async def main():
    async with aiohttp.ClientSession() as session:
        # request_pools()  # Not logged in, this will generate an error
        await login(session)  # Will raise an exception if error
        # pools = request_pools()
        # for i in pools:
        #    print(i['id'], i['name'])
        services = await list_services(
            session=session,
        )
        for i in services:
            print(f'Service: {i}')
            service_id = i['id']
            transport_id = i['transports'][0]['id']
            print(f'Getting link for service {service_id} and transport {transport_id}')
            link = await get_uds_link(
                session=session,
                service_id=service_id,
                transport_id=transport_id,
            )
            print(f'Link is {link}')

        await logout(session)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
