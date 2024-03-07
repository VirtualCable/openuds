# -*- coding: utf-8 -*-

#
# Copyright (c) 2016-2021 Virtual Cable S.L.U.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import json
import typing

# import dateutil.parser

from django.utils.translation import ugettext as _

from uds.core.util import security

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    import requests


logger = logging.getLogger(__name__)

# Required: Authentication v3

# This is an implementation for what we need from openstack
# This does not includes (nor it is intention) full API implementation, just the parts we need
# These are related to auth, compute & network basically

# Do not verify SSL conections right now
VERIFY_SSL = False


# Helpers
def ensureResponseIsValid(
    response: 'requests.Response', errMsg: typing.Optional[str] = None
) -> None:
    if response.ok is False:
        try:
            (
                _,
                err,
            ) = (
                response.json().popitem()
            )  # Extract any key, in case of error is expected to have only one top key so this will work
            msg = ': {message}'.format(**err)
            errMsg = errMsg + msg if errMsg else msg
        except Exception:
            pass  # If error geting error message, simply ignore it (will be loged on service log anyway)
        if errMsg is None:
            errMsg = 'Error checking response'
        logger.error('%s: %s', errMsg, response.content)
        raise Exception(errMsg)


def getRecurringUrlJson(
    url: str,
    session: 'requests.Session',
    headers: typing.Dict[str, str],
    key: str,
    params: typing.Optional[typing.Mapping[str, str]] = None,
    errMsg: typing.Optional[str] = None,
    timeout: int = 10,
) -> typing.Iterable[typing.Any]:
    counter = 0
    while True:
        counter += 1
        logger.debug('Requesting url #%s: %s / %s', counter, url, params)
        r = session.get(
            url, params=params, headers=headers, timeout=timeout
        )

        ensureResponseIsValid(r, errMsg)

        j = r.json()

        for v in j[key]:
            yield v

        if 'next' not in j:
            break

        url = j['next']


RT = typing.TypeVar('RT')

