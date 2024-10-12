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
import json
import logging
import os
import tempfile
import typing
import collections.abc

from uds.core import exceptions, types
from uds.core.util.security import secure_requests_session

if typing.TYPE_CHECKING:
    from uds.models import UserService

logger = logging.getLogger(__name__)

TIMEOUT = 2


def _execute_actor_request(
    userservice: 'UserService',
    method: str,
    data: typing.Optional[collections.abc.MutableMapping[str, typing.Any]] = None,
    min_actor_version: typing.Optional[str] = None,
) -> typing.Any:
    """
    Makes a request to actor using "method"
    if data is None, request is done using GET, else POST
    if no communications url is provided or no min version, raises a "NoActorComms" exception (or OldActorVersion, derived from NoActorComms)
    Returns request response value interpreted as json
    """
    url = userservice.get_comms_endpoint()
    if not url:
        raise exceptions.actor.NoActorComms(f'No notification urls for {userservice.friendly_name}')

    min_actor_version = min_actor_version or '3.5.0'
    version = userservice.properties.get('actor_version', '0.0.0')
    if '-' in version or version < min_actor_version:
        logger.warning('Pool %s has old actors (%s)', userservice.deployed_service.name, version)
        raise exceptions.actor.OldActorVersion(
            f'Old actor version {version} for {userservice.friendly_name}'.format(
                version, userservice.friendly_name
            )
        )

    url += '/' + method

    try:
        verify: typing.Union[bool, str]
        cert = userservice.properties.get('cert', '')
        # cert = ''  # Uncomment to test without cert
        if cert:
            # Generate temp file, and delete it after
            with tempfile.NamedTemporaryFile('wb', delete=False) as f:
                f.write(cert.encode())  # Save cert
                verify = f.name
        else:
            verify = False
        session = secure_requests_session(verify=cert)
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
        if not(isinstance(verify, bool)):
            try:
                os.remove(verify)
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


def notify_preconnect(userservice: 'UserService', info: types.connections.ConnectionData) -> None:
    """
    Notifies a preconnect to an user service
    """
    src = userservice.get_connection_source()
    if userservice.deployed_service.service.get_instance().notify_preconnect(userservice, info) is True:
        return  # Ok, service handled it

    _execute_actor_request(
        userservice,
        'preConnect',
        types.connections.PreconnectRequest(
            user=info.username,
            protocol=info.protocol,
            ip=src.ip,
            hostname=src.hostname,
            udsuser=userservice.user.name + '@' + userservice.user.manager.name if userservice.user else '',
            udsuser_uuid=userservice.user.uuid if userservice.user else '',
            userservice_uuid=userservice.uuid,
            service_type=info.service_type,
        ).as_dict(),
    )


def check_user_service_uuid(user_service: 'UserService') -> bool:
    """
    Checks if the uuid of the service is the same of our known uuid on DB
    """
    try:
        uuid = _execute_actor_request(user_service, 'uuid')
        if uuid and uuid != user_service.uuid:  # Empty UUID means "no check this, fixed pool machine"
            logger.info(
                'Machine %s do not have expected uuid %s, instead has %s',
                user_service.friendly_name,
                user_service.uuid,
                uuid,
            )
            return False
    except exceptions.actor.NoActorComms:
        pass

    return True  # Actor does not supports checking


def request_screenshot(userservice: 'UserService') -> None:
    """
    Requests an screenshot to an actor on an user service
    
    This method is used to request an screenshot to an actor on an user service.
    
    Args:
        userservice: User service to request screenshot from

    Notes:
        The screenshot is not returned directly, but will be returned on a actor REST API call to "screenshot" method.
    """
    try:
        # Data = {} forces an empty POST
        _execute_actor_request(
            userservice, 'screenshot', data={}, min_actor_version='4.0.0'
        )  # First valid version with screenshot is 3.0
    except exceptions.actor.NoActorComms:
        pass # No actor comms, nothing to do


def send_script(userservice: 'UserService', script: str, exec_on_user: bool = False) -> None:
    """
    If allowed, sends script to user service
    Note tha the script is a python script, so it can be executed directly by the actor
    """
    try:
        data: collections.abc.MutableMapping[str, typing.Any] = {'script': script}
        if exec_on_user:
            data['user'] = exec_on_user
        # Data = {} forces an empty POST
        _execute_actor_request(userservice, 'script', data=data)
    except exceptions.actor.NoActorComms:
        pass


def request_logoff(user_service: 'UserService') -> None:
    """
    Ask client to logoff user
    """
    try:
        _execute_actor_request(user_service, 'logout', data={})
    except exceptions.actor.NoActorComms:
        pass


def send_message(userService: 'UserService', message: str) -> None:
    """
    Sends an screen message to client
    """
    try:
        _execute_actor_request(userService, 'message', data={'message': message})
    except exceptions.actor.NoActorComms:
        pass
