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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

import json
import sys
import typing

import requests

rest_url = 'http://172.27.0.1:8000/uds/rest/'

session = requests.Session()
session.headers.update({'Content-Type': 'application/json'})


class RESTException(Exception):
    pass


class AuthException(RESTException):
    pass


class LogoutException(RESTException):
    pass


# Hace login con el root, puede usarse cualquier autenticador y cualquier usuario, pero en la 1.5 solo está implementado poder hacer
# este tipo de login con el usuario "root"
def login():
    # parameters = '{ "auth": "admin", "username": "root", "password": "temporal" }'
    # parameters = '{ "auth": "interna", "username": "admin", "password": "temporal" }'
    parameters = {'auth': 'interna', 'username': 'admin', 'password': 'temporal'}

    response = session.post(rest_url + 'auth/login', json=parameters)

    if not response.ok:
        raise AuthException('Error logging in')

    # resp contiene las cabeceras, content el contenido de la respuesta (que es json), pero aún está en formato texto
    res = response.json()
    print(res)

    if res['result'] != 'ok':  # Authentication error
        raise AuthException('Authentication error')

    session.headers.update({'X-Auth-Token': res['token']})


def logout():
    response = session.get(rest_url + 'auth/logout')

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


def request_pools() -> typing.List[typing.MutableMapping[str, typing.Any]]:
    response = session.get(rest_url + 'servicespools/overview')
    if not response.ok:
        raise RESTException('Error requesting pools')

    return response.json()


def request_ticket(
    username: str,
    authSmallName: str,
    groups: typing.Union[typing.List[str], str],
    servicePool: str,
    realName: typing.Optional[str] = None,
    transport: typing.Optional[str] = None,
    force: bool = False
) -> typing.MutableMapping[str, typing.Any]:
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
    response = session.put(
        rest_url + 'tickets/create',
        json=data
    )
    if not response.ok:
        raise RESTException('Error requesting ticket')
    
    return response.json()


if __name__ == '__main__':
    # request_pools()  # Not logged in, this will generate an error
    login()  # Will raise an exception if error
    #pools = request_pools()
    #for i in pools:
    #    print(i['id'], i['name'])
    ticket = request_ticket(
        username='adolfo',
        authSmallName='172.27.0.1:8000',
        groups=['adolfo', 'dkmaster'],
        servicePool='5d045a19-54b5-541b-ba56-447b0622191c',
        realName='Adolfo Gómez',
        force=True
    )
    print(ticket)

    logout()
