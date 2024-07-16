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
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PAdecorators.FTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TOdecorators.FT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import functools
import logging
import json
import typing
import collections.abc

from django.utils.translation import gettext as _
from uds.core import consts

from uds.core.services.generics import exceptions
from uds.core.util import security, cache, decorators

from . import types as openstack_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    import requests

logger = logging.getLogger(__name__)

# Required: Authentication v3

# This is an implementation for what we need from openstack
# This does not includes (nor it is intention) full API implementation, just the parts we need
# These are related to auth, compute & network basically

# Do not verify SSL conections right now
VOLUMES_ENDPOINT_TYPES = [
    'volumev3',
    'volumev2',
]  #  'volume' is also valid, but it is deprecated A LONG TYPE AGO
COMPUTE_ENDPOINT_TYPES = ['compute', 'compute_legacy']
NETWORKS_ENDPOINT_TYPES = ['network']

T = typing.TypeVar('T')
P = typing.ParamSpec('P')


# Decorators
def auth_required(
    for_project: bool = False,
) -> collections.abc.Callable[[collections.abc.Callable[P, T]], collections.abc.Callable[P, T]]:

    def decorator(func: collections.abc.Callable[P, T]) -> collections.abc.Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> typing.Any:
            obj = typing.cast('OpenStackClient', args[0])
            if for_project is True:
                if obj._projectid is None:
                    raise Exception('Need a project for method {}'.format(func))
            obj.ensure_authenticated()
            return func(*args, **kwargs)

        return wrapper

    return decorator


def cache_key_helper(obj: 'OpenStackClient') -> str:
    return '_'.join(
        [
            obj._identity_endpoint,
            obj._domain,
            obj._username,
            obj._password,
            str(obj._projectid),
            str(obj._region),
            str(obj._access),
        ]
    )


