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
from uds.core.util.Cache import Cache

import logging
import requests
import json
import six
import hashlib
import dateutil.parser


# Python bindings for OpenNebula
from .common import sanitizeName

__updated__ = '2016-03-03'

logger = logging.getLogger(__name__)

# This is a vary basic implementation for what we need from openstack
# This does not includes (nor it is intention) full API implementation, just the parts we need
# Theese are related to auth, compute & network basically

# In case we Cache time for endpoints. This is more likely to not change never, so we will tray to keep it as long as we can (1 hour for example?)
# ENDPOINTS_TIMEOUT = 1 * 3600

# Helpers
def ensureResponseIsValid(response, errMsg=None):
    if response.reason != 'OK':
        if errMsg is None:
            errMsg = 'Error checking response'
        logger.error('{}: {}'.format(errMsg, response.content))
        raise Exception(errMsg)


class UDSOpenStackClient(object):
    cache = Cache('uds-openstack')

    PUBLIC = 'public'
    PRIVATE = 'private'
    INTERNAL = 'url'

    def __init__(self, host, port, username, password, useSSL=False, tenant=None, access=None):
        self._authenticated = False
        self._tokenId = None
        self._serviceCatalog = None

        self._access = UDSOpenStackClient.PUBLIC if access is None else access
        self._host, self._port = host, int(port)
        self._username, self._password = username, password
        self._tenant = tenant
        self._tenantId = None
        self._timeout = 10

        self._authUrl = 'http{}://{}:{}/'.format('s' if useSSL else '', host, port)

        # Generates a hash for auth + credentials
        # h = hashlib.md5()
        # h.update(six.binary_type(username))
        # h.update(six.binary_type(password))
        # h.update(six.binary_type(host))
        # h.update(six.binary_type(port))
        # h.update(six.binary_type(tenant))

        # self._cacheKey = h.hexdigest()

    def _getEndpointFor(self, type_, region=None):  # If no region is indicatad, first endpoint is returned
        for i in self._serviceCatalog:
            if i['type'] == type_:
                for j in i['endpoints']:
                    if region is None or j['region'] == region:
                        return j[self._access + 'URL']

    def _requestHeaders(self):
        headers = {'content-type': 'application/json'}
        if self._tokenId is not None:
            headers['X-Auth-Token'] = self._tokenId

        return headers


    def authPassword(self):
        data = {
            'auth': {
                'passwordCredentials': {
                    'username': self._username,
                    'password': self._password

                }
            }
        }

        if self._tenant is not None:
            data['auth']['tenantName'] = self._tenant

        r = requests.post(self._authUrl + 'v2.0/tokens',
                      data=json.dumps(data),
                      headers={'content-type': 'application/json'},
                      verify=False,
                      timeout=self._timeout)

        ensureResponseIsValid(r, 'Invalid Credentials')

        self._authtenticated = True
        # Extract the token id
        r = json.loads(r.content)
        token = r['access']['token']
        self._tokenId = token['id']
        validity = (dateutil.parser.parse(token['expires']).replace(tzinfo=None) - dateutil.parser.parse(token['issued_at']).replace(tzinfo=None)).seconds - 60

        logger.debug('The token {} will be valid for {}'.format(self._tokenId, validity))

        # Now, if endpoints are present (only if tenant was specified), store & cache them
        if self._tenant is not None:
            self._serviceCatalog = r['access']['serviceCatalog']

            print self._serviceCatalog


    def ensureAuthenticated(self):
        if self._authenticated is False:
            self.authPassword()

    def listTenants(self):
        self.ensureAuthenticated()
        r = requests.get(self._authUrl + 'v2.0/tenants/',
                         headers=self._requestHeaders())

        ensureResponseIsValid(r, 'List Tenants')

        return json.loads(r.content)['tenants']

    def listRegions(self):
        self.ensureAuthenticated()
        r = requests.get(self._authUrl + 'v3/regions/',
                         headers=self._requestHeaders())

        ensureResponseIsValid(r, 'List Regions')

        return json.loads(r.content)['regions']
