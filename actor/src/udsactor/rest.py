# -*- coding: utf-8 -*-
#
# Copyright (c) 2019 Virtual Cable S.L.
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
# pylint: disable=invalid-name
import warnings
import json
import logging
import typing

import requests

from . import types
from .info import VERSION

class RESTError(Exception):
    ERRCODE = 0

class RESTConnectionError(RESTError):
    ERRCODE = -1

# Errors ""raised"" from broker
class RESTInvalidKeyError(RESTError):
    ERRCODE = 1

class RESTUnmanagedHostError(RESTError):
    ERRCODE = 2

class RESTUserServiceNotFoundError(RESTError):
    ERRCODE = 3

class RESTOsManagerError(RESTError):
    ERRCODE = 4

class REST:
    def __init__(self, host: str, validateCert: bool) -> None:
        self.host = host
        self.validateCert = validateCert
        self.url = "https://{}/uds/rest/".format(self.host)
        # Disable logging requests messages except for errors, ...
        logging.getLogger("requests").setLevel(logging.CRITICAL)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        try:
            warnings.simplefilter("ignore")  # Disables all warnings
        except Exception:
            pass

    @property
    def _headers(self) -> typing.MutableMapping[str, str]:
        return {'content-type': 'application/json'}

    def _actorPost(
            self,
            method: str,  # i.e. 'initialize', 'ready', ....
            payLoad: typing.MutableMapping[str, typing.Any],
            headers: typing.Optional[typing.MutableMapping[str, str]] = None
        ) -> typing.Any:
        headers = headers or self._headers
        try:
            result = requests.post(self.url + 'actor/v2/' + method, data=json.dumps(payLoad), headers=headers, verify=self.validateCert)
            if result.ok:
                return result.json()['result']
        except requests.ConnectionError as e:
            raise RESTConnectionError(str(e))
        except Exception as e:
            pass

        raise RESTError(result.content)

    def enumerateAuthenticators(self) -> typing.Iterable[types.AuthenticatorType]:
        try:
            result = requests.get(self.url + 'auth/auths', headers=self._headers, verify=self.validateCert, timeout=4)
            if result.ok:
                for v in sorted(result.json(), key=lambda x: x['priority']):
                    yield types.AuthenticatorType(
                        authId=v['authId'],
                        authSmallName=v['authSmallName'],
                        auth=v['auth'],
                        type=v['type'],
                        priority=v['priority'],
                        isCustom=v['isCustom']
                    )
        except Exception:
            pass

    def register(  #pylint: disable=too-many-arguments, too-many-locals
            self,
            auth: str,
            username: str,
            password: str,
            hostname: str,
            ip: str,
            mac: str,
            preCommand: str,
            runOnceCommand: str,
            postCommand: str,
            logLevel: int
        ) -> str:
        """
        Raises an exception if could not register, or registers and returns the "authorization token"
        """
        data = {
            'username': username + '@' + auth,
            'hostname': hostname,
            'ip': ip,
            'mac': mac,
            'pre_command': preCommand,
            'run_once_command': runOnceCommand,
            'post_command': postCommand,
            'log_level': logLevel
        }

        # First, try to login to REST api
        try:
            # First, try to login
            authInfo = {'auth': auth, 'username': username, 'password': password}
            headers = self._headers
            result = requests.post(self.url + 'auth/login', data=json.dumps(authInfo), headers=headers, verify=self.validateCert)
            if not result.ok or result.json()['result'] == 'error':
                raise Exception()  # Invalid credentials

            headers['X-Auth-Token'] = result.json()['token']

            result = requests.post(self.url + 'actor/v2/register', data=json.dumps(data), headers=headers, verify=self.validateCert)
            if result.ok:
                return result.json()['result']
        except requests.ConnectionError as e:
            raise RESTConnectionError(str(e))
        except RESTError:
            raise
        except Exception as e:
            raise RESTError('Invalid credentials')

        raise RESTError(result.content)

    def initialize(self, token: str, interfaces: typing.Iterable[types.InterfaceInfoType]) -> types.InitializationResultType:
        # Generate id list from netork cards
        payload = {
            'token': token,
            'version': VERSION,
            'id': [{'mac': i.mac, 'ip': i.ip} for i in interfaces]
        }
        r = self._actorPost('initialize', payload)
        os = r['os']
        return types.InitializationResultType(
            own_token=r['own_token'],
            unique_id=r['unique_id'].lower() if r['unique_id'] else None,
            max_idle=r['max_idle'],
            os=types.ActorOsConfigurationType(
                action=os['action'],
                name=os['name'],
                username=os.get('username'),
                password=os.get('password'),
                new_password=os.get('new_password'),
                ad=os.get('ad'),
                ou=os.get('ou')
            ) if r['os'] else None
        )

    def ready(self, own_token: str, secret: str, ip: str, port: int) -> types.CertificateInfoType:
        payload = {
            'token': own_token,
            'secret': secret,
            'ip': ip,
            'port': port
        }
        result = self._actorPost('ready', payload)

        return types.CertificateInfoType(
            private_key=result['private_key'],
            server_certificate=result['server_certificate'],
            password=result['password']
        )

    def notifyIpChange(self, own_token: str, secret: str, ip: str, port: int) -> types.CertificateInfoType:
        payload = {
            'token': own_token,
            'secret': secret,
            'ip': ip,
            'port': port
        }
        result = self._actorPost('ipchange', payload)

        return types.CertificateInfoType(
            private_key=result['private_key'],
            server_certificate=result['server_certificate'],
            password=result['password']
        )

    def login(self, own_token: str, username: str) -> types.LoginResultInfoType:
        payload = {
            'token': own_token,
            'username': username
        }
        result = self._actorPost('login', payload)
        return types.LoginResultInfoType(ip=result['ip'], hostname=result['hostname'], dead_line=result['dead_line'])

    def logout(self, own_token: str, username: str) -> None:
        payload = {
            'token': own_token,
            'username': username
        }
        self._actorPost('logout', payload)


    def log(self, own_token: str, level: int, message: str) -> None:
        payLoad = {
            'token': own_token,
            'level': level,
            'message': message
        }
        self._actorPost('log', payLoad)  # Ignores result...