# Decorators
def authRequired(func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    def ensurer(obj: 'Client', *args, **kwargs) -> RT:
        obj.ensureAuthenticated()
        try:
            return func(obj, *args, **kwargs)
        except Exception as e:
            logger.error('Got error %s for openstack', e)
            raise

    return ensurer


def authProjectRequired(func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    def ensurer(obj, *args, **kwargs) -> RT:
        if obj._projectId is None:  # pylint: disable=protected-access
            raise Exception('Need a project for method {}'.format(func))
        obj.ensureAuthenticated()
        return func(obj, *args, **kwargs)

    return ensurer

class Client:  # pylint: disable=too-many-public-methods
    PUBLIC = 'public'
    PRIVATE = 'private'
    INTERNAL = 'url'

    _authenticated: bool
    _authenticatedProjectId: typing.Optional[str]
    _authUrl: str
    _tokenId: typing.Optional[str]
    _catalog: typing.Optional[typing.List[typing.Dict[str, typing.Any]]]
    _isLegacy: bool
    _volume: str
    _access: typing.Optional[str]
    _domain: str
    _username: str
    _password: str
    _userId: typing.Optional[str]
    _projectId: typing.Optional[str]
    _project: typing.Optional[str]
    _region: typing.Optional[str]
    _timeout: int
    _session: 'requests.Session'

    # Legacyversion is True for versions <= Ocata
    def __init__(
        self,
        host: str,
        port: typing.Union[str, int],
        domain: str,
        username: str,
        password: str,
        legacyVersion: bool = True,
        useSSL: bool = False,
        projectId: typing.Optional[str] = None,
        region: typing.Optional[str] = None,
        access: typing.Optional[str] = None,
        proxies: typing.Optional[typing.MutableMapping[str, str]] = None,
    ):
        self._session = security.secureRequestsSession(verify=VERIFY_SSL)
        if proxies:
            self._session.proxies = proxies

        self._authenticated = False
        self._authenticatedProjectId = None
        self._tokenId = None
        self._catalog = None
        self._isLegacy = legacyVersion

        self._access = Client.PUBLIC if access is None else access
        self._domain, self._username, self._password = domain, username, password
        self._userId = None
        self._projectId = projectId
        self._project = None
        self._region = region
        self._timeout = 10
        self._volume = ''

        if legacyVersion:
            self._authUrl = 'http{}://{}:{}/'.format('s' if useSSL else '', host, port)
        else:
            self._authUrl = host  # Host contains auth URL
            if self._authUrl[-1] != '/':
                self._authUrl += '/'


    def _getEndpointFor(
        self, *type_: str,
    ) -> str:  # If no region is indicatad, first endpoint is returned
        def inner_get(for_type: str) -> str:
            if not self._catalog:
                raise Exception('No catalog for endpoints')
            for i in filter(lambda v: v['type'] == for_type, self._catalog):
                for j in filter(lambda v: v['interface'] == self._access, i['endpoints']):
                    if not self._region or j['region'] == self._region:
                        if 'myhuaweicloud.eu/V1.0' not in j['url']:
                            return j['url']
            raise Exception('No endpoint url found')
        for t in type_:
            try:
                return inner_get(t)
            except Exception:
                pass
        raise Exception('No endpoint url found')

    def _requestHeaders(self) -> typing.Dict[str, str]:
        headers = {'content-type': 'application/json'}
        if self._tokenId:
            headers['X-Auth-Token'] = self._tokenId

        return headers

    def authPassword(self) -> None:
        # logger.debug('Authenticating...')
        data: typing.Dict[str, typing.Any] = {
            'auth': {
                'identity': {
                    'methods': ['password'],
                    'password': {
                        'user': {
                            'name': self._username,
                            'domain': {
                                'name': 'Default'
                                if self._domain is None
                                else self._domain
                            },
                            'password': self._password,
                        }
                    },
                }
            }
        }

        if self._projectId is None:
            self._authenticatedProjectId = None
            if self._isLegacy:
                data['auth']['scope'] = 'unscoped'
        else:
            self._authenticatedProjectId = self._projectId
            data['auth']['scope'] = {
                'project': {'id': self._projectId, 'domain': {'name': self._domain}}
            }

        # logger.debug('Request data: {}'.format(data))

        r = self._session.post(
            self._authUrl + 'v3/auth/tokens',
            data=json.dumps(data),
            headers={'content-type': 'application/json'},
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Invalid Credentials')

        self._authenticated = True
        self._tokenId = r.headers['X-Subject-Token']
        # Extract the token id
        token = r.json()['token']
        # logger.debug('Got token {}'.format(token))
        self._userId = token['user']['id']
        # validity = (dateutil.parser.parse(token['expires_at']).replace(tzinfo=None) - dateutil.parser.parse(token['issued_at']).replace(tzinfo=None)).seconds - 60

        # logger.debug('The token {} will be valid for {}'.format(self._tokenId, validity))

        # Now, if endpoints are present (only if tenant was specified), store them
        if self._projectId is not None:
            self._catalog = token['catalog']
            # Check for the presence of the endpoint for volumes
            # Volume v2 api was deprecated in Pike release, and removed on Xena release
            # Volume v3 api is available since Mitaka. Both are API compatible
            if self._catalog:
                if any(v['type'] == 'volumev3' for v in self._catalog):
                    self._volume = 'volumev3'
                else:
                    self._volume = 'volumev2'

    def ensureAuthenticated(self) -> None:
        if (
            self._authenticated is False
            or self._projectId != self._authenticatedProjectId
        ):
            self.authPassword()

    @authRequired
    def listProjects(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._authUrl + 'v3/users/{user_id}/projects'.format(user_id=self._userId),
            self._session,
            headers=self._requestHeaders(),
            key='projects',
            errMsg='List Projects',
            timeout=self._timeout,
        )

    @authRequired
    def listRegions(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._authUrl + 'v3/regions/',
            self._session,
            headers=self._requestHeaders(),
            key='regions',
            errMsg='List Regions',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listServers(
        self,
        detail: bool = False,
        params: typing.Optional[typing.Dict[str, str]] = None,
    ) -> typing.Iterable[typing.Any]:
        path = '/servers' + ('/detail' if detail is True else '')
        return getRecurringUrlJson(
            self._getEndpointFor('compute', 'compute_legacy') + path,
            self._session,
            headers=self._requestHeaders(),
            key='servers',
            params=params,
            errMsg='List Vms',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listImages(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._getEndpointFor('image') + '/v2/images?status=active',
            self._session,
            headers=self._requestHeaders(),
            key='images',
            errMsg='List Images',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listVolumeTypes(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._getEndpointFor(self._volume) + '/types',
            self._session,
            headers=self._requestHeaders(),
            key='volume_types',
            errMsg='List Volume Types',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listVolumes(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._getEndpointFor(self._volume) + '/volumes/detail',
            self._session,
            headers=self._requestHeaders(),
            key='volumes',
            errMsg='List Volumes',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listVolumeSnapshots(
        self, volumeId: typing.Optional[typing.Dict[str, typing.Any]] = None
    ) -> typing.Iterable[typing.Any]:
        for s in getRecurringUrlJson(
            self._getEndpointFor(self._volume) + '/snapshots',
            self._session,
            headers=self._requestHeaders(),
            key='snapshots',
            errMsg='List snapshots',
            timeout=self._timeout,
        ):
            if volumeId is None or s['volume_id'] == volumeId:
                yield s

    @authProjectRequired
    def listAvailabilityZones(self) -> typing.Iterable[typing.Any]:
        for az in getRecurringUrlJson(
            self._getEndpointFor('compute', 'compute_legacy') + '/os-availability-zone',
            self._session,
            headers=self._requestHeaders(),
            key='availabilityZoneInfo',
            errMsg='List Availability Zones',
            timeout=self._timeout,
        ):
            if az['zoneState']['available'] is True:
                yield az['zoneName']

    @authProjectRequired
    def listFlavors(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._getEndpointFor('compute', 'compute_legacy') + '/flavors',
            self._session,
            headers=self._requestHeaders(),
            key='flavors',
            errMsg='List Flavors',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listNetworks(self, nameFromSubnets=False) -> typing.Iterable[typing.Any]:
        nets = getRecurringUrlJson(
            self._getEndpointFor('network') + '/v2.0/networks',
            self._session,
            headers=self._requestHeaders(),
            key='networks',
            errMsg='List Networks',
            timeout=self._timeout,
        )
        if not nameFromSubnets:
            yield from nets
        else:
            # Get and cache subnets names
            subnetNames = {s['id']: s['name'] for s in self.listSubnets()}
            for net in nets:
                name = ','.join(
                    subnetNames[i] for i in net['subnets'] if i in subnetNames
                )
                net['old_name'] = net['name']
                if name:
                    net['name'] = name

                yield net

    @authProjectRequired
    def listSubnets(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._getEndpointFor('network') + '/v2.0/subnets',
            self._session,
            headers=self._requestHeaders(),
            key='subnets',
            errMsg='List Subnets',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listPorts(
        self,
        networkId: typing.Optional[str] = None,
        ownerId: typing.Optional[str] = None,
    ) -> typing.Iterable[typing.Any]:
        params = {}
        if networkId is not None:
            params['network_id'] = networkId
        if ownerId is not None:
            params['device_owner'] = ownerId

        return getRecurringUrlJson(
            self._getEndpointFor('network') + '/v2.0/ports',
            self._session,
            headers=self._requestHeaders(),
            key='ports',
            params=params,
            errMsg='List ports',
            timeout=self._timeout,
        )

    @authProjectRequired
    def listSecurityGroups(self) -> typing.Iterable[typing.Any]:
        return getRecurringUrlJson(
            self._getEndpointFor('compute', 'compute_legacy') + '/os-security-groups',
            self._session,
            headers=self._requestHeaders(),
            key='security_groups',
            errMsg='List security groups',
            timeout=self._timeout,
        )

    @authProjectRequired
    def getServer(self, serverId: str) -> typing.Dict[str, typing.Any]:
        r = self._session.get(
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}'.format(server_id=serverId),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )
        ensureResponseIsValid(r, 'Get Server information')
        return r.json()['server']

    @authProjectRequired
    def getVolume(self, volumeId: str) -> typing.Dict[str, typing.Any]:
        r = self._session.get(
            self._getEndpointFor(self._volume)
            + '/volumes/{volume_id}'.format(volume_id=volumeId),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Get Volume information')

        return r.json()['volume']

    @authProjectRequired
    def getSnapshot(self, snapshotId: str) -> typing.Dict[str, typing.Any]:
        """
        States are:
            creating, available, deleting, error,  error_deleting
        """
        r = self._session.get(
            self._getEndpointFor(self._volume)
            + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Get Snaphost information')

        return r.json()['snapshot']

    @authProjectRequired
    def updateSnapshot(
        self,
        snapshotId: str,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> typing.Dict[str, typing.Any]:
        data: typing.Dict[str, typing.Any] = {'snapshot': {}}
        if name:
            data['snapshot']['name'] = name

        if description:
            data['snapshot']['description'] = description

        r = self._session.put(
            self._getEndpointFor(self._volume)
            + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
            data=json.dumps(data),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Update Snaphost information')

        return r.json()['snapshot']

    @authProjectRequired
    def createVolumeSnapshot(
        self, volumeId: str, name: str, description: typing.Optional[str] = None
    ) -> typing.Dict[str, typing.Any]:
        description = description or 'UDS Snapshot'
        data = {
            'snapshot': {
                'name': name,
                'description': description,
                'volume_id': volumeId,
                'force': True,
            }
        }

        # First, ensure volume is in state "available"

        r = self._session.post(
            self._getEndpointFor(self._volume) + '/snapshots',
            data=json.dumps(data),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(
            r, 'Cannot create snapshot. Ensure volume is in state "available"'
        )

        return r.json()['snapshot']

    @authProjectRequired
    def createVolumeFromSnapshot(
        self, snapshotId: str, name: str, description: typing.Optional[str] = None
    ) -> typing.Dict[str, typing.Any]:
        description = description or 'UDS Volume'
        data = {
            'volume': {
                'name': name,
                'description': description,
                # 'volume_type': volType,  # This seems to be the volume type name, not the id
                'snapshot_id': snapshotId,
            }
        }

        r = self._session.post(
            self._getEndpointFor(self._volume) + '/volumes',
            data=json.dumps(data),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Cannot create volume from snapshot.')

        return r.json()['volume']

    @authProjectRequired
    def createServerFromSnapshot(
        self,
        snapshotId: str,
        name: str,
        availabilityZone: str,
        flavorId: str,
        networkId: str,
        securityGroupsIdsList: typing.Iterable[str],
        count: int = 1,
    ) -> typing.Dict[str, typing.Any]:
        data = {
            'server': {
                'name': name,
                'imageRef': '',
                'metadata': {'udsOwner': 'xxxxx'},
                # 'os-availability-zone': availabilityZone,
                'availability_zone': availabilityZone,
                'block_device_mapping_v2': [
                    {
                        'boot_index': '0',
                        'uuid': snapshotId,
                        # 'volume_size': 1,
                        # 'device_name': 'vda',
                        'source_type': 'snapshot',
                        'destination_type': 'volume',
                        'delete_on_termination': True,
                    }
                ],
                'flavorRef': flavorId,
                # 'OS-DCF:diskConfig': 'AUTO',
                'max_count': count,
                'min_count': count,
                'networks': [{'uuid': networkId}],
                'security_groups': [{'name': sg} for sg in securityGroupsIdsList],
            }
        }

        r = self._session.post(
            self._getEndpointFor('compute', 'compute_legacy') + '/servers',
            data=json.dumps(data),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Cannot create instance from snapshot.')

        return r.json()['server']

    @authProjectRequired
    def deleteServer(self, serverId: str) -> None:
        # r = self._session.post(
        #     self._getEndpointFor('compute', , 'compute_legacy') + '/servers/{server_id}/action'.format(server_id=serverId),
        #     data='{"forceDelete": null}',
        #     headers=self._requestHeaders(),
        #     timeout=self._timeout
        # )
        r = self._session.delete(
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}'.format(server_id=serverId),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(
            r, 'Cannot delete server (probably server does not exists).'
        )

        # This does not returns anything

    @authProjectRequired
    def deleteSnapshot(self, snapshotId: str) -> None:
        r = self._session.delete(
            self._getEndpointFor(self._volume)
            + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Cannot remove snapshot.')

        # Does not returns a message body

    @authProjectRequired
    def startServer(self, serverId: str) -> None:
        r = self._session.post(
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}/action'.format(server_id=serverId),
            data='{"os-start": null}',
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Starting server')

        # This does not returns anything

    @authProjectRequired
    def stopServer(self, serverId: str) -> None:
        r = self._session.post(
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}/action'.format(server_id=serverId),
            data='{"os-stop": null}',
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Stoping server')

    @authProjectRequired
    def suspendServer(self, serverId: str) -> None:
        r = self._session.post(
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}/action'.format(server_id=serverId),
            data='{"suspend": null}',
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Suspending server')

    @authProjectRequired
    def resumeServer(self, serverId: str) -> None:
        r = self._session.post(
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}/action'.format(server_id=serverId),
            data='{"resume": null}',
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        ensureResponseIsValid(r, 'Resuming server')

    @authProjectRequired
    def resetServer(self, serverId: str) -> None:
        r = self._session.post(  # pylint: disable=unused-variable
            self._getEndpointFor('compute', 'compute_legacy')
            + '/servers/{server_id}/action'.format(server_id=serverId),
            data='{"reboot":{"type":"HARD"}}',
            headers=self._requestHeaders(),
            timeout=self._timeout,
        )

        # Ignore response for this...
        # ensureResponseIsValid(r, 'Reseting server')

    def testConnection(self) -> bool:
        # First, ensure requested api is supported
        # We need api version 3.2 or greater
        try:
            r = self._session.get(
                self._authUrl, headers=self._requestHeaders()
            )
        except Exception:
            logger.exception('Testing')
            raise Exception('Connection error')

        try:
            for v in r.json()['versions']['values']:
                if v['id'] >= 'v3.1':
                    # Tries to authenticate
                    try:
                        self.authPassword()
                        # Log some useful information
                        logger.info('Openstack version: %s', v['id'])
                        logger.info('Endpoints: %s', json.dumps(self._catalog, indent=4))
                        return True
                    except Exception:
                        logger.exception('Authenticating')
                        raise Exception(_('Authentication error'))
        except Exception:  # Not json
            # logger.exception('xx')
            raise Exception('Invalid endpoint (maybe invalid version selected?)')

        raise Exception(
            _(
                'Openstack does not support identity API 3.2 or newer. This OpenStack server is not compatible with UDS.'
            )
        )
