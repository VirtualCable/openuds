# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

# pylint: disable=maybe-no-member

import sys
import imp
import re

import logging
import six

import requests
import  json

__updated__ = '2017-02-09'

logger = logging.getLogger(__name__)


# Decorator
def ensureConnected(fnc):
    def inner(*args, **kwargs):
        args[0].connect()
        return fnc(*args, **kwargs)
    return inner

# Result checker
def ensureResponseIsValid(response, errMsg=None):
    if response.ok is False:
        if errMsg is None:
            errMsg = 'Invalid response'
        errMsg = '{}: {}, ({})'.format(errMsg, response.code, response.content)
        logger.error('{}: {}'.format(errMsg, response.content))
        raise Exception(errMsg)

    return json.loads(response.content)

class OpenGnsysClient(object):
    def __init__(self, username, password, endpoint, verifyCert=False):
        self.username = username
        self.password = password
        self.endpoint = endpoint
        self.auth = None
        self.verifyCert = verifyCert
        self.cachedVersion = None

    @property
    def headers(self):
        headers = {'content-type': 'application/json'}
        if self.auth is not None:
            headers['Authorization'] = self.auth

        return headers

    def _ogUrl(self, path):
        return self.endpoint + '/' + path

    def _post(self, path, data, errMsg=None):
        return ensureResponseIsValid(
            requests.post(self._ogUrl(path), data=json.dumps(data), headers=self.headers, verify=self.verifyCert),
            errMsg=errMsg
        )

    def _get(self, path, errMsg=None):
        return ensureResponseIsValid(
            requests.get(self._ogUrl(path), headers=self.headers, verify=self.verifyCert),
            errMsg=errMsg
        )

    def connect(self):
        if self.auth is not None:
            return

        auth = self._post('login', data={'username': self.username, 'password': self.password})

        self.auth = auth['Authorization']


    @property
    @ensureConnected
    def version(self):
        if self.cachedVersion is None:
            # Retrieve Version & keep it
            pass

