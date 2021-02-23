# -*- coding: utf-8 -*-

#
# Copyright (c) 2017-2019 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import re
import json
import logging
import typing

import requests

from . import urls
from . import fake

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.util.cache import Cache

# Fake part
FAKE = False
CACHE_VALIDITY = 180

RT = typing.TypeVar('RT')

# Decorator
def ensureConnected(fnc: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    def inner(*args, **kwargs) -> RT:
        args[0].connect()
        return fnc(*args, **kwargs)

    return inner


# Result checker
def ensureResponseIsValid(
    response: requests.Response, errMsg: typing.Optional[str] = None
) -> typing.Any:
    if not response.ok:
        if not errMsg:
            errMsg = 'Invalid response'

        try:
            err = response.json()[
                'message'
            ]  # Extract any key, in case of error is expected to have only one top key so this will work
        except Exception:
            err = response.content
        errMsg = '{}: {}, ({})'.format(errMsg, err, response.status_code)
        logger.error('%s: %s', errMsg, response.content)
        raise Exception(errMsg)

    try:
        return json.loads(response.content)
    except Exception:
        raise Exception(
            'Error communicating with OpenGnsys: {}'.format(
                response.content[:128].decode()
            )
        )


class OpenGnsysClient:
    username: str
    password: str
    endpoint: str
    auth: typing.Optional[str]
    cache: 'Cache'
    verifyCert: bool
    cachedVersion: typing.Optional[str]

    def __init__(
        self,
        username: str,
        password: str,
        endpoint: str,
        cache: 'Cache',
        verifyCert: bool = False,
    ):
        self.username = username
        self.password = password
        self.endpoint = endpoint
        self.auth = None
        self.cache = cache
        self.verifyCert = verifyCert
        self.cachedVersion = None

    @property
    def headers(self) -> typing.MutableMapping[str, str]:
        headers = {'content-type': 'application/json'}
        if self.auth:
            headers['Authorization'] = self.auth

        return headers

    def _ogUrl(self, path: str) -> str:
        return self.endpoint + '/' + path

    def _post(
        self, path: str, data: typing.Any, errMsg: typing.Optional[str] = None
    ) -> typing.Any:
        if not FAKE:
            return ensureResponseIsValid(
                requests.post(
                    self._ogUrl(path),
                    data=json.dumps(data),
                    headers=self.headers,
                    verify=self.verifyCert,
                ),
                errMsg=errMsg,
            )
        # FAKE Connection :)
        return fake.post(path, data, errMsg)

    def _get(self, path: str, errMsg: typing.Optional[str] = None) -> typing.Any:
        if not FAKE:
            return ensureResponseIsValid(
                requests.get(
                    self._ogUrl(path), headers=self.headers, verify=self.verifyCert
                ),
                errMsg=errMsg,
            )
        # FAKE Connection :)
        return fake.get(path, errMsg)

    def _delete(self, path: str, errMsg: typing.Optional[str] = None) -> typing.Any:
        if not FAKE:
            return ensureResponseIsValid(
                requests.delete(
                    self._ogUrl(path), headers=self.headers, verify=self.verifyCert
                ),
                errMsg=errMsg,
            )
        return fake.delete(path, errMsg)

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
            errMsg='Loggin in',
        )

        self.auth = auth['apikey']
        self.cache.put(cacheKey, self.auth, CACHE_VALIDITY)

    @property
    def version(self) -> str:
        logger.debug('Getting version')
        if not self.cachedVersion:
            # Retrieve Version & keep it
            info = self._get(urls.INFO, errMsg="Retrieving info")
            self.cachedVersion = info['version']

        return typing.cast(str, self.cachedVersion)

    @ensureConnected
    def getOus(self) -> typing.Any:
        # Returns an array of elements with:
        # 'id': OpenGnsys Id
        # 'name': OU name
        # OpenGnsys already returns it in this format :)
        return self._get(urls.OUS, errMsg='Getting list of ous')

    @ensureConnected
    def getLabs(self, ou: str) -> typing.List[typing.MutableMapping[str, str]]:
        # Returns a list of available labs on an ou
        # /ous/{ouid}/labs
        # Take into accout that we must exclude the ones with "inremotepc" set to false.
        errMsg = 'Getting list of labs from ou {}'.format(ou)
        return [
            {'id': l['id'], 'name': l['name']}
            for l in self._get(urls.LABS.format(ou=ou), errMsg=errMsg)
            if l.get('inremotepc', False) is True
        ]

    @ensureConnected
    def getImages(self, ou: str) -> typing.List[typing.MutableMapping[str, str]]:
        # Returns a list of available labs on an ou
        # /ous/{ouid}/images
        # Take into accout that we must exclude the ones with "inremotepc" set to false.
        errMsg = 'Getting list of images from ou {}'.format(ou)
        return [
            {'id': l['id'], 'name': l['name']}
            for l in self._get(urls.IMAGES.format(ou=ou), errMsg=errMsg)
            if l.get('inremotepc', False) is True
        ]

    @ensureConnected
    def reserve(
        self, ou: str, image: str, lab: int = 0, maxtime: int = 24
    ) -> typing.MutableMapping[str, typing.Union[str, int]]:
        # This method is inteded to "get" a machine from OpenGnsys
        # The method used is POST
        # invokes /ous/{ouid}}/images/{imageid}/reserve
        # also remember to store "labid"
        # Labid can be "0" that means "all laboratories"
        errMsg = 'Reserving image {} in ou {}'.format(image, ou)
        data = {'labid': lab, 'maxtime': maxtime}
        res = self._post(urls.RESERVE.format(ou=ou, image=image), data, errMsg=errMsg)
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

    @ensureConnected
    def unreserve(self, machineId: str) -> typing.Any:
        # This method releases the previous reservation
        # Invoked every time we need to release a reservation (i mean, if a reservation is done, this will be called with the obtained id from that reservation)
        ou, lab, client = machineId.split('.')
        errMsg = 'Unreserving client {} in lab {} in ou {}'.format(client, lab, ou)
        return self._delete(
            urls.UNRESERVE.format(ou=ou, lab=lab, client=client), errMsg=errMsg
        )

    @ensureConnected
    def powerOn(self, machineId, image):
        # This method ask to poweron a machine to openGnsys
        ou, lab, client = machineId.split('.')
        errMsg = 'Powering on client {} in lab {} in ou {}'.format(client, lab, ou)
        try:
            data = {
                'image': image,
            }
            return self._post(
                urls.START.format(ou=ou, lab=lab, client=client), data, errMsg=errMsg
            )
        except Exception:  # For now, if this fails, ignore it to keep backwards compat
            return 'OK'

    @ensureConnected
    def notifyURLs(
        self, machineId: str, loginURL: str, logoutURL: str, releaseURL: str
    ) -> typing.Any:
        ou, lab, client = machineId.split('.')
        errMsg = 'Notifying login/logout urls'
        data = {'urlLogin': loginURL, 'urlLogout': logoutURL, 'urlRelease': releaseURL}

        return self._post(
            urls.EVENTS.format(ou=ou, lab=lab, client=client), data, errMsg=errMsg
        )

    @ensureConnected
    def notifyDeadline(
        self, machineId: str, deadLine: typing.Optional[int]
    ) -> typing.Any:
        ou, lab, client = machineId.split('.')
        deadLine = deadLine or 0
        errMsg = 'Notifying deadline'
        data = {'deadLine': deadLine}

        return self._post(
            urls.SESSIONS.format(ou=ou, lab=lab, client=client), data, errMsg=errMsg
        )

    @ensureConnected
    def status(self, id_: str) -> typing.Any:
        # This method gets the status of the machine
        # /ous/{uoid}/labs/{labid}/clients/{clientid}/status
        # possible status are ("off", "oglive", "busy", "linux", "windows", "macos" o "unknown").
        # Look at api at informatica.us..
        ou, lab, client = id_.split('.')
        return self._get(urls.STATUS.format(ou=ou, lab=lab, client=client))
