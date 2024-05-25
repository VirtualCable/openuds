# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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
import collections.abc
import requests

REST_URL: typing.Final[str] = 'http://172.27.0.1:8000/rest/'

# Global session
session = requests.Session()

# Hace login con el root, puede usarse cualquier autenticador y cualquier usuario, pero en la 1.5 solo está implementado poder hacer
# este tipo de login con el usuario "root"
def login():
    
    # parameters = '{ "auth": "admin", "username": "root", "password": "temporal" }'
    parameters = { "auth": "casa", "username": "172.27.0.1", "password": "" }

    response = session.post(REST_URL + 'auth/login', parameters)

    if response.status_code // 100 != 2:  # Authentication error due to incorrect parameters, bad request, etc...
        print("Authentication error")
        return -1

    # resp contiene las cabeceras, content el contenido de la respuesta (que es json), pero aún está en formato texto
    res = response.json()
    print(res)
    if res['result'] != 'ok':  # Authentication error
        print("Authentication error")
        return -1

    session.headers['X-Auth-Token'] = res['token']

    return 0

def logout():
    response = session.get(REST_URL + 'auth/logout')

    if response.status_code // 100 != 2:  # error due to incorrect parameters, bad request, etc...
        print("Error requesting logout %s" % response.status_code)
        return -1

    # Return value of logout method is nonsense (returns always done right now, but it's not important)

    return 0

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

def request_services() -> dict[str, typing.Any]:
    response = session.get(REST_URL + 'connection')
    if response.status_code // 100 != 2:
        print("Error requesting services %s" % response.status_code)
        print(response.text)
        return {}

    return response.json()

if __name__ == '__main__':
    if login() == 0:  # If we can log in, will get the pools correctly
        res = request_services()
        print(res)
        print(logout())

