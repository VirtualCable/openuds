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
from django.utils.translation import ugettext as _

from uds.core.util.Cache import Cache

import logging
import requests
import json
import dateutil.parser


__updated__ = '2016-03-07'

logger = logging.getLogger(__name__)

# Required: Authentication v3


# This is a vary basic implementation for what we need from openstack
# This does not includes (nor it is intention) full API implementation, just the parts we need
# Theese are related to auth, compute & network basically

# In case we Cache time for endpoints. This is more likely to not change never, so we will tray to keep it as long as we can (1 hour for example?)
# ENDPOINTS_TIMEOUT = 1 * 3600

# Do not verify SSL conections right now
VERIFY_SSL = False

# Helpers
def ensureResponseIsValid(response, errMsg=None):
    if response.ok is False:
        print "False"
        try:
            _x, err = response.json().popitem()  # Extract any key, in case of error is expected to have only one top key so this will work
            errMsg = errMsg + ': {message}'.format(**err)
        except Exception:
            pass  # If error geting error message, simply ignore it (will be loged on service log anyway)
        if errMsg is None:
            errMsg = 'Error checking response'
        logger.error('{}: {}'.format(errMsg, response.content))
        raise Exception(errMsg)


def getRecurringUrlJson(url, headers, key, params=None, errMsg=None, timeout=10):
    counter = 0
    while True:
        counter += 1
        logger.debug('Requesting url #{}: {} / {}'.format(counter, url, params))
        r = requests.get(url, params=params, headers=headers, verify=VERIFY_SSL, timeout=timeout)

        ensureResponseIsValid(r, errMsg)

        j = r.json()

        for v in j[key]:
            yield v

        if 'next' not in j:
            break

        url = j['next']


# Decorators
def authRequired(func):
    def ensurer(obj, *args, **kwargs):
        obj.ensureAuthenticated()
        return func(obj, *args, **kwargs)
    return ensurer

def authProjectRequired(func):
    def ensurer(obj, *args, **kwargs):
        if obj._projectId is None:
            raise Exception('Need a project for method {}'.format(func))
        obj.ensureAuthenticated()
        return func(obj, *args, **kwargs)
    return ensurer


