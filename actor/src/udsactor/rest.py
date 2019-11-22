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


# Disable warnings log messages
try:
    import urllib3  # @UnusedImport @UnresolvedImport
except Exception:
    from requests.packages import urllib3  # @Reimport @UnresolvedImport

try:
    urllib3.disable_warnings()  # @UndefinedVariable
    warnings.simplefilter("ignore")
except Exception:
    pass  # In fact, isn't too important, but will log warns to logging file

# Constants

def ensureResultIsOk(result: typing.Any) -> None:
    if 'error' not in result:
        return

    for i in (RESTInvalidKeyError, RESTUnmanagedHostError, RESTUserServiceNotFoundError, RESTOsManagerError):
        if result['error'] == i.ERRCODE:
            raise i(result['result'])

    err = RESTError(result['result'])
    err.ERRCODE = result['error']
    raise err


class REST:
    def __init__(self, host: str, validateCert: bool) -> None:
        self.host = host
        self.validateCert = validateCert
        self.url = "https://{}/uds/rest/".format(self.host)
        # Disable logging requests messages except for errors, ...
        logging.getLogger("requests").setLevel(logging.CRITICAL)
        # Tries to disable all warnings
        try:
            warnings.simplefilter("ignore")  # Disables all warnings
        except Exception:
            pass

    @property
    def _headers(self) -> typing.MutableMapping[str, str]:
        return {'content-type': 'application/json'}

    def _login(self, auth: str, username: str, password: str) -> typing.MutableMapping[str, str]:
        try:
            # First, try to login
            authInfo = {'auth': auth, 'username': username, 'password': password}
            headers = self._headers
            result = requests.post(self.url + 'auth/login', data=json.dumps(authInfo), headers=headers, verify=self.validateCert)
            if not result.ok or result.json()['result'] == 'error':
                raise Exception()  # Invalid credentials
        except requests.ConnectionError as e:
            raise RESTConnectionError(str(e))
        except Exception as e:
            raise RESTError('Invalid credentials')

        headers['X-Auth-Token'] = result.json()['token']

        return headers


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


    def register(  #pylint: disable=too-many-arguments
            self,
            auth: str,
            username: str,
            password: str,
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
            'username': username,
            'ip': ip,
            'mac': mac,
            'pre_command': preCommand,
            'run_once_command': runOnceCommand,
            'post_command': postCommand,
            'log_level': logLevel
        }

        try:
            headers = self._login(auth, username, password)
            result = requests.post(self.url + 'actor/v2/register', data=json.dumps(data), headers=headers, verify=self.validateCert)
            if result.ok:
                return result.json()['result']
        except requests.ConnectionError as e:
            raise RESTConnectionError(str(e))
        except RESTError:
            raise
        except Exception:
            pass

        raise RESTError(result.content)

    def readConfig(
            self,
            auth: str,
            username: str,
            password: str,
            mac: str,
            config: typing.Optional[types.ActorConfigurationType] = None
        ) -> typing.Optional[typing.MutableMapping[str, typing.Any]]:
        try:
            res = None
            headers = self._login(auth, username, password)
            result = requests.post(self.url + 'actor/v2/config', data=json.dumps(mac), headers=headers, verify=self.validateCert)
            if result.ok:
                res = result.json()['result']
        except Exception:
            pass

        if config:
            config
        return None
