# -*- coding: utf-8 -*-

#
# Copyright (c) 2017-2023 Virtual Cable S.L.U.
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
import re
import json
import logging
import typing
import collections.abc

from uds.core import consts

from uds.core.util.decorators import ensure_connected
from uds.core.util import security

from . import urls
from . import fake
from . import types

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import requests
    from uds.core.util.cache import Cache

# Fake part
FAKE: typing.Final[bool] = True
CACHE_VALIDITY: typing.Final[int] = consts.cache.DEFAULT_CACHE_TIMEOUT
TIMEOUT: typing.Final[int] = 10

RT = typing.TypeVar('RT')


# Result checker
def ensure_response_is_valid(
    response: 'requests.Response', error_message: typing.Optional[str] = None
) -> typing.Any:
    if not response.ok:
        if not error_message:
            error_message = 'Invalid response'

        try:
            # Extract any key, in case of error is expected to have only one top key so this will work
            err = response.json()['message']
        except Exception:
            err = response.content.decode()
        if 'Database error' in err:
            err = 'Database error: Please, check OpenGnsys fields length on remotepc table (loginurl and logouturl)'

        error_message = '{}: {}, ({})'.format(error_message, err, response.status_code)
        logger.error('%s: %s', error_message, response.content)
        raise Exception(error_message)

    try:
        return json.loads(response.content)
    except Exception:
        raise Exception('Error communicating with OpenGnsys: {}'.format(response.content[:128].decode()))