class OpenStackClient:  # pylint: disable=too-many-public-methods
    _authenticated: bool
    _authenticated_projectid: typing.Optional[str]
    _identity_endpoint: str
    _tokenid: typing.Optional[str]
    _catalog: typing.Optional[list[dict[str, typing.Any]]]
    _is_legacy: bool
    _access: typing.Optional[str]
    _domain: str
    _username: str
    _password: str
    _auth_method: openstack_types.AuthMethod
    _userid: typing.Optional[str]
    _projectid: typing.Optional[str]
    _region: typing.Optional[str]
    _timeout: int
    _session: 'requests.Session'

    # Cache for data
    cache: 'cache.Cache'

    # Legacyversion is True for versions <= Ocata
    def __init__(
        self,
        identity_endpoint: str,
        domain: str,
        username: str,
        password: str,
        port: int = -1,  # Only used for legacy
        use_ssl: bool = False,  # Only used for legacy
        projectid: typing.Optional[str] = None,
        region: typing.Optional[str] = None,
        access: typing.Optional[openstack_types.AccessType] = None,
        proxies: typing.Optional[dict[str, str]] = None,
        timeout: int = 10,
        verify_ssl: bool = True,
        auth_method: openstack_types.AuthMethod = openstack_types.AuthMethod.PASSWORD,
    ):
        self._session = security.secure_requests_session(verify=verify_ssl)
        if proxies:
            self._session.proxies = proxies

        self._authenticated = False
        self._authenticated_projectid = None
        self._tokenid = None
        self._catalog = None
        self._is_legacy = port != -1  # If port is present, we are using legacy

        self._access = openstack_types.AccessType.PUBLIC if access is None else access
        self._domain, self._username, self._password = domain or 'Default', username, password
        self._userid = None
        self._projectid = projectid
        self._region = region
        self._timeout = timeout
        self._auth_method = auth_method

        if self._is_legacy:
            self._identity_endpoint = 'http{}://{}:{}/'.format('s' if use_ssl else '', identity_endpoint, port)
        else:
            self._identity_endpoint = identity_endpoint  # Host contains auth URL
            if self._identity_endpoint[-1] != '/':
                self._identity_endpoint += '/'

        self.cache = cache.Cache(f'openstack_{identity_endpoint}_{port}_{domain}_{username}_{projectid}_{region}')

    def _get_endpoints_for(self, *endpoint_types: str) -> collections.abc.Generator[str, None, None]:
        def inner_get(for_type: str) -> collections.abc.Generator[str, None, None]:
            if not self._catalog:
                raise Exception('No catalog for endpoints')

            # Filter by type and interface
            for i in typing.cast(
                list[dict[str, typing.Any]], filter(lambda v: v['type'] == for_type, self._catalog)
            ):
                # Filter for interface accessiblity (public, ...)
                for j in typing.cast(
                    list[dict[str, typing.Any]],
                    filter(
                        lambda v: v['interface'] == self._access,
                        typing.cast(list[dict[str, typing.Any]], i['endpoints']),
                    ),
                ):
                    # Filter for region if present
                    if not self._region or j['region'] == self._region:
                        # if 'myhuaweicloud.eu/V1.0' not in j['url']:
                        yield j['url']

        for t in endpoint_types:
            try:
                yield from inner_get(t)
            except Exception:
                pass

    def _get_endpoint_for(
        self, *endpoint_type: str
    ) -> str:  # If no region is indicatad, first endpoint is returned
        try:
            return next(self._get_endpoints_for(*endpoint_type))
        except StopIteration:
            raise Exception('No endpoint url found')

    def _get_request_headers(self) -> dict[str, str]:
        headers = {'content-type': 'application/json'}
        if self._tokenid:
            headers['X-Auth-Token'] = self._tokenid

        return headers

    def _get_compute_endpoint(self) -> str:
        return self._get_endpoint_for('compute', 'compute_legacy')

    def _get_endpoints_iterable(self, cache_key: str, *types: str) -> list[str]:
        # If endpoint is cached, use it as first endpoint
        found_endpoints = list(self._get_endpoints_for(*types))
        if self.cache.get(cache_key) in found_endpoints:
            # If cached endpoint is in the list, use it as first endpoint
            found_endpoints = [self.cache.get(cache_key)] + list(
                set(found_endpoints) - {self.cache.get(cache_key)}
            )

        logger.debug('Endpoints for %s: %s', types, found_endpoints)

        return found_endpoints

    @auth_required(for_project=True)
    def _request_from_endpoint(
        self,
        type: typing.Literal['get', 'put', 'post', 'delete'],
        endpoints_types: list[str],
        path: str,
        error_message: str,
        data: typing.Any = None,
        expects_json: bool = True,
    ) -> typing.Any:
        cache_key = ''.join(endpoints_types)
        found_endpoints = self._get_endpoints_iterable(cache_key, *endpoints_types)

        for i, endpoint in enumerate(found_endpoints):
            try:
                logger.debug(
                    'Requesting from endpoint: %s and path %s using %s: %s', endpoint, path, type, data
                )
                r = self._session.request(
                    type,
                    endpoint + path,
                    data=data,
                    headers=self._get_request_headers(),
                    timeout=self._timeout,
                )

                OpenStackClient._ensure_valid_response(r, error_message, expects_json=expects_json)
                logger.debug('Result: %s', r.content)
                return r
            except Exception as e:
                if i == len(found_endpoints) - 1:
                    # Endpoint is down, can retry if none is working
                    if isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
                        raise exceptions.RetryableError('All endpoints failed') from e  # With last exception
                    raise e
                logger.warning('Error requesting %s: %s', endpoint + path, e)
                self.cache.remove(cache_key)
                continue

    @auth_required(for_project=True)
    def _get_recurring_from_endpoint(
        self,
        endpoint_types: list[str],
        path: str,
        error_message: str,
        key: str,
        params: typing.Optional[dict[str, str]] = None,
    ) -> collections.abc.Iterable[typing.Any]:
        cache_key = ''.join(endpoint_types)
        found_endpoints = self._get_endpoints_iterable(cache_key, *endpoint_types)

        logger.debug('Requesting from endpoints: %s and path %s', found_endpoints, path)
        # Iterate request over all endpoints, until one works, and store it as cached running endpoint
        for i, endpoint in enumerate(found_endpoints):
            try:
                # If fails, cached endpoint is removed and next one is tried
                self.cache.put(
                    cache_key, endpoint, consts.cache.EXTREME_CACHE_TIMEOUT
                )  # Cache endpoint for a very long time
                yield from OpenStackClient._get_recurring_url_json(
                    endpoint=endpoint,
                    path=path,
                    session=self._session,
                    headers=self._get_request_headers(),
                    key=key,
                    params=params,
                    error_message=error_message,
                    timeout=self._timeout,
                )
                return
            except Exception as e:
                # If last endpoint, raise exception
                if i == len(found_endpoints) - 1:
                    # Endpoint is down, can retry if none is working
                    if isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
                        raise exceptions.RetryableError('All endpoints failed') from e  # With last exception
                    raise e
                logger.warning('Error requesting %s: %s (%s)', endpoint + path, e, error_message)
                self.cache.remove(cache_key)
                
    def set_projectid(self, projectid: str) -> None:
        self._projectid = projectid

    def authenticate(self) -> None:
        # logger.debug('Authenticating...')
        data: dict[str, typing.Any]
        if self._auth_method == openstack_types.AuthMethod.APPLICATION_CREDENTIAL:
            data = {
                'auth': {
                    'identity': {
                        'methods': ['application_credential'],
                        'application_credential': {
                            'id': self._username,
                            'secret': self._password,
                        },
                    }
                }
            }
            # application_credential is not scoped, so we need to use the projectid
        else:
            data = {
                'auth': {
                    'identity': {
                        'methods': ['password'],
                        'password': {
                            'user': {
                                'name': self._username,
                                'domain': {'name': 'Default' if not self._domain else self._domain},
                                'password': self._password,
                            }
                        },
                    }
                }
            }
            # Note that the user domain could be different from the scope domain (the project domain)
            # Currently, we are using the same domain for both
            if self._projectid is not None:
                data['auth']['scope'] = {'project': {'id': self._projectid, 'domain': {'name': self._domain}}}

        if self._projectid is None:
            self._authenticated_projectid = None
            if self._is_legacy:
                data['auth']['scope'] = 'unscoped'
        else:
            self._authenticated_projectid = self._projectid

        # logger.debug('Request data: {}'.format(data))

        r = self._session.post(
            self._identity_endpoint + 'v3/auth/tokens',
            data=json.dumps(data),
            headers={'content-type': 'application/json'},
            timeout=self._timeout,
        )

        OpenStackClient._ensure_valid_response(r, 'Invalid Credentials')

        self._authenticated = True
        self._tokenid = r.headers['X-Subject-Token']
        # Extract the token id
        token = r.json()['token']
        # logger.debug('Got token {}'.format(token))
        self._userid = token['user']['id']
        # validity = (dateutil.parser.parse(token['expires_at']).replace(tzinfo=None) - dateutil.parser.parse(token['issued_at']).replace(tzinfo=None)).seconds - 60

        # logger.debug('The token {} will be valid for {}'.format(self._tokenId, validity))

        # Now, if endpoints are present (only if tenant was specified), store them
        if self._projectid is not None:
            self._catalog = token['catalog']
            logger.debug('Catalog found: %s', self._catalog)
            # Check for the presence of the endpoint for volumes
            # Volume v2 api was deprecated in Pike release, and removed on Xena release
            # Volume v3 api is available since Mitaka. Both are API compatible
            # if self._catalog:
            #    if any(v['type'] == 'volumev3' for v in self._catalog):
            #        'volumev3', 'volumev2' = 'volumev3'
            #    else:
            #        'volumev3', 'volumev2' = 'volumev2'

    def ensure_authenticated(self) -> None:
        if self._authenticated is False or self._projectid != self._authenticated_projectid:
            self.authenticate()

    @auth_required()
    @decorators.cached(prefix='prjs', timeout=consts.cache.EXTREME_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_projects(self) -> list[openstack_types.ProjectInfo]:
        return [
            openstack_types.ProjectInfo.from_dict(p)
            for p in OpenStackClient._get_recurring_url_json(
                self._identity_endpoint,
                'v3/users/{user_id}/projects'.format(user_id=self._userid),
                self._session,
                headers=self._get_request_headers(),
                key='projects',
                error_message='List Projects',
                timeout=self._timeout,
            )
        ]

    @auth_required()
    @decorators.cached(prefix='rgns', timeout=consts.cache.EXTREME_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_regions(self) -> list[openstack_types.RegionInfo]:
        return [
            openstack_types.RegionInfo.from_dict(r)
            for r in OpenStackClient._get_recurring_url_json(
                self._identity_endpoint,
                'v3/regions',
                self._session,
                headers=self._get_request_headers(),
                key='regions',
                error_message='List Regions',
                timeout=self._timeout,
            )
        ]

    @decorators.cached(prefix='svrs', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_servers(
        self,
        detail: bool = False,
        params: typing.Optional[dict[str, str]] = None,
    ) -> list[openstack_types.ServerInfo]:
        return [
            openstack_types.ServerInfo.from_dict(s)
            for s in self._get_recurring_from_endpoint(
                endpoint_types=COMPUTE_ENDPOINT_TYPES,
                path='/servers' + ('/detail' if detail is True else ''),
                error_message='List Vms',
                key='servers',
                params=params,
            )
        ]

    @decorators.cached(prefix='imgs', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_images(self) -> list[openstack_types.ImageInfo]:
        return [
            openstack_types.ImageInfo.from_dict(i)
            for i in self._get_recurring_from_endpoint(
                endpoint_types=['image'],
                path='/v2/images?status=active',
                error_message='List Images',
                key='images',
            )
        ]

    @decorators.cached(prefix='volts', timeout=consts.cache.EXTREME_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_volume_types(self) -> list[openstack_types.VolumeTypeInfo]:
        return [
            openstack_types.VolumeTypeInfo.from_dict(t)
            for t in self._get_recurring_from_endpoint(
                endpoint_types=VOLUMES_ENDPOINT_TYPES,
                path='/types',
                error_message='List Volume Types',
                key='volume_types',
            )
        ]

    @decorators.cached(prefix='vols', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_volumes(self) -> list[openstack_types.VolumeInfo]:
        return [
            openstack_types.VolumeInfo.from_dict(v)
            for v in self._get_recurring_from_endpoint(
                endpoint_types=VOLUMES_ENDPOINT_TYPES,
                path='/volumes/detail',
                error_message='List Volumes',
                key='volumes',
            )
        ]

    @decorators.cached(prefix='snps', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_volume_snapshots(
        self, volume_id: typing.Optional[dict[str, typing.Any]] = None
    ) -> list[openstack_types.SnapshotInfo]:
        return [
            openstack_types.SnapshotInfo.from_dict(snapshot)
            for snapshot in self._get_recurring_from_endpoint(
                endpoint_types=VOLUMES_ENDPOINT_TYPES,
                path='/snapshots',
                error_message='List snapshots',
                key='snapshots',
            )
            if volume_id is None or snapshot['volume_id'] == volume_id
        ]

    @decorators.cached(prefix='azs', timeout=consts.cache.EXTREME_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_availability_zones(self) -> list[openstack_types.AvailabilityZoneInfo]:
        # Only available zones are returned
        return [
            openstack_types.AvailabilityZoneInfo.from_dict(availability_zone)
            for availability_zone in self._get_recurring_from_endpoint(
                endpoint_types=COMPUTE_ENDPOINT_TYPES,
                path='/os-availability-zone',
                error_message='List Availability Zones',
                key='availabilityZoneInfo',
            )
            if availability_zone['zoneState']['available'] is True
        ]

    @decorators.cached(prefix='flvs', timeout=consts.cache.EXTREME_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_flavors(self) -> list[openstack_types.FlavorInfo]:
        return [
            openstack_types.FlavorInfo.from_dict(f)
            for f in self._get_recurring_from_endpoint(
                endpoint_types=COMPUTE_ENDPOINT_TYPES,
                path='/flavors/detail',
                error_message='List Flavors',
                key='flavors',
            )
        ]

    @decorators.cached(prefix='nets', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_networks(self, name_from_subnets: bool = False) -> list[openstack_types.NetworkInfo]:
        nets = self._get_recurring_from_endpoint(
            endpoint_types=NETWORKS_ENDPOINT_TYPES,
            path='/v2.0/networks',
            error_message='List Networks',
            key='networks',
        )

        if not name_from_subnets:
            return [openstack_types.NetworkInfo.from_dict(n) for n in nets]
        else:
            # Get and cache subnets names
            subnets_dct = {s.id: f'{s.name} ({s.cidr})' for s in self.list_subnets()}
            res: list[openstack_types.NetworkInfo] = []
            for net in nets:
                name = ','.join(subnets_dct[i] for i in net['subnets'] if i in subnets_dct)
                if name:
                    net['name'] = name

                res.append(openstack_types.NetworkInfo.from_dict(net))

            return res

    @decorators.cached(prefix='subns', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_subnets(self) -> collections.abc.Iterable[openstack_types.SubnetInfo]:
        return [
            openstack_types.SubnetInfo.from_dict(s)
            for s in self._get_recurring_from_endpoint(
                endpoint_types=NETWORKS_ENDPOINT_TYPES,
                path='/v2.0/subnets',
                error_message='List Subnets',
                key='subnets',
            )
        ]

    @decorators.cached(prefix='sgps', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_ports(
        self,
        network_id: typing.Optional[str] = None,
        owner_id: typing.Optional[str] = None,
    ) -> list[openstack_types.PortInfo]:
        params: dict[str, typing.Any] = {}
        if network_id is not None:
            params['network_id'] = network_id
        if owner_id is not None:
            params['device_owner'] = owner_id

        return [
            openstack_types.PortInfo.from_dict(p)
            for p in self._get_recurring_from_endpoint(
                endpoint_types=NETWORKS_ENDPOINT_TYPES,
                path='/v2.0/ports',
                error_message='List ports',
                key='ports',
                params=params,
            )
        ]

    @decorators.cached(prefix='sgps', timeout=consts.cache.EXTREME_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_security_groups(self) -> list[openstack_types.SecurityGroupInfo]:
        return [
            openstack_types.SecurityGroupInfo.from_dict(sg)
            for sg in self._get_recurring_from_endpoint(
                endpoint_types=NETWORKS_ENDPOINT_TYPES,
                path=f'/v2.0/security-groups?project_id={self._projectid}',
                error_message='List security groups',
                key='security_groups',
            )
        ]

    # Very small timeout, so repeated operations will use same data
    # Any cache time less than 5 seconds will be fine, beceuse checks on
    # openstack are done every 5 seconds
    @decorators.cached(prefix='svr', timeout=consts.cache.SHORTEST_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_server_info(self, server_id: str) -> openstack_types.ServerInfo:
        r = self._request_from_endpoint(
            'get',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path=f'/servers/{server_id}',
            error_message='Get Server information',
        )
        return openstack_types.ServerInfo.from_dict(r.json()['server'])

    @decorators.cached(prefix='vol', timeout=consts.cache.SHORTEST_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def get_volume_info(self, volume_id: str, **kwargs: typing.Any) -> openstack_types.VolumeInfo:
        r = self._request_from_endpoint(
            'get',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path=f'/volumes/{volume_id}',
            error_message='Get Volume information',
        )

        return openstack_types.VolumeInfo.from_dict(r.json()['volume'])

    def get_snapshot_info(self, snapshot_id: str) -> openstack_types.SnapshotInfo:
        """
        States are:
            creating, available, deleting, error,  error_deleting
        """
        r = self._request_from_endpoint(
            'get',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path=f'/snapshots/{snapshot_id}',
            error_message='Get Snaphost information',
        )

        return openstack_types.SnapshotInfo.from_dict(r.json()['snapshot'])

    def update_snapshot(
        self,
        snapshot_id: str,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> openstack_types.SnapshotInfo:
        data: dict[str, typing.Any] = {'snapshot': {}}
        if name:
            data['snapshot']['name'] = name

        if description:
            data['snapshot']['description'] = description

        r = self._request_from_endpoint(
            'put',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path=f'/snapshots/{snapshot_id}',
            data=json.dumps(data),
            error_message='Update Snaphost information',
        )

        return openstack_types.SnapshotInfo.from_dict(r.json()['snapshot'])

    def create_snapshot(
        self, volume_id: str, name: str, description: typing.Optional[str] = None
    ) -> openstack_types.SnapshotInfo:
        description = description or 'UDS Snapshot'
        data = {
            'snapshot': {
                'name': name,
                'description': description,
                'volume_id': volume_id,
                'force': True,
            }
        }

        r = self._request_from_endpoint(
            'post',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path=f'/snapshots',
            data=json.dumps(data),
            error_message='Create Volume Snapshot',
        )

        return openstack_types.SnapshotInfo.from_dict(r.json()['snapshot'])

    def create_volume_from_snapshot(
        self, snapshot_id: str, name: str, description: typing.Optional[str] = None
    ) -> openstack_types.VolumeInfo:
        description = description or 'UDS Volume'
        data = {
            'volume': {
                'name': name,
                'description': description,
                # 'volume_type': volType,  # This seems to be the volume type name, not the id
                'snapshot_id': snapshot_id,
            }
        }

        r = self._request_from_endpoint(
            'post',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path='/volumes',
            data=json.dumps(data),
            error_message='Create Volume from Snapshot',
        )

        return openstack_types.VolumeInfo.from_dict(r.json()['volume'])

    def create_server_from_snapshot(
        self,
        snapshot_id: str,
        name: str,
        availability_zone: str,
        flavor_id: str,
        network_id: str,
        security_groups_names: collections.abc.Iterable[str],
        count: int = 1,
    ) -> openstack_types.ServerInfo:
        data = {
            'server': {
                'name': name,
                'imageRef': '',
                'metadata': {'udsOwner': 'xxxxx'},
                # 'os-availability-zone': availability_zone,
                'availability_zone': availability_zone,
                'block_device_mapping_v2': [
                    {
                        'boot_index': '0',
                        'uuid': snapshot_id,
                        # 'volume_size': 1,
                        # 'device_name': 'vda',
                        'source_type': 'snapshot',
                        'destination_type': 'volume',
                        'delete_on_termination': True,
                    }
                ],
                'flavorRef': flavor_id,
                # 'OS-DCF:diskConfig': 'AUTO',
                'max_count': count,
                'min_count': count,
                'networks': [{'uuid': network_id}],
                'security_groups': [{'name': sg} for sg in security_groups_names],
            }
        }

        r = self._request_from_endpoint(
            'post',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path='/servers',
            data=json.dumps(data),
            error_message='Create instance from snapshot',
        )

        return openstack_types.ServerInfo.from_dict(r.json()['server'])

    def delete_server(self, server_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'delete',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path=f'/servers/{server_id}',
            error_message='Cannot delete server (probably server does not exists).',
            expects_json=False,
        )

    def delete_snapshot(self, snapshot_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'delete',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path=f'/snapshots/{snapshot_id}',
            error_message='Cannot remove snapshot.',
            expects_json=False,
        )

    def start_server(self, server_id: str) -> None:
        # this does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path=f'/servers/{server_id}/action',
            data='{"os-start": null}',
            error_message='Starting server',
            expects_json=False,
        )

    def stop_server(self, server_id: str) -> None:
        # this does not returns anything
        # {"os-resetState": {"state": "error"}}
        self._request_from_endpoint(
            'post',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path=f'/servers/{server_id}/action',
            data='{"os-stop": null}',
            error_message='Stoping server',
            expects_json=False,
        )

    def reboot_server(self, server_id: str, hard: bool = True) -> None:
        # Does not need return value
        try:
            type_reboot = 'HARD' if hard else 'SOFT'
            self._request_from_endpoint(
                'post',
                endpoints_types=COMPUTE_ENDPOINT_TYPES,
                path=f'/servers/{server_id}/action',
                data=f'{{"reboot": {{"type": "{type_reboot}"}}}}',
                error_message='Rebooting server',
                expects_json=False,
            )
        except Exception:
            pass

    def suspend_server(self, server_id: str) -> None:
        # this does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path=f'/servers/{server_id}/action',
            data='{"suspend": null}',
            error_message='Suspending server',
            expects_json=False,
        )

    def resume_server(self, server_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=COMPUTE_ENDPOINT_TYPES,
            path=f'/servers/{server_id}/action',
            data='{"resume": null}',
            error_message='Resuming server',
            expects_json=False,
        )

    def reset_server(self, server_id: str, hard: bool = True) -> None:
        # Does not need return value
        try:
            type_reboot = 'HARD' if hard else 'SOFT'
            self._request_from_endpoint(
                'post',
                endpoints_types=COMPUTE_ENDPOINT_TYPES,
                path=f'/servers/{server_id}/action',
                data='{"reboot":{"type":"' + type_reboot + '"}}',
                error_message='Resetting server',
                expects_json=False,
            )
        except Exception:
            pass  # Ignore error for reseting server

    def test_connection(self) -> bool:
        # First, ensure requested api is supported
        # We need api version 3.2 or greater
        try:
            r = self._session.get(self._identity_endpoint, headers=self._get_request_headers())
        except Exception:
            logger.exception('Testing')
            raise Exception('Connection error')

        try:
            for v in r.json()['versions']['values']:
                if v['id'] >= 'v3.1':
                    # Tries to authenticate
                    try:
                        self.authenticate()
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

    # Low cache, simple to avoid non needed requests
    @decorators.cached(prefix='ava', timeout=4, key_helper=cache_key_helper)
    def is_available(self) -> bool:
        try:
            # If we can connect, it is available
            self._session.get(self._identity_endpoint, headers=self._get_request_headers())
            return True
        except Exception:
            return False

    # Helpers
    @staticmethod
    def _get_recurring_url_json(
        endpoint: str,
        path: str,
        session: 'requests.Session',
        headers: dict[str, str],
        key: str,
        params: typing.Optional[collections.abc.Mapping[str, str]] = None,
        error_message: typing.Optional[str] = None,
        timeout: int = 10,
    ) -> collections.abc.Iterable[typing.Any]:
        counter = 0
        path = endpoint + path
        while True:
            counter += 1
            logger.debug('Requesting url #%s: %s / %s', counter, path, params)
            r = session.get(path, params=params, headers=headers, timeout=timeout)

            OpenStackClient._ensure_valid_response(r, error_message)

            j = r.json()

            logger.debug('Json: *** %s  ***', r.content)

            for v in j[key]:
                yield v

            if 'next' not in j:
                break

            path = j['next']
            if path.startswith('http') is False:
                path = endpoint + path

    @staticmethod
    def _ensure_valid_response(
        response: 'requests.Response', errMsg: typing.Optional[str] = None, expects_json: bool = True
    ) -> None:
        if response.ok is False:
            if not expects_json:
                return  # If not expecting json, simply return
            try:
                # Extract any key, in case of error is expected to have only one top key so this will work
                _, err = response.json().popitem()
                msg = ': {message}'.format(**err)
                errMsg = errMsg + msg if errMsg else msg
            except (
                Exception
            ):  # nosec: If error geting error message, simply ignore it (will be loged on service log anyway)
                pass
            if errMsg is None:
                errMsg = 'Error checking response'
            logger.error('%s: %s', errMsg, response.content)
            raise Exception(errMsg)

    # Only for testing purposes, not used at runtime
    def t_create_volume(self, name: str, size: int) -> openstack_types.VolumeInfo:
        data = {
            'volume': {
                'size': size,
                'name': name,
                # 'volume_type': volume_type,
            }
        }

        r = self._request_from_endpoint(
            'post',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path='/volumes',
            data=json.dumps(data),
            error_message='Create Volume',
        )

        return openstack_types.VolumeInfo.from_dict(r.json()['volume'])

    def t_delete_volume(self, volume_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'delete',
            endpoints_types=VOLUMES_ENDPOINT_TYPES,
            path=f'/volumes/{volume_id}',
            error_message='Cannot delete volume (probably volume does not exists).',
            expects_json=False,
        )
