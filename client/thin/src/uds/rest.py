# -*- coding: utf-8 -*-

#
# Copyright (c) 2015 Virtual Cable S.L.
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
from __future__ import unicode_literals

import requests
from . import VERSION

import json
import six
import osDetector

from .log import logger


class RetryException(Exception):
    pass


class RestRequest(object):

    restApiUrl = ''

    def __init__(self, host, ssl=True):  # parent not used
        super(RestRequest, self).__init__()

        self.host = host
        self.ssl = ssl
        self.restApiUrl = '{}://{}/rest/client'.format(['http', 'https'][ssl], host)

    def get(self, url, params=None):
        url = self.restApiUrl + url
        if params is not None:
            url += '?' + '&'.join('{}={}'.format(k, six.moves.urllib.parse.quote(six.text_type(v).encode('utf8'))) for k, v in params.iteritems())  # @UndefinedVariable

        logger.debug('Requesting {}'.format(url))

        try:
            r = requests.get(url, headers={'Content-type': 'application/json', 'User-Agent': osDetector.getOs() + " - UDS Connector " + VERSION }, verify=False)
        except requests.exceptions.ConnectionError as e:
            raise Exception('Error connecting to UDS Server at {}'.format(self.restApiUrl[0:-11]))

        if r.ok:
            logger.debug('Request was OK. {}'.format(r.text))
            data = json.loads(r.text)
            if not 'error' in data:
                return data['result']
            # Has error
            if data.get('retryable', '0') == '1':
                raise RetryException(data['error'])

            raise Exception(data['error'])
        else:
            logger.error('Error requesting {}: {}, {}'.format(url, r.code. r.text))
            raise Exception('Error {}: {}'.format(r.code, r.text))

        return data