class OpenGnsysClient:
    username: str
    password: str
    endpoint: str
    auth: typing.Optional[str]
    cache: 'Cache'
    verify_ssl: bool
    cached_version: typing.Optional[str]

    def __init__(
        self,
        username: str,
        password: str,
        endpoint: str,
        cache: 'Cache',
        verify_ssl: bool = False,
    ):
        self.username = username
        self.password = password
        self.endpoint = endpoint
        self.auth = None
        self.cache = cache
        self.verify_ssl = verify_ssl
        self.cached_version = None

    @property
    def headers(self) -> collections.abc.MutableMapping[str, str]:
        headers = {'content-type': 'application/json'}
        if self.auth:
            headers['Authorization'] = self.auth

        return headers

    def _og_endpoint(self, path: str) -> str:
        return self.endpoint + '/' + path

    def _post(self, path: str, data: typing.Any, error_message: typing.Optional[str] = None) -> typing.Any:
        if not FAKE:
            return ensure_response_is_valid(
                security.secure_requests_session(verify=self.verify_ssl).post(
                    self._og_endpoint(path),
                    data=json.dumps(data),
                    headers=self.headers,
                    timeout=TIMEOUT,
                ),
                error_message=error_message,
            )
        # FAKE Connection :)
        return fake.post(path, data, error_message)

    def _get(self, path: str, error_message: typing.Optional[str] = None) -> typing.Any:
        if not FAKE:
            return ensure_response_is_valid(
                security.secure_requests_session(verify=self.verify_ssl).get(
                    self._og_endpoint(path),
                    headers=self.headers,
                    verify=self.verify_ssl,
                    timeout=TIMEOUT,
                ),
                error_message=error_message,
            )
        # FAKE Connection :)
        return fake.get(path, error_message)

    def _delete(self, path: str, error_message: typing.Optional[str] = None) -> typing.Any:
        if not FAKE:
            return ensure_response_is_valid(
                security.secure_requests_session(verify=self.verify_ssl).delete(
                    self._og_endpoint(path),
                    headers=self.headers,
                    timeout=TIMEOUT,
                ),
                error_message=error_message,
            )
        return fake.delete(path, error_message)

    def connect(self) -> None:
        if self.auth:
            return

        cacheKey = 'auth{}{}'.format(self.endpoint, self.username)
        self.auth = self.cache.get(cacheKey)
        if self.auth:
            return

        auth = self._post(
            urls.LOGIN,
            data={'username': self.username, 'password': self.password},
            error_message='Loggin in',
        )

        self.auth = auth['apikey']
        self.cache.put(cacheKey, self.auth, CACHE_VALIDITY)

    @property
    def version(self) -> str:
        logger.debug('Getting version')
        if not self.cached_version:
            # Retrieve Version & keep it
            info = self._get(urls.INFO, error_message="Retrieving info")
            self.cached_version = info['version']

        return typing.cast(str, self.cached_version)

    @ensure_connected
    def list_of_ous(self) -> list[types.OGOuInfo]:
        # Returns an array of elements with:
        # 'id': OpenGnsys Id
        # 'name': OU name
        # OpenGnsys already returns it in this format :)
        return [
            {'id': ou['id'], 'name': ou['name']}
            for ou in self._get(urls.OUS, error_message='Getting list of ous')
        ]

    @ensure_connected
    def list_labs(self, ou: str) -> list[types.OGLabInfo]:
        # Returns a list of available labs on an ou
        # /ous/{ouid}/labs
        # Take into accout that we must exclude the ones with "inremotepc" set to false.
        error_message = 'Getting list of labs from ou {}'.format(ou)
        return [
            {'id': l['id'], 'name': l['name']}
            for l in self._get(urls.LABS.format(ou=ou), error_message=error_message)
            if l.get('inremotepc', False) is True
        ]

    @ensure_connected
    def list_images(self, ou: str) -> list[types.OGImageInfo]:
        # Returns a list of available labs on an ou
        # /ous/{ouid}/images
        # Take into accout that we must exclude the ones with "inremotepc" set to false.
        error_message = 'Getting list of images from ou {}'.format(ou)
        return [
            {'id': l['id'], 'name': l['name']}
            for l in self._get(urls.IMAGES.format(ou=ou), error_message=error_message)
            if l.get('inremotepc', False) is True
        ]

    @ensure_connected
    def reserve(self, ou: str, image: str, lab: int = 0, maxtime: int = 24) -> types.OGReservationInfo:
        # This method is inteded to "get" a machine from OpenGnsys
        # The method used is POST
        # invokes /ous/{ouid}}/images/{imageid}/reserve
        # also remember to store "labid"
        # Labid can be "0" that means "all laboratories"
        error_message = 'Reserving image {} in ou {}'.format(image, ou)
        data = {'labid': lab, 'maxtime': maxtime}
        res = self._post(urls.RESERVE.format(ou=ou, image=image), data, error_message=error_message)
        return {
            'ou': ou,
            'image': image,
            'lab': lab,
            'client': res['id'],
            'id': '.'.join((str(ou), str(res['lab']['id']), str(res['id']))),
            'name': res['name'],
            'ip': res['ip'],
            'mac': ':'.join(re.findall('..', res['mac'])),
        }

    @ensure_connected
    def unreserve(self, machine_id: str) -> None:
        # This method releases the previous reservation
        # Invoked every time we need to release a reservation (i mean, if a reservation is done, this will be called with the obtained id from that reservation)
        ou, lab, client = machine_id.split('.')
        error_message = 'Unreserving client {} in lab {} in ou {}'.format(client, lab, ou)
        self._delete(urls.UNRESERVE.format(ou=ou, lab=lab, client=client), error_message=error_message)

    @ensure_connected
    def power_on(self, machine_id: str, image: str) -> None:
        # This method ask to poweron a machine to openGnsys
        ou, lab, client = machine_id.split('.')
        try:
            data = {
                'image': image,
            }
            self._post(
                urls.START.format(ou=ou, lab=lab, client=client),
                data,
                error_message=f'Powering on client {client} in lab {lab} in ou {ou}',
            )
        except Exception as e:  # For now, if this fails, ignore it to keep backwards compat
            logger.error('Error powering on machine %s: %s', machine_id, e)

    @ensure_connected
    def notify_endpoints(self, machine_id: str, login_url: str, logout_url: str, release_url: str) -> None:
        ou, lab, client = machine_id.split('.')
        data = {'urlLogin': login_url, 'urlLogout': logout_url, 'urlRelease': release_url}

        self._post(
            urls.EVENTS.format(ou=ou, lab=lab, client=client), data, error_message='Notifying login/logout urls'
        )

    @ensure_connected
    def notify_deadline(self, machine_id: str, dead_line: typing.Optional[int]) -> None:
        ou, lab, client = machine_id.split('.')
        dead_line = dead_line or 0
        data = {'deadLine': dead_line}

        self._post(
            urls.SESSIONS.format(ou=ou, lab=lab, client=client), data, error_message='Notifying deadline'
        )

    @ensure_connected
    def status(self, id_: str) -> types.OGStatusInfo:
        # This method gets the status of the machine
        # /ous/{uoid}/labs/{labid}/clients/{clientid}/status
        # possible status are ("off", "oglive", "busy", "linux", "windows", "macos" o "unknown").
        # Look at api at informatica.us..
        ou, lab, client = id_.split('.')
        response = self._get(urls.STATUS.format(ou=ou, lab=lab, client=client))
        return {
            'id': str(response['id']),
            'ip': response.get('ip', ''),
            'status': response['status'],
            'loggedin': response.get('loggedin', False),
        }
