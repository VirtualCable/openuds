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
import uuid
import warnings
import json
import logging
import typing

import requests

from . import types

from .info import VERSION
from .utils import exceptionToMessage
from .log import logger


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
    def headers(self) -> typing.MutableMapping[str, str]:
        return {'content-type': 'application/json'}

    def enumerateAuthenticators(self) -> typing.Iterable[types.AuthenticatorType]:
        try:
            result = requests.get(self.url + 'auth/auths', headers=self.headers, verify=self.validateCert, timeout=4)
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


    def register(self, auth: str, username: str, password: str, ip: str, mac: str, preCommand: str, runOnceCommand: str, postCommand: str, logLevel: int) -> str:
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
            # First, try to login
            authInfo = {'auth': auth, 'username': username, 'password': password }
            headers = self.headers
            result = requests.post(self.url + 'auth/login', data=json.dumps(authInfo), headers=headers, verify=self.validateCert)
            if not result.ok or result.json()['result'] == 'error':
                raise Exception()  # Invalid credentials
        except (requests.ConnectionError, requests.ConnectTimeout) as e:
            raise RESTConnectionError(str(e))
        except Exception as e:
            raise RESTError('Invalid credentials')

        try:
            headers['X-Auth-Token'] = result.json()['token']
            result = requests.post(self.url + 'actor/v2/register', data=json.dumps(data), headers=headers, verify=self.validateCert)
            if result.ok:
                return result.json()['result']
        except (requests.ConnectionError, requests.ConnectTimeout) as e:
            raise RESTConnectionError(str(e))
        except Exception as e:
            pass

        raise RESTError(result.content)

    def _getUrl(self, method, key=None, ids=None):
        url = self.url + method
        params = []
        if key is not None:
            params.append('key=' + key)
        if ids is not None:
            params.append('id=' + ids)
            params.append('version=' + VERSION)

        if len(params) > 0:
            url += '?' + '&'.join(params)

        return url

    def _request(self, url, data=None):
        try:
            if data is None:
                # Old requests version does not support verify, but they do not checks ssl certificate by default
                if self.newerRequestLib:
                    r = requests.get(url, verify=self.validateCert)
                else:
                    logger.debug('Requesting with old')
                    r = requests.get(url)  # Always ignore certs??
            else:
                if data == '':
                    data = '{"dummy": true}'  # Ensures no proxy rewrites POST as GET because body is empty...
                if self.newerRequestLib:
                    r = requests.post(url, data=data, headers={'content-type': 'application/json'}, verify=self.validateCert)
                else:
                    logger.debug('Requesting with old')
                    r = requests.post(url, data=data, headers={'content-type': 'application/json'})

            # From versions of requests, content maybe bytes or str. We need str for json.loads
            content = r.content
            if not isinstance(content, str):
                content = content.decode('utf8')
            r = json.loads(content)  # Using instead of r.json() to make compatible with oooold rquests lib versions
        except requests.exceptions.RequestException as e:
            raise ConnectionError(e)
        except Exception as e:
            raise ConnectionError(exceptionToMessage(e))

        ensureResultIsOk(r)

        return r

    @property
    def isConnected(self):
        return self.uuid is not None

    def test(self):
        url = self._getUrl('test', self.masterKey)
        return self._request(url)['result']

    def init(self, ids):
        '''
        Ids is a comma separated values indicating MAC=ip
        Server returns:
          uuid, mac
          Optionally can return an third parameter, that is max "idle" request time
        '''
        logger.debug('Invoking init')
        url = self._getUrl('init', key=self.masterKey, ids=ids)
        res = self._request(url)['result']
        logger.debug('Got response parameters: {}'.format(res))
        self.uuid, self.mac = res[0:2]
        # Optional idle parameter
        try:
            self.idle = int(res[2])
            if self.idle < 30:
                self.idle = None  # No values under 30 seconds are allowed :)
        except Exception:
            self.idle = None

        return self.uuid

    def postMessage(self, msg, data, processData=True):
        logger.debug('Invoking post message {} with data {}'.format(msg, data))

        if self.uuid is None:
            raise ConnectionError('REST api has not been initialized')

        if processData:
            if data and not isinstance(data, str):
                data = data.decode('utf8')
            data = json.dumps({'data': data})
        url = self._getUrl('/'.join([self.uuid, msg]))
        return self._request(url, data)['result']

    def notifyComm(self, url):
        logger.debug('Notifying comms {}'.format(url))
        return self.postMessage('notifyComms', url)

    def login(self, username):
        logger.debug('Notifying login {}'.format(username))
        return self.postMessage('login', username)

    def logout(self, username):
        logger.debug('Notifying logout {}'.format(username))
        return self.postMessage('logout', username)

    def information(self):
        logger.debug('Requesting information'.format())
        return self.postMessage('information', '')

    def setReady(self, ipsInfo, hostName=None):
        logger.debug('Notifying readyness: {}'.format(ipsInfo))
        #    data = ','.join(['{}={}'.format(v[0], v[1]) for v in ipsInfo])
        data = {
            'ips': ipsInfo,
            'hostname': hostName
        }
        return self.postMessage('ready', data)

    def notifyIpChanges(self, ipsInfo):
        logger.debug('Notifying ip changes: {}'.format(ipsInfo))
        data = ','.join(['{}={}'.format(v[0], v[1]) for v in ipsInfo])
        return self.postMessage('ip', data)

    def getTicket(self, ticketId, secure=False):
        url = self._getUrl('ticket/' + ticketId, self.masterKey) + "&secure={}".format('1' if secure else '0')
        return self._request(url)['result']


    def log(self, logLevel, message):
        data = json.dumps({'message': message, 'level': logLevel})
        return self.postMessage('log', data, processData=False)

