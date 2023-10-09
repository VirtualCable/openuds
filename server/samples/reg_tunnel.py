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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import requests
import argparse
import socket

REST_URL: typing.Final[str] = 'http{ssl}://{host}{port}/uds/rest/'


class RESTException(Exception):
    pass


class AuthException(RESTException):
    pass


class LogoutException(RESTException):
    pass


def registerWithBroker(
    auth_uuid: str,
    username: str,
    password: str,
    broker_host: str,
    tunnel_ip: str,
    tunnel_hostname: typing.Optional[str] = None,
    broker_port: typing.Optional[int] = None,
    ssl: bool = True,
    verify: bool = True,
) -> str:
    sport = (
        ''
        if not broker_port
        else ':' + str(broker_port)
        if (ssl and broker_port != 443) or (not ssl and broker_port != 80)
        else ''
    )
    brokerURL = REST_URL.format(ssl='s' if ssl else '', host=broker_host, port=sport)
    print(f'Registering tunnel with broker at {brokerURL}')
    
    tunnel_hostname = tunnel_hostname or socket.gethostname()

    session = requests.Session()

    # First, try to login
    with session.post(
        brokerURL + '/auth/login',
        json={'auth_id': auth_uuid, 'username': username, 'password': password},
        verify=verify,
    ) as r:
        if not r.ok:
            raise Exception('Invalid credentials supplied')
        session.headers.update({'X-Auth-Token': r.json()['token']})
    print('Logged in')

    with session.post(
        brokerURL + '/tunnel/register',
        json={'ip': tunnel_ip, 'hostname': tunnel_hostname},
        verify=False,
    ) as r:
        if r.ok:
            return r.json()['result']
        raise Exception(r.content)


def main():
    parser = argparse.ArgumentParser(description='Register a tunnel with UDS Broker')
    parser.add_argument(
        '--auth-uuid',
        help='UUID of authenticator to use',
        default='00000000-0000-0000-0000-000000000000',
    )
    parser.add_argument(
        '--username',
        help='Username to use (must have administator privileges)',
        required=True,
    )
    parser.add_argument(
        '--password',
        help='Password to use',
        required=True,
    )
    parser.add_argument(
        '--broker-host',
        help='Broker host to connect to',
        required=True,
    )
    parser.add_argument(
        '--broker-port',
        help='Broker port to connect to',
        type=int,
        default=None,
        required=False,
    )
    parser.add_argument(
        '--tunnel-ip',
        help='IP of tunnel server',
        required=True,
    )
    parser.add_argument(
        '--tunnel-hostname',
        help=f'Hostname of tunnel server (defaults to {socket.gethostname()})',
        required=False,
    )
    parser.add_argument(
        '--no-ssl',
        help='Disable SSL in connection to broker',
        action='store_true',
    )
    parser.add_argument(
        '--no-verify',
        help='Disable SSL certificate verification',
        action='store_true',
    )
    
    args = parser.parse_args()
    
    try:
        token = registerWithBroker(
            auth_uuid=args.auth_uuid,
            username=args.username,
            password=args.password,
            broker_host=args.broker_host,
            tunnel_ip=args.tunnel_ip,
            tunnel_hostname=args.tunnel_hostname,
            broker_port=args.broker_port,
            ssl=not args.no_ssl,
            verify=not args.no_verify,
        )
        print(f'Registered with token "{token}"')
    except Exception as e:
        print(f'Error registering tunnel: {e}')




if __name__ == "__main__":
    main()
