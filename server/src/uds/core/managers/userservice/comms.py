# -*- coding: utf-8 -*-
#
# Copyright (c) 2019-2021 Virtual Cable S.L.U.
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
import os
import json
import base64
import tempfile
import logging
import typing
from uds.core import types

from uds.core.util.security import secureRequestsSession

if typing.TYPE_CHECKING:
    from uds.models import UserService

logger = logging.getLogger(__name__)

TIMEOUT = 2


class NoActorComms(Exception):
    pass


class OldActorVersion(NoActorComms):
    pass


def _requestActor(
    userService: 'UserService',
    method: str,
    data: typing.Optional[typing.MutableMapping[str, typing.Any]] = None,
    minVersion: typing.Optional[str] = None,
) -> typing.Any:
    """
    Makes a request to actor using "method"
    if data is None, request is done using GET, else POST
    if no communications url is provided or no min version, raises a "NoActorComms" exception (or OldActorVersion, derived from NoActorComms)
    Returns request response value interpreted as json
    """
    url = userService.getCommsUrl()
    if not url:
        # Maybe service knows how to do it

        # logger.warning('No notification is made because agent does not supports notifications: %s', userService.friendly_name)
        raise NoActorComms(
            f'No notification urls for {userService.friendly_name}'
        )

    minVersion = minVersion or '3.5.0'
    version = userService.getProperty('actor_version') or '0.0.0'
    if '-' in version or version < minVersion:
        logger.warning(
            'Pool %s has old actors (%s)', userService.deployed_service.name, version
        )
        raise OldActorVersion(
            f'Old actor version {version} for {userService.friendly_name}'.format(version, userService.friendly_name)
        )

    url += '/' + method

    try:
        verify: typing.Union[bool, str]
        cert = userService.getProperty('cert') or ''
        # cert = ''  # Uncomment to test without cert
        if cert:
            # Generate temp file, and delete it after
            with tempfile.NamedTemporaryFile('wb', delete=False) as f:
                f.write(cert.encode())  # Save cert
                verify = f.name
        else:
            verify = False
        session = secureRequestsSession(verify=cert)
        if data is None:
            r = session.get(url, verify=verify, timeout=TIMEOUT)
        else:
            r = session.post(
                url,
                data=json.dumps(data),
                headers={'content-type': 'application/json'},
                verify=verify,
                timeout=TIMEOUT,
            )
        if verify:
            try:
                os.remove(typing.cast(str, verify))
            except Exception:
                logger.exception('removing verify')
        js = r.json()

        if version >= '3.0.0':
            js = js['result']
        logger.debug('Requested %s to actor. Url=%s', method, url)
    except Exception as e:
        logger.warning(
            'Request %s failed: %s. Check connection on destination machine: %s',
            method,
            e,
            url,
        )
        js = None

    return js


def notifyPreconnect(userService: 'UserService', info: types.ConnectionInfoType) -> None:
    """
    Notifies a preconnect to an user service
    """
    src = userService.getConnectionSource()

    try:
        _requestActor(
            userService,
            'preConnect',
            {
                'user': info.username,
                'protocol': info.protocol,
                'ip': src.ip,
                'hostname': src.hostname,
                'udsuser': userService.user.name + '@' + userService.user.manager.name if userService.user else '',
            },
        )
    except NoActorComms:
        pass  # If no preconnect, warning will appear on UDS log


def checkUuid(userService: 'UserService') -> bool:
    """
    Checks if the uuid of the service is the same of our known uuid on DB
    """
    try:
        uuid = _requestActor(userService, 'uuid')
        if (
            uuid and uuid != userService.uuid
        ):  # Empty UUID means "no check this, fixed pool machine"
            logger.info(
                'Machine %s do not have expected uuid %s, instead has %s',
                userService.friendly_name,
                userService.uuid,
                uuid,
            )
            return False
    except NoActorComms:
        pass

    return True  # Actor does not supports checking


def requestScreenshot(userService: 'UserService') -> bytes:
    """
    Returns an screenshot in PNG format (bytes) or empty png if not supported
    """
    emptyPng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    try:
        png = _requestActor(
            userService, 'screenshot', minVersion='3.0.0'
        )  # First valid version with screenshot is 3.0
    except NoActorComms:
        png = None

    return base64.b64decode(png or emptyPng)


def sendScript(userService: 'UserService', script: str, forUser: bool = False) -> None:
    """
    If allowed, send script to user service
    """
    try:
        data: typing.MutableMapping[str, typing.Any] = {'script': script}
        if forUser:
            data['user'] = forUser
        _requestActor(userService, 'script', data=data)
    except NoActorComms:
        pass


def requestLogoff(userService: 'UserService') -> None:
    """
    Ask client to logoff user
    """
    try:
        _requestActor(userService, 'logout', data={})
    except NoActorComms:
        pass


def sendMessage(userService: 'UserService', message: str) -> None:
    """
    Sends an screen message to client
    """
    try:
        _requestActor(userService, 'message', data={'message': message})
    except NoActorComms:
        pass
