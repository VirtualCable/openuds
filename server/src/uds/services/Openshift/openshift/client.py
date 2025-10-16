#
# Copyright (c) 2025 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import typing
import datetime
import urllib.parse
import logging


from uds.core.util import security
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached
from uds.core.util.model import sql_now

from . import types, consts, exceptions


import requests

logger = logging.getLogger(__name__)


# caching helper
def caching_key_helper(obj: 'OpenshiftClient') -> str:
    return obj._host  # pylint: disable=protected-access


class OpenshiftClient:
    _host: str
    _port: int
    _username: str
    _password: str
    _verify_ssl: bool
    _timeout: int
    _url: str
    _access_token: str
    _token_expiry: datetime.datetime

    _session: typing.Optional[requests.Session] = None

    cache: typing.Optional['Cache']

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: int = 5,
        verify_ssl: bool = False,
        cache: typing.Optional['Cache'] = None,
        client_id: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password

        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._client_id = client_id or 'morph-api'

        self.cache = cache

        self._access_token = self._refresh_token = ''
        self._token_expiry = datetime.datetime.min

        self._url = f'https://{host}' + (f':{port}' if port != 443 else '') + '/'

    @property
    def session(self) -> requests.Session:
        return self.connect()

    def connect(self, force: bool = False) -> requests.Session:
        now = sql_now()
        if self._access_token and self._session and self._token_expiry > now and not force:
            return self._session

        session = self._session = security.secure_requests_session(verify=self._verify_ssl)
        self._session.headers.update(
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
        )

        def set_auth_header() -> requests.Session:
            """Set the Authorization header with the given token."""
            session.headers.update({'Authorization': f'Bearer {self._access_token}'})
            return session

        # If we have an access token, use it as bearer token
        # If the token is expired, we will refresh it
        # If force is True, we will refresh the token even if it is not expired
        if self._access_token and self._token_expiry > now and not force:
            return set_auth_header()

        try:
            result = session.post(
                # ?client_id=morph-api&grant_type=password&scope=write
                url=self.get_api_url(
                    'oauth/token',
                    ('client_id', self._client_id),
                    ('grant_type', 'password'),
                    ('scope', 'write'),
                ),
                data={
                    'username': self._username,
                    'password': self._password,
                },
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                timeout=self._timeout,
            )
            if not result.ok:
                raise exceptions.OpenshiftAuthError(result.content.decode('utf8'))
            data = result.json()
            self._access_token = data['access_token']
            # self._refresh_token = data['refresh_token']   # Not used, but could be used to refresh the token
            self._token_expiry = datetime.datetime.now() + datetime.timedelta(
                seconds=data.get('expires_in', 3600)
            )  # Default to 1 hour if not provided
            return set_auth_header()
        except requests.RequestException as e:
            raise exceptions.OpenshiftConnectionError(str(e)) from e

    def get_api_url(self, path: str, *parameters: tuple[str, str]) -> str:
        url = self._url + path
        if parameters:
            url += '?' + urllib.parse.urlencode(
                parameters, doseq=True, safe='[]', quote_via=urllib.parse.quote_plus
            )
        return url

    def do_request(
        self,
        method: typing.Literal['GET', 'POST', 'PUT', 'DELETE'],
        path: str,
        *parameters: tuple[str, str],
        data: typing.Any = None,
        check_for_success: bool = False,
    ) -> typing.Any:
        logger.debug(
            'Requesting %s %s with parameters %s and data %s',
            method.upper(),
            path,
            parameters,
            data,
        )
        try:
            match method:
                case 'GET':
                    response = self.session.get(
                        self.get_api_url(path, *parameters),
                        timeout=self._timeout,
                    )
                case 'POST':
                    response = self.session.post(
                        self.get_api_url(path, *parameters),
                        json=data,
                        timeout=self._timeout,
                    )
                case 'PUT':
                    response = self.session.put(
                        self.get_api_url(path, *parameters),
                        json=data,
                        timeout=self._timeout,
                    )
                case 'DELETE':
                    response = self.session.delete(
                        self.get_api_url(path, *parameters),
                        timeout=self._timeout,
                    )
                case _:
                    raise ValueError(f'Unsupported HTTP method: {method}')
        except requests.ConnectionError as e:
            raise exceptions.OpenshiftConnectionError(str(e))
        except requests.RequestException as e:
            raise exceptions.OpenshiftError(f'Error during request: {str(e)}')
        logger.debug('Request result to %s: %s -- %s', path, response.status_code, response.content[:64])

        if not response.ok:
            if response.status_code == 401:
                # Unauthorized, try to refresh the token
                logger.debug('Unauthorized request, refreshing token')
                self._session = None
                raise exceptions.OpenshiftAuthError(
                    'Unauthorized request, please check your credentials or token expiry'
                )
            elif response.status_code == 403:
                # Forbidden, user does not have permissions
                logger.debug('Forbidden request, check your permissions')
                raise exceptions.OpenshiftPermissionError('Forbidden request, please check your permissions')
            elif response.status_code == 404:
                # Not found, resource does not exist
                logger.debug('Resource not found: %s', path)
                raise exceptions.OpenshiftNotFoundError(f'Resource not found: {path}')

            error_message = f'Error on request {method.upper()} {path}: {response.status_code} - {response.content.decode("utf8")[:128]}'
            logger.debug(error_message)
            raise exceptions.OpenshiftError(error_message)

        try:
            data = response.json()
        except Exception as e:
            error_message = f'Error parsing JSON response from {method.upper()} {path}: {str(e)}'
            logger.debug(error_message)
            raise exceptions.OpenshiftError(error_message)

        if check_for_success and not data.get('success', False):
            error_message = f'Error on request {method.upper()} {path}: {data.get("error", "Unknown error")}'
            logger.debug(error_message)
            raise exceptions.OpenshiftError(error_message)

        return data

    def do_paginated_request(
        self,
        method: typing.Literal['GET', 'POST', 'PUT', 'DELETE'],
        path: str,
        key: str,
        *parameters: tuple[str, str],
        data: typing.Any = None,
    ) -> typing.Iterator[typing.Any]:
        """
        Make a paginated request to the Openshift API.
        Args:
            method (str): HTTP method to use (GET, POST, PUT, DELETE)
            path (str): API endpoint path
            *parameters: Additional parameters to include in the request
            data (Any): Data to send with the request (for POST/PUT)
        Yields:
            typing.Any: The JSON response from each page of the request

        Note:
            The responses has also the "meta" key, which contains pagination information:
            offset: int64
            max: int64
            size: int64
            total: int64

            This information is used to determine if there are more pages to fetch.
            If not present, we try our best by counting the number of items returned
            and comparing it with the items requested per page (consts.MAX_ITEMS_PER_REQUEST).
        """
        offset = 0
        while True:
            params: list[tuple[str, str]] = [i for i in parameters] + [
                ('max', str(consts.MAX_ITEMS_PER_REQUEST)),
                ('offset', str(offset)),
            ]
            response = self.do_request(method, path, *params, data=data)
            data = response.get(key, [])
            yield from data

            # Checke meta information to see if we have more pages
            meta = response.get('meta', {})
            if not meta:  # Do our best to avoid errors if meta is not present
                # Check if we have more pages
                if len(data) < consts.MAX_ITEMS_PER_REQUEST:
                    break
            elif meta.get('offset', 0) + meta.get('size', 0) >= meta.get('total', 0):
                # No more pages, as offset is greater than or equal to total
                break

            offset += consts.MAX_ITEMS_PER_REQUEST

    @cached('test', consts.CACHE_VM_INFO_DURATION, key_helper=caching_key_helper)
    def test(self) -> bool:
        try:
            self.connect(force=True)
        except Exception:
            # logger.error('Error testing Openshift: %s', e)
            return False
        return True

    # Not cacheable, as it is a generator
    def enumerate_instances(
        self, *, name: str | None = None, detailed: bool = False, show_deleted: bool = False
    ) -> collections.abc.Iterator[types.InstanceInfo]:
        """
        Get all instances from Openshift

        Args:
            name (str|None): If provided, filter instances by name (case-insensitive?)
            detailed (bool): If True, return detailed information about instances

        Yields:
            types.Instance: An instance object with the details of each instance

        Raises:
            OpenshiftError: If there is an error getting the instances
        """
        params = [
            ('showDeleted', str(show_deleted).lower()),
            ('details', str(detailed).lower()),
        ]
        if name:
            params.append(('name', name))
        yield from (
            types.InstanceInfo.from_dict(instance)
            for instance in self.do_paginated_request('GET', 'api/instances', 'instances', *params)
        )

    @cached('instances', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    def list_instances(
        self,
        *,
        name: str | None = None,
        detailed: bool = False,
        show_deleted: bool = False,
        force: bool = False,
    ) -> list[types.InstanceInfo]:
        return list(self.enumerate_instances(name=name, detailed=detailed, show_deleted=show_deleted))

    @cached('instance', consts.CACHE_VM_INFO_DURATION, key_helper=caching_key_helper)
    def get_instance_info(self, instance_id: str | int, force: bool = False) -> types.InstanceInfo:
        """
        Get a specific instance by ID
        """
        OpenshiftClient.validate_instance_id(instance_id)

        response = self.do_request(
            'GET',
            f'api/instances/{instance_id}',
            ('details', 'true'),
        )
        return types.InstanceInfo.from_dict(response['instance'])

    def clone_instance(self, instance_id: str | int, name: str, group_id: int | None = None) -> None:
        """
        Clone a specific instance by ID

        TODO: maybe we can change the network interface configuration
            "networkInterfaces": [{ "network": { "id": "subnet-12542" } }]
        """
        # "https://172.27.0.1/api/instances/{id}/clone"
        # Params: name, group: {'id': id} (optional)
        OpenshiftClient.validate_instance_id(instance_id)

        data: dict[str, typing.Any] = {
            'name': name,
        }
        if group_id is not None:
            data['group'] = {'id': group_id}
        self.do_request(
            'PUT',
            f'api/instances/{instance_id}/clone',
            data=data,
            check_for_success=True,
        )

    def start_instance(self, instance_id: str | int) -> None:
        """
        Start a specific instance by ID

        Args:
            instance_id (int): The ID of the instance to start

        Raises:
            OpenshiftError: If there is an error starting the instance
        """
        OpenshiftClient.validate_instance_id(instance_id)

        self.do_request(
            'PUT',
            f'api/instances/{instance_id}/start',
            check_for_success=True,
        )

    def stop_instance(self, instance_id: str | int) -> None:
        """
        Stop a specific instance by ID

        Args:
            instance_id (int): The ID of the instance to stop
            force (bool): If True, force stop the instance

        Raises:
            OpenshiftError: If there is an error stopping the instance
        """
        OpenshiftClient.validate_instance_id(instance_id)

        self.do_request(
            'PUT',
            f'api/instances/{instance_id}/stop',
            check_for_success=True,
        )

    def restart_instance(self, instance_id: str | int) -> None:
        """
        Restart a specific instance by ID

        Args:
            instance_id (int): The ID of the instance to restart
            force (bool): If True, force restart the instance

        Raises:
            OpenshiftError: If there is an error restarting the instance
        """
        OpenshiftClient.validate_instance_id(instance_id)

        self.do_request(
            'PUT',
            f'api/instances/{instance_id}/restart',
            check_for_success=True,
        )

    def delete_instance(self, instance_id: str | int, force: bool = False) -> None:
        """
        Delete a specific instance by ID

        Args:
            instance_id (int): The ID of the instance to delete

        Raises:
            OpenshiftError: If there is an error deleting the instance
        """
        OpenshiftClient.validate_instance_id(instance_id)
        params = [('force', 'true')] if force else []

        self.do_request(
            'DELETE',
            f'api/instances/{instance_id}',
            *params,
            check_for_success=True,
        )

    def enumerate_groups(self) -> collections.abc.Iterator[types.BasicInfo]:
        """
        Get all groups from Openshift

        Yields:
            types.IdValuePair: An IdValuePair object with the details of each group
        """
        yield from (
            types.BasicInfo.from_dict(group)
            for group in self.do_paginated_request('GET', 'api/groups', 'groups')
        )

    @cached('groups', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    def list_groups(self, force: bool = False) -> list[types.BasicInfo]:
        """
        List all groups available in Openshift

        Returns:
            list[types.IdValuePair]: A list of IdValuePair objects representing the groups
        """
        return list(self.enumerate_groups())

    def enumerate_clouds(self, group_id: int | None = None) -> collections.abc.Iterator[types.BasicInfo]:
        """
        Get all clouds from Openshift
        Args:
            group (str|None): If provided, filter clouds by group name
        Yields:
            types.BasicInfo: An IdValuePair object with the details of each cloud
        """
        parameters: list[tuple[str, str]] = []
        if group_id is not None:
            parameters.append(('groupId', str(group_id)))
        yield from (
            types.BasicInfo.from_dict(cloud)
            for cloud in self.do_paginated_request('GET', 'api/zones', 'zones', *parameters)
        )

    @cached('clouds', consts.CACHE_INFO_DURATION, key_helper=caching_key_helper)
    def list_clouds(self, group_id: int | None = None, force: bool = False) -> list[types.BasicInfo]:
        """
        List all clouds available in Openshift

        Returns:
            list[types.IdValuePair]: A list of IdValuePair objects representing the clouds
        """
        return list(self.enumerate_clouds(group_id=group_id))

    @staticmethod
    def validate_instance_id(instance_id: str | int) -> None:
        try:
            int(instance_id)
        except ValueError:
            raise exceptions.OpenshiftNotFoundError(f'Instance {instance_id} not found')
