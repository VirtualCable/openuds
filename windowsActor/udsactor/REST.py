# -*- coding: utf-8 -*-
#
# Copyright (c) 201 Virtual Cable S.L.
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

# pylint: disable-msg=E1101,W0703

from __future__ import unicode_literals

import requests
import logging
import json
import uuid

class RESTError(Exception):
    ERRCODE = 0


class ConnectionError(RESTError):
    ERRCODE = -1


# Errors ""raised"" from broker
class InvalidKeyError(RESTError):
    ERRCODE = 1


class UnmanagedHostError(RESTError):
    ERRCODE = 2


class UserServiceNotFoundError(RESTError):
    ERRCODE = 3


class OsManagerError(RESTError):
    ERRCODE = 4


def ensureResultIsOk(result):
    if not 'error' in result:
        return

    for i in (InvalidKeyError, UnmanagedHostError, UserServiceNotFoundError, OsManagerError):
        if result['error'] == i.ERRCODE:
            raise i(result['result'])

    err = RESTError(result['result'])
    err.ERRCODE = result['error']
    raise err


def unscramble(value):
    if value is None or value == '':
        return value

    value = value.decode('hex')

    n = 0x32
    result = []
    for ch in value:
        c = ord(ch) ^ n
        n = (n + c) & 0xFF
        result.append(chr(c))

    return b''.join(result)[::-1].decode('utf8')


class Api(object):
    def __init__(self, host, masterKey, ssl, scrambledResponses=False):
        self.host = host
        self.masterKey = masterKey
        self.useSSL = ssl
        self.scrambledResponses = scrambledResponses
        self.uuid = None
        self.url = "{}://{}/rest/actor/".format(('http', 'https')[ssl], self.host)
        self.secretKey = uuid.uuid4().get_hex()
        # Disable logging requests messages except for warnings, errors, ...
        logging.getLogger("requests").setLevel(logging.WARNING)

    def _getUrl(self, method, key=None, ids=None, secretKey=None):
        url = self.url + method
        params = []
        if key is not None:
            params.append('key=' + key)
        if ids is not None:
            params.append('id=' + ids)
        if secretKey is not None:
            params.append('sk=' + secretKey)

        if len(params) > 0:
            url += '?' + '&'.join(params)

        print url

        return url

    def _request(self, url, data=None):
        try:
            if data is None:
                r = requests.get(url)
            else:
                r = requests.post(url, data)

            r = r.json()
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(e.message.args[-1].strerror)
        except Exception as e:
            raise ConnectionError(unicode(e))

        ensureResultIsOk(r)

        if self.scrambledResponses is True:
            # test && init are not scrambled, even if rest of messages are
            try:
                r['result'] = unscramble(r['result'])
            except Exception:
                pass

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
        '''
        url = self._getUrl('init', key=self.masterKey, ids=ids, secretKey=self.secretKey)
        self.uuid, self.mac = self._request(url)['result']
        return self.uuid

    def postMessage(self, msg, data, processData=True):
        if self.uuid is None:
            raise ConnectionError('REST api has not been initialized')

        if processData:
            data = json.dumps({'data': data})
        print data
        url = self._getUrl('/'.join([self.uuid, msg]))
        return self._request(url, data)['result']

    def notifyComm(self, url):
        return self.postMessage('notifyComms', url)

    def login(self, username):
        return self.postMessage('login', username)

    def logout(self, username):
        return self.postMessage('logout', username)

    def information(self):
        return self.postMessage('information', '')

    def setReady(self, ipsInfo):
        data = ','.join(['{}={}'.format(v[0], v[1]) for v in ipsInfo])
        return self.postMessage('ready', data)

    def notifyIpChanges(self, ipsInfo):
        data = ','.join(['{}={}'.format(v[0], v[1]) for v in ipsInfo])
        return self.postMessage('ip', data)

    def log(self, logLevel, message):
        data = json.dumps({'message': message, 'level': logLevel})
        return self.postMessage('log', data, processData=False)