class Client(object):
    cache = Cache('uds-openstack')

    PUBLIC = 'public'
    PRIVATE = 'private'
    INTERNAL = 'url'

    def __init__(self, host, port, domain, username, password, useSSL=False, projectId=None, region=None, access=None):
        self._authenticated = False
        self._tokenId = None
        self._catalog = None

        self._access = Client.PUBLIC if access is None else access
        self._host, self._port = host, int(port)
        self._domain, self._username, self._password = domain, username, password
        self._userId = None
        self._projectId = projectId
        self._project = None
        self._region = region
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

    def _getEndpointFor(self, type_):  # If no region is indicatad, first endpoint is returned
        for i in self._catalog:
            if i['type'] == type_:
                for j in i['endpoints']:
                    if j['interface'] == self._access and (self._region is None or j['region'] == self._region):
                        return j['url']

    def _requestHeaders(self):
        headers = {'content-type': 'application/json'}
        if self._tokenId is not None:
            headers['X-Auth-Token'] = self._tokenId

        return headers

    def authPassword(self):
        data = {
            'auth': {
                'identity': {
                    'methods': [
                        'password'
                    ],
                    'password': {
                        'user': {
                            'name': self._username,
                            'domain': {
                                'name': 'Default' if self._domain is None else self._domain
                            },
                            'password': self._password
                        }
                    }
                }
            }
        }

        if self._projectId is None:
            data['auth']['scope'] = 'unscoped'
        else:
            data['auth']['scope'] = {
                'project': {
                    'id': self._projectId
                }
            }

        r = requests.post(self._authUrl + 'v3/auth/tokens',
                          data=json.dumps(data),
                          headers={'content-type': 'application/json'},
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Invalid Credentials')

        self._authenticated = True
        self._tokenId = r.headers['X-Subject-Token']
        # Extract the token id
        token = r.json()['token']
        self._userId = token['user']['id']
        validity = (dateutil.parser.parse(token['expires_at']).replace(tzinfo=None) - dateutil.parser.parse(token['issued_at']).replace(tzinfo=None)).seconds - 60


        logger.debug('The token {} will be valid for {}'.format(self._tokenId, validity))

        # Now, if endpoints are present (only if tenant was specified), store & cache them
        if self._projectId is not None:
            self._catalog = token['catalog']


    def ensureAuthenticated(self):
        if self._authenticated is False:
            self.authPassword()


    @authRequired
    def listProjects(self):
        return getRecurringUrlJson(self._authUrl + 'v3/users/{user_id}/projects'.format(user_id=self._userId),
                                     headers=self._requestHeaders(),
                                     key='projects',
                                     errMsg='List Projects',
                                     timeout=self._timeout)


    @authRequired
    def listRegions(self):
        return getRecurringUrlJson(self._authUrl + 'v3/regions/',
                                     headers=self._requestHeaders(),
                                     key='regions',
                                     errMsg='List Regions',
                                     timeout=self._timeout)


    @authProjectRequired
    def listServers(self, detail=False, params=None):
        path = '/servers/' + 'detail' if detail is True else ''
        return getRecurringUrlJson(self._getEndpointFor('compute') + path,
                                    headers=self._requestHeaders(),
                                    key='servers',
                                    params=params,
                                    errMsg='List Vms',
                                    timeout=self._timeout)


    @authProjectRequired
    def listImages(self):
        return getRecurringUrlJson(self._getEndpointFor('image') + '/v2/images?status=active',
                                     headers=self._requestHeaders(),
                                     key='images',
                                     errMsg='List Images',
                                     timeout=self._timeout)


    @authProjectRequired
    def listVolumeTypes(self):
        return getRecurringUrlJson(self._getEndpointFor('volumev2') + '/types',
                                     headers=self._requestHeaders(),
                                     key='volume_types',
                                     errMsg='List Volume Types',
                                     timeout=self._timeout)


    @authProjectRequired
    def listVolumes(self):
        # self._getEndpointFor('volumev2') + '/volumes'
        return getRecurringUrlJson(self._getEndpointFor('volumev2') + '/volumes/detail',
                                     headers=self._requestHeaders(),
                                     key='volumes',
                                     errMsg='List Volumes',
                                     timeout=self._timeout)


    @authProjectRequired
    def listVolumeSnapshots(self, volumeId=None):
        for s in getRecurringUrlJson(self._getEndpointFor('volumev2') + '/snapshots',
                                     headers=self._requestHeaders(),
                                     key='snapshots',
                                     errMsg='List snapshots',
                                     timeout=self._timeout):
            if volumeId is None or s['volume_id'] == volumeId:
                yield s


    @authProjectRequired
    def listAvailabilityZones(self):
        for az in getRecurringUrlJson(self._getEndpointFor('compute') + '/os-availability-zone',
                                     headers=self._requestHeaders(),
                                     key='availabilityZoneInfo',
                                     errMsg='List Availability Zones',
                                     timeout=self._timeout):
            if az['zoneState']['available'] is True:
                yield az['zoneName']


    @authProjectRequired
    def listFlavors(self):
        return getRecurringUrlJson(self._getEndpointFor('compute') + '/flavors',
                                     headers=self._requestHeaders(),
                                     key='flavors',
                                     errMsg='List Flavors',
                                     timeout=self._timeout)


    @authProjectRequired
    def listNetworks(self):
        return getRecurringUrlJson(self._getEndpointFor('network') + '/v2.0/networks',
                                     headers=self._requestHeaders(),
                                     key='networks',
                                     errMsg='List Networks',
                                     timeout=self._timeout)

    @authProjectRequired
    def listPorts(self, networkId=None, ownerId=None):
        params = {}
        if networkId is not None:
            params['network_id'] = networkId
        if ownerId is not None:
            params['device_owner'] = ownerId

        return getRecurringUrlJson(self._getEndpointFor('network') + '/v2.0/ports',
                                   headers=self._requestHeaders(),
                                   key='ports',
                                   params=params,
                                   errMsg='List ports',
                                     timeout=self._timeout)

    @authProjectRequired
    def listSecurityGroups(self):
        return getRecurringUrlJson(self._getEndpointFor('compute') + '/os-security-groups',
                                     headers=self._requestHeaders(),
                                     key='security_groups',
                                     errMsg='List security groups',
                                     timeout=self._timeout)


    @authProjectRequired
    def getServer(self, serverId):
        r = requests.get(self._getEndpointFor('compute') + '/servers/{server_id}'.format(server_id=serverId),
                                    headers=self._requestHeaders(),
                                    verify=VERIFY_SSL,
                                    timeout=self._timeout)

        ensureResponseIsValid(r, 'Get Server information')
        return r.json()['server']

    @authProjectRequired
    def getVolume(self, volumeId):
        r = requests.get(self._getEndpointFor('volumev2') + '/volumes/{volume_id}'.format(volume_id=volumeId),
                         headers=self._requestHeaders(),
                         verify=VERIFY_SSL,
                         timeout=self._timeout)

        ensureResponseIsValid(r, 'Get Volume information')

        v = r.json()['volume']

        return v


    @authProjectRequired
    def getSnapshot(self, snapshotId):
        '''
        States are:
            creating, available, deleting, error,  error_deleting
        '''
        r = requests.get(self._getEndpointFor('volumev2') + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
                         headers=self._requestHeaders(),
                         verify=VERIFY_SSL,
                         timeout=self._timeout)

        ensureResponseIsValid(r, 'Get Snaphost information')

        v = r.json()['snapshot']

        return v


    @authProjectRequired
    def updateSnapshot(self, snapshotId, name=None, description=None):
        data = { 'snapshot': {} }
        if name is not None:
            data['snapshot']['name'] = name

        if description is not None:
            data['snapshot']['description'] = description

        r = requests.put(self._getEndpointFor('volumev2') + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
                         data=json.dumps(data),
                         headers=self._requestHeaders(),
                         verify=VERIFY_SSL,
                         timeout=self._timeout)

        ensureResponseIsValid(r, 'Update Snaphost information')

        v = r.json()['snapshot']

        return v


    @authProjectRequired
    def createVolumeSnapshot(self, volumeId, name, description=None):
        description = 'UDS Snapshot' if description is None else description
        data = {
            'snapshot': {
                'name': name,
                'description': description,
                'volume_id': volumeId,
                'force': True
            }
        }

        # First, ensure volume is in state "available"

        r = requests.post(self._getEndpointFor('volumev2') + '/snapshots',
                          data=json.dumps(data),
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Cannot create snapshot. Ensure volume is in state "available"')

        return r.json()['snapshot']


    @authProjectRequired
    def createVolumeFromSnapshot(self, snapshotId, name, description=None):
        description = 'UDS Volume' if description is None else description
        data = {
                'volume': {
                        'name': name,
                        'description': description,
                        # 'volume_type': volType,  # This seems to be the volume type name, not the id
                        'snapshot_id': snapshotId
                }
        }

        r = requests.post(self._getEndpointFor('volumev2') + '/volumes',
                          data=json.dumps(data),
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Cannot create volume from snapshot.')

        return r.json()

    @authProjectRequired
    def createServerFromSnapshot(self, snapshotId, name, availabilityZone, flavorId, networkId, securityGroupsIdsList, count=1):
        data = {
            'server': {
                'name': name,
                'imageRef': '',
                'os-availability-zone': availabilityZone,
                'availability_zone': availabilityZone,
                'block_device_mapping_v2': [{
                    'boot_index': '0',
                    'uuid': snapshotId,
                    # 'volume_size': 1,
                    # 'device_name': 'vda',
                    'source_type': 'snapshot',
                    'destination_type': 'volume',
                    'delete_on_termination': True
                }],
                'flavorRef': flavorId,
                # 'OS-DCF:diskConfig': 'AUTO',
                'max_count': count,
                'min_count': count,
                'networks': [ { 'uuid': networkId } ],
                'security_groups': [{'name': sg} for sg in securityGroupsIdsList]
            }
        }

        r = requests.post(self._getEndpointFor('compute') + '/servers',
                          data=json.dumps(data),
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Cannot create instance from snapshot.')

        return r.json()['server']


    @authProjectRequired
    def deleteServer(self, serverId):
        r = requests.post(self._getEndpointFor('compute') + '/servers/{server_id}/action'.format(server_id=serverId),
                          data='{"forceDelete": null}',
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Cannot start server (probably server does not exists).')

        # This does not returns anything


    @authProjectRequired
    def deleteSnapshot(self, snapshotId):
        r = requests.delete(self._getEndpointFor('volumev2') + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Cannot remove snapshot.')

        # Does not returns a message body


    @authProjectRequired
    def startServer(self, serverId):
        r = requests.post(self._getEndpointFor('compute') + '/servers/{server_id}/action'.format(server_id=serverId),
                          data='{"os-start": null}',
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Starting server')

        # This does not returns anything


    @authProjectRequired
    def stopServer(self, serverId):
        r = requests.post(self._getEndpointFor('compute') + '/servers/{server_id}/action'.format(server_id=serverId),
                          data='{"os-stop": null}',
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Stoping server')

    @authProjectRequired
    def suspendServer(self, serverId):
        r = requests.post(self._getEndpointFor('compute') + '/servers/{server_id}/action'.format(server_id=serverId),
                          data='{"suspend": null}',
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Suspending server')

    @authProjectRequired
    def resumeServer(self, serverId):
        r = requests.post(self._getEndpointFor('compute') + '/servers/{server_id}/action'.format(server_id=serverId),
                          data='{"resume": null}',
                          headers=self._requestHeaders(),
                          verify=VERIFY_SSL,
                          timeout=self._timeout)

        ensureResponseIsValid(r, 'Resuming server')


    def testConnection(self):
        # First, ensure requested api is supported
        # We need api version 3.2 or greater
        try:
            r = requests.get(self._authUrl,
                             headers=self._requestHeaders())
        except Exception:
            raise Exception('Connection error')

        for v in r.json()['versions']['values']:
            if v['id'] >= 'v3.2':
                # Tries to authenticate
                try:
                    self.authPassword()
                    return True
                except Exception:
                    raise Exception(_('Authentication error'))

        raise Exception(_('Openstack does not support identity API 3.2 or newer. This OpenStack server is not compatible with UDS.'))
