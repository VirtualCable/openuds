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

from uds.core.util import security, cache, decorators

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
def ensure_valid_response(response: 'requests.Response', errMsg: typing.Optional[str] = None) -> None:
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
        except (
            Exception
        ):  # nosec: If error geting error message, simply ignore it (will be loged on service log anyway)
            pass
        if errMsg is None:
            errMsg = 'Error checking response'
        logger.error('%s: %s', errMsg, response.content)
        raise Exception(errMsg)


def get_recurring_url_json(
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
    while True:
        counter += 1
        logger.debug('Requesting url #%s: %s%s / %s', counter, endpoint, path, params)
        r = session.get(endpoint + path, params=params, headers=headers, timeout=timeout)

        ensure_valid_response(r, error_message)

        j = r.json()

        for v in j[key]:
            yield v

        if 'next' not in j:
            break

        logger.debug('Json: %s', j)

        path = j['next']


# Decorators
def auth_required(for_project: bool = False) -> collections.abc.Callable[[decorators.FT], decorators.FT]:

    def decorator(func: decorators.FT) -> decorators.FT:
        @functools.wraps(func)
        def wrapper(obj: 'Client', *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            if for_project is True:
                if obj._projectid is None:
                    raise Exception('Need a project for method {}'.format(func))
            obj.ensure_authenticated()
            return func(obj, *args, **kwargs)

        return typing.cast(decorators.FT, wrapper)

    return decorator


def cache_key_helper(obj: 'Client', *args: typing.Any, **kwargs: typing.Any) -> str:
    return '_'.join(
        [
            obj._authurl,
            obj._domain,
            obj._username,
            obj._password,
            str(obj._projectid),
            str(obj._region),
            str(obj._access),
            str(args),
            str(kwargs),
        ]
    )


class Client:  # pylint: disable=too-many-public-methods
    PUBLIC = 'public'
    PRIVATE = 'private'
    INTERNAL = 'url'

    _authenticated: bool
    _authenticatedProjectId: typing.Optional[str]
    _authurl: str
    _tokenid: typing.Optional[str]
    _catalog: typing.Optional[list[dict[str, typing.Any]]]
    _is_legacy: bool
    _volume: str
    _access: typing.Optional[str]
    _domain: str
    _username: str
    _password: str
    _userid: typing.Optional[str]
    _projectid: typing.Optional[str]
    _project: typing.Optional[str]
    _region: typing.Optional[str]
    _timeout: int
    _session: 'requests.Session'

    # Cache for data
    cache: 'cache.Cache'

    # Legacyversion is True for versions <= Ocata
    def __init__(
        self,
        host: str,
        port: typing.Union[str, int],
        domain: str,
        username: str,
        password: str,
        is_legacy: bool = True,
        use_ssl: bool = False,
        projectid: typing.Optional[str] = None,
        region: typing.Optional[str] = None,
        access: typing.Optional[str] = None,
        proxies: typing.Optional[dict[str, str]] = None,
    ):
        self._session = security.secure_requests_session(verify=VERIFY_SSL)
        if proxies:
            self._session.proxies = proxies

        self._authenticated = False
        self._authenticatedProjectId = None
        self._tokenid = None
        self._catalog = None
        self._is_legacy = is_legacy

        self._access = Client.PUBLIC if access is None else access
        self._domain, self._username, self._password = domain, username, password
        self._userid = None
        self._projectid = projectid
        self._project = None
        self._region = region
        self._timeout = 10
        self._volume = ''

        if is_legacy:
            self._authurl = 'http{}://{}:{}/'.format('s' if use_ssl else '', host, port)
        else:
            self._authurl = host  # Host contains auth URL
            if self._authurl[-1] != '/':
                self._authurl += '/'

        self.cache = cache.Cache(f'openstack_{host}_{port}_{domain}_{username}_{projectid}_{region}')

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

    def _get_endpoints_iterable(self, cache_key: str, *type_: str) -> list[str]:
        # If endpoint is cached, use it as first endpoint
        found_endpoints = list(self._get_endpoints_for(*type_))
        if self.cache.get(cache_key) in found_endpoints:
            # If cached endpoint is in the list, use it as first endpoint
            found_endpoints = [self.cache.get(cache_key)] + list(
                set(found_endpoints) - {self.cache.get(cache_key)}
            )

        logger.debug('Endpoints for %s: %s', type_, found_endpoints)

        return found_endpoints

    @auth_required(for_project=True)
    def _request_from_endpoint(
        self,
        type: typing.Literal['get', 'put', 'post', 'delete'],
        endpoints_types: list[str],
        path: str,
        error_message: str,
        data: typing.Any = None,
    ) -> typing.Any:
        cache_key = ''.join(endpoints_types)
        found_endpoints = self._get_endpoints_iterable(cache_key, *endpoints_types)

        for i, endpoint in enumerate(found_endpoints):
            try:
                r = self._session.request(
                    type,
                    endpoint + path,
                    data=data,
                    headers=self._get_request_headers(),
                    timeout=self._timeout,
                )
                ensure_valid_response(r, error_message)
                return r
            except Exception as e:
                if i == len(found_endpoints) - 1:
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
                yield from get_recurring_url_json(
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
                    raise e
                logger.warning('Error requesting %s: %s (%s)', endpoint + path, e, error_message)
                self.cache.remove(cache_key)

    def authenticate_with_password(self) -> None:
        # logger.debug('Authenticating...')
        data: dict[str, typing.Any] = {
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

        if self._projectid is None:
            self._authenticatedProjectId = None
            if self._is_legacy:
                data['auth']['scope'] = 'unscoped'
        else:
            self._authenticatedProjectId = self._projectid
            data['auth']['scope'] = {'project': {'id': self._projectid, 'domain': {'name': self._domain}}}

        # logger.debug('Request data: {}'.format(data))

        r = self._session.post(
            self._authurl + 'v3/auth/tokens',
            data=json.dumps(data),
            headers={'content-type': 'application/json'},
            timeout=self._timeout,
        )

        ensure_valid_response(r, 'Invalid Credentials')

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
            # Check for the presence of the endpoint for volumes
            # Volume v2 api was deprecated in Pike release, and removed on Xena release
            # Volume v3 api is available since Mitaka. Both are API compatible
            if self._catalog:
                if any(v['type'] == 'volumev3' for v in self._catalog):
                    self._volume = 'volumev3'
                else:
                    self._volume = 'volumev2'

    def ensure_authenticated(self) -> None:
        if self._authenticated is False or self._projectid != self._authenticatedProjectId:
            self.authenticate_with_password()

    @auth_required()
    def list_projects(self) -> list[typing.Any]:
        return list(
            get_recurring_url_json(
                self._authurl,
                'v3/users/{user_id}/projects'.format(user_id=self._userid),
                self._session,
                headers=self._get_request_headers(),
                key='projects',
                error_message='List Projects',
                timeout=self._timeout,
            )
        )

    @auth_required()
    def list_regions(self) -> list[typing.Any]:
        return list(
            get_recurring_url_json(
                self._authurl,
                'v3/regions/',
                self._session,
                headers=self._get_request_headers(),
                key='regions',
                error_message='List Regions',
                timeout=self._timeout,
            )
        )

    @decorators.cached(prefix='svrs', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_servers(
        self,
        detail: bool = False,
        params: typing.Optional[dict[str, str]] = None,
    ) -> list[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=['compute', 'compute_legacy'],
                path='/servers' + ('/detail' if detail is True else ''),
                error_message='List Vms',
                key='servers',
                params=params,
            )
        )

    @decorators.cached(prefix='imgs', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_images(self) -> list[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=['image'],
                path='/v2/images?status=active',
                error_message='List Images',
                key='images',
            )
        )

    @decorators.cached(prefix='volts', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_volume_types(self) -> list[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=[self._volume],
                path='/types',
                error_message='List Volume Types',
                key='volume_types',
            )
        )

        # TODO: Remove this
        # return get_recurring_url_json(
        #     self._get_endpoint_for(self._volume) + '/types',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='volume_types',
        #     error_message='List Volume Types',
        #     timeout=self._timeout,
        # )

    @decorators.cached(prefix='vols', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_volumes(self) -> list[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=[self._volume],
                path='/volumes/detail',
                error_message='List Volumes',
                key='volumes',
            )
        )

        # TODO: Remove this
        # return get_recurring_url_json(
        #     self._get_endpoint_for(self._volume) + '/volumes/detail',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='volumes',
        #     error_message='List Volumes',
        #     timeout=self._timeout,
        # )

    def list_volume_snapshots(
        self, volume_id: typing.Optional[dict[str, typing.Any]] = None
    ) -> list[typing.Any]:
        return [
            snapshot
            for snapshot in self._get_recurring_from_endpoint(
                endpoint_types=[self._volume],
                path='/snapshots',
                error_message='List snapshots',
                key='snapshots',
            )
            if volume_id is None or snapshot['volume_id'] == volume_id
        ]

        # TODO: Remove this
        # for s in get_recurring_url_json(
        #     self._get_endpoint_for(self._volume) + '/snapshots',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='snapshots',
        #     error_message='List snapshots',
        #     timeout=self._timeout,
        # ):
        #     if volume_id is None or s['volume_id'] == volume_id:
        #         yield s

    @decorators.cached(prefix='azs', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_availability_zones(self) -> list[typing.Any]:
        return [
            availability_zone['zoneName']
            for availability_zone in self._get_recurring_from_endpoint(
                endpoint_types=['compute', 'compute_legacy'],
                path='/os-availability-zone',
                error_message='List Availability Zones',
                key='availabilityZoneInfo',
            )
            if availability_zone['zoneState']['available'] is True
        ]

        # TODO: Remove this
        # for az in get_recurring_url_json(
        #     self._get_compute_endpoint() + '/os-availability-zone',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='availabilityZoneInfo',
        #     error_message='List Availability Zones',
        #     timeout=self._timeout,
        # ):
        #     if az['zoneState']['available'] is True:
        #         yield az['zoneName']

    @decorators.cached(prefix='flvs', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_flavors(self) -> list[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=['compute', 'compute_legacy'],
                path='/flavors',
                error_message='List Flavors',
                key='flavors',
            )
        )

        # TODO: Remove this
        # return get_recurring_url_json(
        #     self._get_compute_endpoint() + '/flavors',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='flavors',
        #     error_message='List Flavors',
        #     timeout=self._timeout,
        # )

    @decorators.cached(prefix='nets', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_networks(self, name_from_subnets: bool = False) -> list[typing.Any]:
        nets = self._get_recurring_from_endpoint(
            endpoint_types=['network'],
            path='/v2.0/networks',
            error_message='List Networks',
            key='networks',
        )

        # TODO: Remove this
        # nets = get_recurring_url_json(
        #     self._get_endpoint_for('network') + '/v2.0/networks',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='networks',
        #     error_message='List Networks',
        #     timeout=self._timeout,
        # )
        if not name_from_subnets:
            return list(nets)
        else:
            # Get and cache subnets names
            subnetNames = {s['id']: s['name'] for s in self.list_subnets()}
            res: list[typing.Any] = []
            for net in nets:
                name = ','.join(subnetNames[i] for i in net['subnets'] if i in subnetNames)
                net['old_name'] = net['name']
                if name:
                    net['name'] = name

                res.append(net)
            return res

    @decorators.cached(prefix='subns', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_subnets(self) -> collections.abc.Iterable[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=['network'],
                path='/v2.0/subnets',
                error_message='List Subnets',
                key='subnets',
            )
        )

        # TODO: Remove this
        # return get_recurring_url_json(
        #     self._get_endpoint_for('network') + '/v2.0/subnets',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='subnets',
        #     error_message='List Subnets',
        #     timeout=self._timeout,
        # )

    @decorators.cached(prefix='sgps', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_ports(
        self,
        networkId: typing.Optional[str] = None,
        ownerId: typing.Optional[str] = None,
    ) -> list[typing.Any]:
        params: dict[str, typing.Any] = {}
        if networkId is not None:
            params['network_id'] = networkId
        if ownerId is not None:
            params['device_owner'] = ownerId

        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=['network'],
                path='/v2.0/ports',
                error_message='List ports',
                key='ports',
                params=params,
            )
        )

        # TODO: Remove this
        # return get_recurring_url_json(
        #     self._get_endpoint_for('network') + '/v2.0/ports',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='ports',
        #     params=params,
        #     error_message='List ports',
        #     timeout=self._timeout,
        # )

    @decorators.cached(prefix='sgps', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=cache_key_helper)
    def list_security_groups(self) -> list[typing.Any]:
        return list(
            self._get_recurring_from_endpoint(
                endpoint_types=['network'],
                path='/v2.0/security-groups',
                error_message='List security groups',
                key='security_groups',
            )
        )

        # TODO: Remove this
        # return get_recurring_url_json(
        #     self._get_compute_endpoint() + '/os-security-groups',
        #     self._session,
        #     headers=self._get_request_headers(),
        #     key='security_groups',
        #     error_message='List security groups',
        #     timeout=self._timeout,
        # )

    def get_server(self, server_id: str) -> dict[str, typing.Any]:
        r = self._request_from_endpoint(
            'get',
            endpoints_types=['compute', 'compute_legacy'],
            path=f'/servers/{server_id}',
            error_message='Get Server information',
        )
        return r.json()['server']

    def get_volume(self, volumeId: str) -> dict[str, typing.Any]:
        r = self._request_from_endpoint(
            'get',
            endpoints_types=[self._volume],
            path=f'/volumes/{volumeId}',
            error_message='Get Volume information',
        )

        # TODO: Remove this
        # r = self._session.get(
        #     self._get_endpoint_for(self._volume) + '/volumes/{volume_id}'.format(volume_id=volumeId),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Get Volume information')

        return r.json()['volume']

    def get_snapshot(self, snapshot_id: str) -> dict[str, typing.Any]:
        """
        States are:
            creating, available, deleting, error,  error_deleting
        """
        r = self._request_from_endpoint(
            'get',
            endpoints_types=[self._volume],
            path=f'/snapshots/{snapshot_id}',
            error_message='Get Snaphost information',
        )

        # TODO: Remove this
        # r = self._session.get(
        #     self._get_endpoint_for(self._volume) + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Get Snaphost information')

        return r.json()['snapshot']

    def update_snapshot(
        self,
        snapshot_id: str,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        data: dict[str, typing.Any] = {'snapshot': {}}
        if name:
            data['snapshot']['name'] = name

        if description:
            data['snapshot']['description'] = description

        r = self._request_from_endpoint(
            'put',
            endpoints_types=[self._volume],
            path=f'/snapshots/{snapshot_id}',
            data=json.dumps(data),
            error_message='Update Snaphost information',
        )

        # TODO: Remove this
        # r = self._session.put(
        #     self._get_endpoint_for(self._volume) + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshot_id),
        #     data=json.dumps(data),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Update Snaphost information')

        return r.json()['snapshot']

    def create_volume_snapshot(
        self, volume_id: str, name: str, description: typing.Optional[str] = None
    ) -> dict[str, typing.Any]:
        description = description or 'UDS Snapshot'
        data = {
            'snapshot': {
                'name': name,
                'description': description,
                'volume_id': volume_id,
                'force': True,
            }
        }

        # First, ensure volume is in state "available"

        r = self._request_from_endpoint(
            'post',
            endpoints_types=[self._volume],
            path=f'/volumes/{volume_id}',
            data=json.dumps(data),
            error_message='Get Volume information',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._get_endpoint_for(self._volume) + '/snapshots',
        #     data=json.dumps(data),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Cannot create snapshot. Ensure volume is in state "available"')

        return r.json()['snapshot']

    def create_volume_from_snapshot(
        self, snapshotId: str, name: str, description: typing.Optional[str] = None
    ) -> dict[str, typing.Any]:
        description = description or 'UDS Volume'
        data = {
            'volume': {
                'name': name,
                'description': description,
                # 'volume_type': volType,  # This seems to be the volume type name, not the id
                'snapshot_id': snapshotId,
            }
        }

        r = self._request_from_endpoint(
            'post',
            endpoints_types=[self._volume],
            path='/volumes',
            data=json.dumps(data),
            error_message='Create Volume from Snapshot',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._get_endpoint_for(self._volume) + '/volumes',
        #     data=json.dumps(data),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Cannot create volume from snapshot.')

        return r.json()['volume']

    def create_server_from_snapshot(
        self,
        snapshotId: str,
        name: str,
        availability_zone: str,
        flavorId: str,
        networkId: str,
        securityGroupsIdsList: collections.abc.Iterable[str],
        count: int = 1,
    ) -> dict[str, typing.Any]:
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

        r = self._request_from_endpoint(
            'post',
            endpoints_types=['compute', 'compute_legacy'],
            path='/servers',
            data=json.dumps(data),
            error_message='Create instance from snapshot',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._get_compute_endpoint() + '/servers',
        #     data=json.dumps(data),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Cannot create instance from snapshot.')

        return r.json()['server']

    @auth_required(for_project=True)
    def delete_server(self, server_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'delete',
            endpoints_types=['compute', 'compute_legacy'],
            path=f'/servers/{server_id}',
            error_message='Cannot delete server (probably server does not exists).',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._getEndpointFor('compute', , 'compute_legacy') + '/servers/{server_id}/action'.format(server_id=serverId),
        #     data='{"forceDelete": null}',
        #     headers=self._requestHeaders(),
        #     timeout=self._timeout
        # )

        # r = self._session.delete(
        #     self._get_compute_endpoint() + f'/servers/{server_id}',
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Cannot delete server (probably server does not exists).')

    def delete_snapshot(self, snapshot_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'delete',
            endpoints_types=[self._volume],
            path=f'/snapshots/{snapshot_id}',
            error_message='Cannot remove snapshot.',
        )

        # TODO: Remove this
        # r = self._session.delete(
        #     self._get_endpoint_for(self._volume) + '/snapshots/{snapshot_id}'.format(snapshot_id=snapshotId),
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Cannot remove snapshot.')

        # Does not returns a message body

    def start_server(self, server_id: str) -> None:
        # this does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=['compute', 'compute_legacy'],
            path=f'/servers/{server_id}/action',
            data='{"os-start": null}',
            error_message='Starting server',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._get_compute_endpoint() + f'/servers/{server_id}/action',
        #     data='{"os-start": null}',
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Starting server')

    def stop_server(self, server_id: str) -> None:
        # this does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=['compute', 'compute_legacy'],
            path=f'/servers/{server_id}/action',
            data='{"os-stop": null}',
            error_message='Stoping server',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._get_compute_endpoint() + f'/servers/{server_id}/action',
        #     data='{"os-stop": null}',
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Stoping server')

    @auth_required(for_project=True)
    def suspend_server(self, server_id: str) -> None:
        # this does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=['compute', 'compute_legacy'],
            path=f'/servers/{server_id}/action',
            data='{"suspend": null}',
            error_message='Suspending server',
        )

        # TODO: Remove this
        # r = self._session.post(
        #     self._get_compute_endpoint() + f'/servers/{server_id}/action',
        #     data='{"suspend": null}',
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Suspending server')

    def resume_server(self, server_id: str) -> None:
        # This does not returns anything
        self._request_from_endpoint(
            'post',
            endpoints_types=['compute', 'compute_legacy'],
            path=f'/servers/{server_id}/action',
            data='{"resume": null}',
            error_message='Resuming server',
        )

        # r = self._session.post(
        #     self._get_compute_endpoint() + f'/servers/{server_id}/action',
        #     data='{"resume": null}',
        #     headers=self._get_request_headers(),
        #     timeout=self._timeout,
        # )

        # ensure_valid_response(r, 'Resuming server')

    def reset_server(self, server_id: str) -> None:
        # Does not need return value
        self._session.post(
            self._get_compute_endpoint() + f'/servers/{server_id}/action',
            data='{"reboot":{"type":"HARD"}}',
            headers=self._get_request_headers(),
            timeout=self._timeout,
        )

        # Ignore response for this...
        # ensureResponseIsValid(r, 'Reseting server')

    def test_connection(self) -> bool:
        # First, ensure requested api is supported
        # We need api version 3.2 or greater
        try:
            r = self._session.get(self._authurl, headers=self._get_request_headers())
        except Exception:
            logger.exception('Testing')
            raise Exception('Connection error')

        try:
            for v in r.json()['versions']['values']:
                if v['id'] >= 'v3.1':
                    # Tries to authenticate
                    try:
                        self.authenticate_with_password()
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

    def is_available(self) -> bool:
        try:
            # If we can connect, it is available
            self._session.get(self._authurl, headers=self._get_request_headers())
            return True
        except Exception:
            return False
